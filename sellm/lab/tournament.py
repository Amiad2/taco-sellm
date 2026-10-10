"""Play strategies against the lab's suppliers and rank them.

Two modes:
- `compare`: named strategies (see `strategies.registry`) on every twin and invented scenario,
  several seeds each.
- `search`: random variants of the `Calculator` knobs, successive halving - many variants on few
  scenarios, the better half on twice as many, until the time is up - plus the baselines.

The ranking is by the mean score over all scenarios. The report also shows the twins and the
invented scenarios apart, the held-out twins (P04, P10, P18 per docs/PLAN.md section 8), the worst
tenth, and every crash, broken must-have and deal worse than the opening (score 0 with a deal).
"""

import json
import math
import os
import random
import statistics
import time
import traceback
from concurrent.futures import ProcessPoolExecutor

from arena_kit.play import play

from . import invent, twins
from .strategies import registry, sample_knobs
from .table import LocalTable

HOLDOUT = {"P04", "P10", "P18"}
_W = {}  # per worker process: the package and the scenarios


def _init(n_invented, invent_seed):
    from arena_kit.data import DataPackage

    pkg = DataPackage(os.environ.get("ARENA_DATA", "data/package"))
    pkg.lookup("")
    scen = twins.load()
    scen += invent.generate(n_invented, scen, pkg, seed=invent_seed)
    _W.update(pkg=pkg, scenarios={s.name: s for s in scen})


def _play(job):
    """One negotiation: (strategy name, knobs, scenario name, seed) -> a result row."""
    name, knobs, scen_name, seed = job
    s = _W["scenarios"][scen_name]
    row = {"strategy": name, "knobs": knobs, "scenario": scen_name, "kind": s.kind, "seed": seed}
    try:
        agent = registry(_W["pkg"])[name](**(knobs or {}))
        r = play(LocalTable(s, _W["pkg"].facts, seed=seed), s.case["case_id"], agent)
        row.update(
            score=r["score"],
            deal=r["deal"],
            rounds=r.get("rounds"),
            end=r.get("end_reason"),
            broken=bool(r["deal"] and not r["must_haves_ok"]),
            worse=bool(r["deal"] and r["c_deal"] > r["c_open"]),
        )
    except Exception as e:  # a crash is a result too: it would cost the case in the final
        row.update(score=0.0, deal=False, crash=f"{type(e).__name__}: {e}"[:200], trace=traceback.format_exc()[-600:])
    return row


def _scenario_names(n_invented, invent_seed):
    _init(n_invented, invent_seed)
    return list(_W["scenarios"]), {k: v.kind for k, v in _W["scenarios"].items()}


def compare(names, n_invented=100, seeds=3, workers=None, invent_seed=1):
    scen, _ = _scenario_names(n_invented, invent_seed)
    jobs = [(n, {}, s, seed) for n in names for s in scen for seed in range(seeds)]
    with ProcessPoolExecutor(workers, initializer=_init, initargs=(n_invented, invent_seed)) as pool:
        return list(pool.map(_play, jobs, chunksize=16))


