"""Play strategies against the lab's suppliers, rank them, and show where they are weak.

Scenario pools (built once per run in the main process, saved as `scenarios.json.gz`, loaded by every
worker):
- **train**: the twins except the held-out ones (P04, P10, P18, docs/PLAN.md section 8), plus
  generated scenarios (unplayed case files and invented ones, `invent.py`).
- **test**: the held-out twins plus freshly generated scenarios from another seed. A search never
  looks at them; its best variants are scored on them at the end, so the report shows how much of
  a gain survives on cases it was not tuned on.

Modes:
- `compare`: named strategies on train and test.
- `search`: random variants of the `Calculator` knobs, successive halving (many variants on few
  scenarios, the better half on twice as many), then mutations of the best, until the time is up -
  checked between batches, not only between rounds - then the test phase.

Every negotiation runs with the clock and the wave cap (`play_lab`), sequentially as the kit's
runner or with one loop per thread, and twins vary within their families. Progress goes to
`progress.log` in the run folder as it happens.
"""

import importlib
import json
import math
import os
import random
import statistics
import time
import traceback
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from . import invent, store, twins
from .strategies import registry, sample_knobs
from .table import LocalTable, play_lab

HOLDOUT = {"P04", "P10", "P18"}
BATCH = 400  # negotiations between two looks at the clock
_W = {}  # per worker process


def build_pools(n_invented, invent_seed, n_test, package):
    tw = twins.load()
    train = [s for s in tw if s.name not in HOLDOUT] + invent.generate(n_invented, package, seed=invent_seed)
    test = [s for s in tw if s.name in HOLDOUT] + invent.generate(n_test, package, seed=invent_seed + 1000)
    return train, test


def _init(path, opts):
    from arena_kit.data import DataPackage

    pkg = DataPackage(os.environ.get("ARENA_DATA", "data/package"))
    pkg.lookup("")
    _W.update(pkg=pkg, scenarios={s.name: s for s in store.load(path)}, opts=opts)


def make_agent(name, knobs, package):
    """A strategy by name: naive, calc, llm, or any importable 'module:Class' (built with the data
    package if its constructor takes one, then the knobs)."""
    if ":" in name:
        module, cls = name.split(":", 1)
        klass = getattr(importlib.import_module(module), cls)
        try:
            return klass(package, **(knobs or {}))
        except TypeError:
            return klass(**(knobs or {}))
    return registry(package)[name](**(knobs or {}))


def _alt_score(s):
    from arena_kit.cost import score

    return score(s.c_open, s.c_alt, s.c_best) if s.c_alt else 0.0


def _play(job):
    """One negotiation: (strategy name, knobs, scenario name, seed) -> a result row."""
    name, knobs, scen_name, seed = job
    s, o = _W["scenarios"][scen_name], _W["opts"]
    row = {
        "strategy": name,
        "knobs": knobs,
        "scenario": scen_name,
        "kind": s.kind,
        "seed": seed,
        "type": s.case.get("type"),
        "goal": s.case["buyer"].get("category_goal"),
        "tags": s.tags,
        "archetypes": sorted({p.archetype for p in s.personas.values()}),
        "pool": s.notes,
    }
    t0 = time.monotonic()
    try:
        agent = make_agent(name, knobs, _W["pkg"])
        table = LocalTable(
            s,
            _W["pkg"].facts,
            seed=seed,
            clock=o["clock"],
            wave_cap_s=o["wave_cap_s"],
            think_s=o["think_s"],
            vary=o["vary"] and s.kind == "twin",
        )
        r = play_lab(table, agent, mode=o["mode"])
        row.update(
            score=r["score"],
            deal=r["deal"],
            rounds=r.get("rounds"),
            end=r.get("end_reason"),
            broken=bool(r["deal"] and not r["must_haves_ok"]),
            worse=bool(r["deal"] and r["c_deal"] > r["c_open"]),
            timeouts=r.get("timeouts", 0),
            rejected=r.get("rejected", 0),
            seconds=r.get("seconds"),
            alt_score=_alt_score(s),
            c_deal=r.get("c_deal"),
        )
    except Exception as e:  # a crash is a result too: it would cost the case in the final
        row.update(score=0.0, deal=False, crash=f"{type(e).__name__}: {e}"[:200], trace=traceback.format_exc()[-800:])
    row["wall_s"] = round(time.monotonic() - t0, 3)
    return row