def search(minutes=10, n_invented=150, start=64, seeds=2, workers=None, invent_seed=1, seed=0, log=print):
    """Successive halving over random Calculator knobs within `minutes`; baselines always run."""
    rng = random.Random(seed)
    scen, _ = _scenario_names(n_invented, invent_seed)
    rng.shuffle(scen)
    deadline = time.time() + 60 * minutes
    variants = [("calc", {})] + [("calc", sample_knobs(rng)) for _ in range(start - 1)]
    rows, size = [], max(12, len(scen) // 8)
    with ProcessPoolExecutor(workers, initializer=_init, initargs=(n_invented, invent_seed)) as pool:
        base = [(n, {}, s, k) for n in ("naive",) for s in scen for k in range(seeds)]
        rows += list(pool.map(_play, base, chunksize=16))
        done = {}  # (name, knobs json) -> scenarios already played
        while variants and time.time() < deadline:
            subset = scen[:size]
            jobs = []
            for name, knobs in variants:
                key = (name, json.dumps(knobs, sort_keys=True))
                have = done.setdefault(key, set())
                jobs += [(name, knobs, s, k) for s in subset if s not in have for k in range(seeds)]
                have.update(subset)
            rows += list(pool.map(_play, jobs, chunksize=16))
            means = {}
            for r in rows:
                key = (r["strategy"], json.dumps(r["knobs"], sort_keys=True))
                means.setdefault(key, []).append(r["score"])
            ranked = sorted(variants, key=lambda v: -statistics.mean(means[(v[0], json.dumps(v[1], sort_keys=True))]))
            log(
                f"{time.strftime('%H:%M:%S')} {len(variants)} variants on {len(subset)} scenarios; "
                f"best {statistics.mean(means[(ranked[0][0], json.dumps(ranked[0][1], sort_keys=True))]):.3f}"
            )
            if size >= len(scen):
                # all scenarios played: refill with mutations of the best, keep searching
                keep = ranked[: max(4, len(ranked) // 4)]
                variants = keep + [("calc", mutate(rng, keep[i % len(keep)][1])) for i in range(len(keep) * 3)]
            else:
                variants = ranked[: max(4, len(ranked) // 2)]
                size = min(len(scen), size * 2)
    return rows


def mutate(rng, knobs):
    """A neighbour of a variant: one or two knobs re-drawn."""
    fresh = sample_knobs(rng)
    out = dict(knobs)
    for k in rng.sample(list(fresh), rng.randint(1, 2)):
        out[k] = fresh[k]
    return out


def summarise(rows, min_scenarios=0):
    """{variant key: stats} over the rows; variants played on fewer scenarios are left out."""
    by = {}
    for r in rows:
        key = r["strategy"] + (" " + json.dumps(r["knobs"], sort_keys=True) if r["knobs"] else "")
        by.setdefault(key, []).append(r)
    out = {}
    for key, rs in by.items():
        scen = {r["scenario"] for r in rs}
        if len(scen) < min_scenarios:
            continue
        per = {}
        for r in rs:
            per.setdefault(r["scenario"], []).append(r["score"])
        means = {s: statistics.mean(v) for s, v in per.items()}
        kinds = {r["scenario"]: r["kind"] for r in rs}
        twin = [v for s, v in means.items() if kinds[s] == "twin"]
        inv = [v for s, v in means.items() if kinds[s] == "invented"]
        hold = [v for s, v in means.items() if s in HOLDOUT]
        worst = sorted(means.values())[: max(1, len(means) // 10)]
        out[key] = {
            "strategy": rs[0]["strategy"],
            "knobs": rs[0]["knobs"],
            "scenarios": len(scen),
            "mean": statistics.mean(means.values()),
            "twins": statistics.mean(twin) if twin else math.nan,
            "invented": statistics.mean(inv) if inv else math.nan,
            "holdout": statistics.mean(hold) if hold else math.nan,
            "worst10": statistics.mean(worst),
            "crashes": sum("crash" in r for r in rs),
            "broken": sum(r.get("broken", False) for r in rs),
            "worse": sum(r.get("worse", False) for r in rs),
            "no_deal": sum(not r.get("deal") for r in rs),
            "per_twin": {s: round(v, 3) for s, v in sorted(means.items()) if kinds[s] == "twin"},
        }
    return out


def report(rows, title, top=12, min_scenarios=0):
    stats = summarise(rows, min_scenarios)
    ranked = sorted(stats.values(), key=lambda x: -x["mean"])
    lines = [
        f"# {title}",
        "",
        f"{len(rows)} negotiations, {len({r['scenario'] for r in rows})} scenarios "
        f"({sum(1 for s in {(r['scenario'], r['kind']) for r in rows} if s[1] == 'twin')} twins). "
        "Scores x 100; 'worst 10 %' is the mean of the worst tenth of scenarios; crashes, broken "
        "must-haves and deals worse than the opening are counted per negotiation.",
        "",
        "| # | Strategy | Knobs | Scen. | Mean | Twins | Invented | Held-out | Worst 10 % "
        "| No deal | Crash | Broken | Worse |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for i, s in enumerate(ranked[:top], 1):
        knobs = ", ".join(f"{k}={v}" for k, v in sorted((s["knobs"] or {}).items())) or "-"
        lines.append(
            f"| {i} | {s['strategy']} | {knobs} | {s['scenarios']} | **{100 * s['mean']:.1f}** | "
            f"{100 * s['twins']:.1f} | {100 * s['invented']:.1f} | {100 * s['holdout']:.1f} | "
            f"{100 * s['worst10']:.1f} | {s['no_deal']} | {s['crashes']} | {s['broken']} | {s['worse']} |"
        )
    base = [s for s in ranked if not s["knobs"]]
    if base and ranked[0] not in base:
        lines += ["", "Baselines:", ""]
        for s in base:
            lines.append(
                f"- {s['strategy']}: mean {100 * s['mean']:.1f}, twins {100 * s['twins']:.1f}, "
                f"invented {100 * s['invented']:.1f}"
            )
    lines += ["", "Per twin (best three and baselines):", ""]
    show = ranked[:3] + [s for s in base if s not in ranked[:3]]
    names = sorted({t for s in show for t in s["per_twin"]})
    lines.append("| Strategy | " + " | ".join(names) + " |")
    lines.append("|---|" + "---|" * len(names))
    for s in show:
        label = s["strategy"] + (" #" + str(ranked.index(s) + 1) if s["knobs"] else "")
        lines.append(f"| {label} | " + " | ".join(f"{s['per_twin'].get(n, math.nan):.2f}" for n in names) + " |")
    crashes = [r for r in rows if "crash" in r]
    if crashes:
        lines += ["", f"Crashes ({len(crashes)}), first ones:", ""]
        for r in crashes[:5]:
            lines.append(f"- {r['strategy']} {r['scenario']}: {r['crash']}")
    return "\n".join(lines) + "\n"