class Run:
    """A run folder with its scenario pools, a pool of workers and a progress log."""

    def __init__(self, out, opts, train, test, workers=None, log=print):
        self.out, self.opts, self.log_fn = Path(out), opts, log
        self.out.mkdir(parents=True, exist_ok=True)
        self.progress = open(self.out / "progress.log", "a", encoding="utf-8", buffering=1)  # noqa: SIM115
        self.train, self.test = train, test
        for s in self.train:
            s.notes = "train"
        for s in self.test:
            s.notes = "test"
        path = self.out / "scenarios.json.gz"
        store.save(self.train + self.test, path)
        n_tw_train = sum(s.kind == "twin" for s in self.train)
        n_tw_test = sum(s.kind == "twin" for s in self.test)
        self.log(
            f"pools: train {len(self.train)} ({n_tw_train} twins), test {len(self.test)} ({n_tw_test} twins); "
            f"options {opts}"
        )
        self.pool = ProcessPoolExecutor(workers, initializer=_init, initargs=(str(path), opts))

    def log(self, text):
        line = f"{time.strftime('%H:%M:%S')} {text}"
        self.progress.write(line + "\n")
        self.log_fn(line)

    def play(self, jobs, deadline=None):
        """Rows for the jobs, in batches; stops early (keeping what is done) once past `deadline`."""
        rows = []
        for i in range(0, len(jobs), BATCH):
            if deadline and time.time() > deadline:
                self.log(f"time is up: {len(jobs) - i} negotiations of this round not played")
                break
            rows += list(self.pool.map(_play, jobs[i : i + BATCH], chunksize=8))
        return rows

    def close(self):
        self.pool.shutdown()
        self.progress.close()


def _key(name, knobs):
    return name + (" " + json.dumps(knobs, sort_keys=True) if knobs else "")


def compare(run, names, seeds=2, knobs=None):
    knobs = knobs or {}
    jobs = [(n, knobs.get(n, {}), s.name, k) for n in names for s in run.train + run.test for k in range(seeds)]
    run.log(f"compare {names}: {len(jobs)} negotiations")
    t0 = time.time()
    rows = run.play(jobs)
    run.log(f"done in {time.time() - t0:.0f} s")
    return rows


def search(run, minutes=10, start=64, seeds=2, seed=0, test_top=8, test_seeds=3, baselines=("naive",)):
    """Successive halving over random Calculator knobs on the train pool, then the best `test_top`
    variants, the default and the baselines on the test pool."""
    rng = random.Random(seed)
    names = [s.name for s in run.train]
    rng.shuffle(names)
    deadline = time.time() + 60 * minutes * 0.85  # the rest of the time is for the test phase
    variants = [("calc", {})] + [("calc", sample_knobs(rng)) for _ in range(start - 1)]
    size, played = max(12, len(names) // 8), {}
    rows = run.play([(b, {}, n, k) for b in baselines for n in names for k in range(seeds)])
    rnd = 0
    while variants and time.time() < deadline:
        rnd += 1
        subset = names[:size]
        jobs = []
        for name, knobs in variants:
            have = played.setdefault(_key(name, knobs), set())
            jobs += [(name, knobs, n, k) for n in subset if n not in have for k in range(seeds)]
            have.update(subset)
        rows += run.play(jobs, deadline)
        means = {}
        for r in rows:
            means.setdefault(_key(r["strategy"], r["knobs"]), []).append(r["score"])
        ranked = sorted(variants, key=lambda v: -statistics.mean(means.get(_key(*v), [0])))
        best = statistics.mean(means.get(_key(*ranked[0]), [0]))
        run.log(f"round {rnd}: {len(variants)} variants on {len(subset)} train scenarios, best {100 * best:.1f}")
        if size >= len(names):
            keep = ranked[: max(4, len(ranked) // 4)]
            variants = keep + [("calc", mutate(rng, keep[i % len(keep)][1])) for i in range(len(keep) * 3)]
        else:
            variants = ranked[: max(4, len(ranked) // 2)]
            size = min(len(names), size * 2)
    calc_rows = [r for r in rows if r["strategy"] == "calc"]
    stats = summarise(calc_rows, min_scenarios=len(names))
    top = sorted(stats.values(), key=lambda x: -x["mean"])[:test_top]
    if not top:  # nothing was played on every train scenario: take the widest-played ones
        top = sorted(summarise(calc_rows).values(), key=lambda x: (-x["scenarios"], -x["mean"]))[:test_top]
    cands = [("calc", t["knobs"]) for t in top] + [(b, {}) for b in baselines]
    if not any(n == "calc" and not k for n, k in cands):
        cands.append(("calc", {}))
    run.log(f"test phase: {len(cands)} strategies on {len(run.test)} test scenarios, {test_seeds} seeds")
    rows += run.play([(n, k, s.name, 100 + j) for n, k in cands for s in run.test for j in range(test_seeds)])
    run.log("search done")
    return rows


def mutate(rng, knobs):
    """A neighbour of a variant: one or two knobs re-drawn."""
    fresh = sample_knobs(rng)
    out = dict(knobs)
    for k in rng.sample(list(fresh), rng.randint(1, 2)):
        out[k] = fresh[k]
    return out


def _mean(xs):
    return statistics.mean(xs) if xs else math.nan


def _vals(row, dim):
    v = row.get(dim)
    return v if isinstance(v, list) else [v] if v is not None else []


def summarise(rows, min_scenarios=0):
    """{variant: stats} over the rows; variants played on fewer scenarios are left out."""
    by = {}
    for r in rows:
        by.setdefault(_key(r["strategy"], r["knobs"]), []).append(r)
    out = {}
    for key, rs in by.items():
        per = {}
        for r in rs:
            per.setdefault(r["scenario"], []).append(r)
        if len(per) < min_scenarios:
            continue
        means = {s: _mean([r["score"] for r in v]) for s, v in per.items()}
        first = {s: v[0] for s, v in per.items()}
        worst = sorted(means.values())[: max(1, len(means) // 10)]

        def part(pred, means=means, first=first):
            return _mean([m for s, m in means.items() if pred(first[s])])

        out[key] = {
            "strategy": rs[0]["strategy"],
            "knobs": rs[0]["knobs"],
            "scenarios": len(per),
            "negotiations": len(rs),
            "mean": _mean(list(means.values())),
            "train": part(lambda r: r["pool"] == "train"),
            "test": part(lambda r: r["pool"] == "test"),
            "twins": part(lambda r: r["kind"] == "twin"),
            "data": part(lambda r: r["kind"] == "data"),
            "invented": part(lambda r: r["kind"] == "invented"),
            "worst10": _mean(worst),
            "crashes": sum("crash" in r for r in rs),
            "rejected": sum(r.get("rejected", 0) for r in rs),
            "broken": sum(r.get("broken", False) for r in rs),
            "worse": sum(r.get("worse", False) for r in rs),
            "no_deal": sum(not r.get("deal") for r in rs),
            "below_alt": sum(r["score"] < r.get("alt_score", 0) - 1e-9 for r in rs if "crash" not in r),
            "wave_cap": sum(r.get("end") == "wave_cap" for r in rs),
            "timeouts": sum(r.get("timeouts", 0) for r in rs),
            "seconds": _mean([r["seconds"] for r in rs if r.get("seconds") is not None]),
            "per_twin": {s: round(m, 3) for s, m in sorted(means.items()) if first[s]["kind"] == "twin"},
            "by": {
                dim: {
                    v: round(_mean([m for s, m in means.items() if v in _vals(first[s], dim)]), 3)
                    for v in sorted({x for r in first.values() for x in _vals(r, dim)})
                }
                for dim in ("type", "goal", "archetypes", "tags")
            },
        }
    return out


def _rank(stats, sort):
    return sorted(stats.values(), key=lambda x: -(x[sort] if not math.isnan(x[sort]) else -1))


def report(rows, title, sort="test", top=12, min_scenarios=0):
    stats = summarise(rows, min_scenarios)
    ranked = _rank(stats, sort)
    n_scen = len({r["scenario"] for r in rows})

    def f(x):
        return "-" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{100 * x:.1f}"

    lines = [
        f"# {title}",
        "",
        f"{len(rows)} negotiations on {n_scen} scenarios. Scores x 100. **Test** = scenarios the search never "
        "saw (held-out twins P04/P10/P18 and freshly generated ones): rank by it. Train = what the search tuned "
        "on. Worst 10 % = mean of the worst tenth of scenarios. Counts are per negotiation: crashes and refused "
        "moves (422) would cost cases in the final; broken must-haves and deals worse than the opening score 0; "
        "'below alt' = ended under what walking away would have scored.",
        "",
        "| # | Strategy | Knobs | Test | Train | Twins | Case files | Invented | Worst 10 % | Crash | 422 "
        "| Broken | Worse | Below alt | Wave cap | Timeouts | No deal |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for i, s in enumerate(ranked[:top], 1):
        knobs = ", ".join(f"{k}={v}" for k, v in sorted((s["knobs"] or {}).items())) or "default"
        lines.append(
            f"| {i} | {s['strategy']} | {knobs} | **{f(s['test'])}** | {f(s['train'])} | {f(s['twins'])} | "
            f"{f(s['data'])} | {f(s['invented'])} | {f(s['worst10'])} | {s['crashes']} | {s['rejected']} | "
            f"{s['broken']} | {s['worse']} | {s['below_alt']} | {s['wave_cap']} | {s['timeouts']} | {s['no_deal']} |"
        )
    if not ranked:
        return "\n".join(lines) + "\n"
    win = ranked[0]
    show = [win] + [s for s in ranked if not s["knobs"] and s is not win]

    def label(s):
        return "#1" if s is win else s["strategy"] + (" default" if s["strategy"] == "calc" else "")

    lines += ["", "## Where the winner (#1) is weak, next to the baselines", ""]
    dims = (("type", "case type"), ("goal", "goal"), ("archetypes", "supplier archetype"), ("tags", "edge case"))
    for dim, name in dims:
        keys = sorted({k for s in show for k in s["by"][dim]})
        if not keys:
            continue
        lines.append(f"| By {name} | " + " | ".join(keys) + " |")
        lines.append("|---|" + "---|" * len(keys))
        for s in show:
            lines.append(f"| {label(s)} | " + " | ".join(f(s["by"][dim].get(k)) for k in keys) + " |")
        lines.append("")
    twins_ = sorted({t for s in show for t in s["per_twin"]})
    if twins_:
        lines.append("| Per twin | " + " | ".join(twins_) + " |")
        lines.append("|---|" + "---|" * len(twins_))
        for s in show:
            lines.append(f"| {label(s)} | " + " | ".join(f(s["per_twin"].get(n)) for n in twins_) + " |")
    crashes = [r for r in rows if "crash" in r]
    if crashes:
        lines += ["", f"## Crashes ({len(crashes)}), first ones", ""]
        for r in crashes[:5]:
            lines.append(f"- {r['strategy']} on {r['scenario']} ({r['tags']}): `{r['crash']}`")
    return "\n".join(lines) + "\n"


def write(run, rows, title, sort="test", min_scenarios=0):
    """report.md, best.json (the ten best with their knobs) and rows.jsonl.gz into the run folder."""
    import gzip

    text = report(rows, title, sort=sort, min_scenarios=min_scenarios)
    (run.out / "report.md").write_text(text, encoding="utf-8")
    with gzip.open(run.out / "rows.jsonl.gz", "wt", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps({k: v for k, v in r.items() if k != "trace"}, default=str) + "\n")
    best = _rank(summarise(rows, min_scenarios), sort)[:10]
    (run.out / "best.json").write_text(json.dumps(best, indent=1, default=str) + "\n", encoding="utf-8")
    return text
