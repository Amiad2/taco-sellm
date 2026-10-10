# ruff: noqa: E501  (report lines)
"""Experiment (Sun 00:30, Omar): the price path of `--agent sellm`, swept in the lab.

Questions (experiments/PRICE-PATH.md): does a lower or a different first ask pay (`open_below`, now
0.06 below the target); how far can the target be pushed before suppliers stop (`target_scale`);
does a longer horizon than 4 rounds catch more (`horizon`); do relationship suppliers take a harder
push (`rel`: knobs used only when the case's goal is stabilise or secure_supply); what would knowing
each supplier's full cost gain (`oracle`, the lab persona's calibrated floor, optionally off by
`oracle_bias`).

Every variant is `sellm.agent.make_agent` (what `--agent sellm` plays) plus these test switches;
nothing in sellm/ changes. Engine suppliers only (free, deterministic per seed), clock on, one loop
per thread, the fitted twins (no family variation) plus invented scenarios.

    uv run python -m experiments.price_path [--seeds 3] [--invented 120] [--only base,open_0.10]
"""

import argparse
import collections
import gzip
import json
import math
import os
import statistics
import time
from pathlib import Path

from arena_kit.cost import RELATIONSHIP_GOALS

AGENT = "experiments.price_path:make"
OWN = ("oracle", "oracle_bias", "target_scale", "rel")

VARIANTS = {
    "base": {},
    # the first ask (target x (1 - open_below)); 0.06 is today's
    "open_0.00": {"open_below": 0.0},
    "open_0.03": {"open_below": 0.03},
    "open_0.10": {"open_below": 0.10},
    "open_0.15": {"open_below": 0.15},
    "open_0.20": {"open_below": 0.20},
    # the target itself pushed lower (first ask and the relationship stop move with it)
    "target_0.97": {"target_scale": 0.97},
    "target_0.94": {"target_scale": 0.94},
    "target_0.90": {"target_scale": 0.90},
    "target_0.85": {"target_scale": 0.85},
    # rounds until our price should meet its price; 4 is today's
    "horizon_3": {"horizon": 3},
    "horizon_6": {"horizon": 6},
    "horizon_8": {"horizon": 8},
    "horizon_10": {"horizon": 10},
    "horizon_6+open_0.10": {"horizon": 6, "open_below": 0.10},
    # a harder push only where the goal is stabilise or secure_supply
    "rel_horizon_6": {"rel": {"horizon": 6}},
    "rel_open_0.10": {"rel": {"open_below": 0.10}},
    "rel_target_0.95": {"rel": {"target_scale": 0.95}},
    "rel_h6+open_0.10": {"rel": {"horizon": 6, "open_below": 0.10}},
    # knowing the supplier's full cost (the lab's calibrated floor), exact or 5 % off
    "oracle": {"oracle": True},
    "oracle+5%": {"oracle": True, "oracle_bias": 0.05},
    "oracle-5%": {"oracle": True, "oracle_bias": -0.05},
    "oracle+horizon_6": {"oracle": True, "horizon": 6},
    # the oracle's first ask at several distances below the true floor: where does a supplier stop?
    "oracle+open_0.00": {"oracle": True, "open_below": 0.0},
    "oracle+open_0.03": {"oracle": True, "open_below": 0.03},
    "oracle+open_0.10": {"oracle": True, "open_below": 0.10},
    "oracle+open_0.15": {"oracle": True, "open_below": 0.15},
    # one more ask after its final offer instead of accepting (sellm/endgame.py push_final)
    "push_final_0.005": {"push_final": 0.005},
    "push_final_0.01": {"push_final": 0.01},
}


def _floor(case_id, sid):
    """The lab persona's full cost (its floor) of this supplier in this case, in the worker."""
    from sellm.lab import tournament

    index = tournament._W.get("_floors")
    if index is None:
        index = {}
        for s in tournament._W.get("scenarios", {}).values():
            for supplier, persona in s.personas.items():
                index[(s.case.get("case_id"), supplier)] = getattr(persona, "full_cost", None)
        tournament._W["_floors"] = index
    return index.get((case_id, sid))


def make(package=None, **knobs):
    """`sellm.agent.make_agent` with the test switches of this experiment."""
    from sellm.agent import make_agent

    own = {k: knobs.pop(k) for k in list(knobs) if k in OWN}
    agent = make_agent(package, **knobs)
    if own:
        _patch(agent, own)
    return agent


def _patch(agent, own):
    should_cost, aim, decide = agent.should_cost, agent.aim, agent.decide
    state = {"in_aim": False, "seen": set()}

    def oracle_should_cost(case, sid):
        if own.get("oracle") and state["in_aim"]:  # only the target, never a cited fact
            floor = _floor(case.get("case_id"), sid)
            if floor:
                return ("oracle", floor * (1 + own.get("oracle_bias", 0.0)))
        return should_cost(case, sid)

    def scaled_aim(case, v, s0):
        state["in_aim"] = True
        try:
            found = aim(case, v, s0)
        finally:
            state["in_aim"] = False
        if own.get("target_scale") and not found.get("_scaled"):  # the memo holds it: scale once
            found["target"] *= own["target_scale"]
            found["_scaled"] = True
        return found

    def goal_decide(case, threads, focus=None):
        rel = own.get("rel")
        if rel and case.get("case_id") not in state["seen"]:
            state["seen"].add(case.get("case_id"))
            if (case.get("buyer") or {}).get("category_goal") in RELATIONSHIP_GOALS:
                agent.k.update({k: x for k, x in rel.items() if k in agent.k})
                if hasattr(agent, "e"):
                    agent.e.update({k: x for k, x in rel.items() if k in agent.e})
                own.update({k: x for k, x in rel.items() if k in OWN})
        return decide(case, threads, focus)

    agent.should_cost, agent.aim, agent.decide = oracle_should_cost, scaled_aim, goal_decide


def _name_of(knobs):
    for name, k in VARIANTS.items():
        if k == knobs:
            return name
    return json.dumps(knobs, sort_keys=True)


def summarise(rows, seeds):
    """Per variant: mean score, paired difference to base (same scenario and seed) with its
    standard error, deals lost, rounds; split by twins/invented and relationship goal."""
    by = collections.defaultdict(dict)
    for r in rows:
        by[r["variant"]][(r["scenario"], r["seed"])] = r
    base = by.get("base", {})
    out = []
    for name in VARIANTS:
        cells = by.get(name)
        if not cells:
            continue
        line = {"variant": name, "n": len(cells)}
        for group, keep in (
            ("all", lambda r: True),
            ("twins", lambda r: r["kind"] == "twin"),
            ("invented", lambda r: r["kind"] != "twin"),
            ("relationship", lambda r: r["goal"] in RELATIONSHIP_GOALS),
            ("other_goals", lambda r: r["goal"] not in RELATIONSHIP_GOALS),
        ):
            mine = [r for r in cells.values() if keep(r)]
            if not mine:
                continue
            diffs = [r["score"] - base[k]["score"] for k, r in cells.items() if keep(r) and k in base]
            se = statistics.stdev(diffs) / math.sqrt(len(diffs)) if len(diffs) > 1 else 0.0
            line[group] = {
                "mean": round(100 * statistics.mean(r["score"] for r in mine), 2),
                "diff": round(100 * statistics.mean(diffs), 2) if diffs else None,
                "se": round(100 * se, 2),
                "better": sum(d > 0.005 for d in diffs),
                "worse": sum(d < -0.005 for d in diffs),
                "no_deal": sum(not r.get("deal") for r in mine),
                "walked": sum(r.get("end") == "walked_away" for r in mine),
                "rounds": round(statistics.mean(r.get("rounds") or 0 for r in mine), 2),
                "n": len(mine),
            }
        line["crash"] = sum(bool(r.get("crash")) for r in cells.values())
        line["broken"] = sum(bool(r.get("broken")) for r in cells.values())
        line["worse_than_open"] = sum(bool(r.get("worse")) for r in cells.values())
        line["timeouts"] = sum(r.get("timeouts") or 0 for r in cells.values())
        out.append(line)
    return out


def main(argv=None):
    from arena_kit.cli import load_env
    from arena_kit.data import DataPackage
    from sellm.lab import invent, twins
    from sellm.lab import tournament as T

    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=3)
    ap.add_argument("--invented", type=int, default=120)
    ap.add_argument("--invent-seed", type=int, default=7)
    ap.add_argument("--workers", type=int, default=None)
    ap.add_argument("--only", default="", help="comma-separated variant names")
    ap.add_argument("--out", default="")
    a = ap.parse_args(argv)
    load_env()
    pkg = DataPackage(os.environ.get("ARENA_DATA", "data/package"))
    scenarios = twins.load() + invent.generate(a.invented, pkg, seed=a.invent_seed)
    names = [n for n in VARIANTS if not a.only or n in a.only.split(",")]
    out = Path(a.out or f"runs/lab/{time.strftime('%Y%m%d-%H%M')}-price-path")
    opts = {"clock": True, "mode": "parallel", "wave_cap_s": 480, "think_s": 2.0, "vary": False,
            "reader": "keywords", "supplier": "engine", "no_cache": False}  # fmt: skip
    run = T.Run(out, opts, scenarios, [], workers=a.workers, log=print)
    jobs = [(AGENT, VARIANTS[n], s.name, k) for n in names for s in scenarios for k in range(a.seeds)]
    run.log(f"price path: {len(names)} variants x {len(scenarios)} scenarios x {a.seeds} seeds = {len(jobs)} negotiations")
    t0 = time.time()
    rows = run.play(jobs)
    run.log(f"done in {time.time() - t0:.0f} s")
    run.close()
    for r in rows:
        r["variant"] = _name_of(r.get("knobs") or {})
    with gzip.open(out / "rows.jsonl.gz", "wt", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    summary = summarise(rows, a.seeds)
    (out / "summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    print(f"\n{'variant':<22} {'all':>7} {'diff':>7} {'se':>5} {'twins':>7} {'diff':>7} {'invent':>7} {'diff':>7} {'rel':>7} {'diff':>7} {'other':>7} {'diff':>7} {'nodeal':>6} {'rounds':>6}")
    for s in summary:
        cols = [s["variant"]]
        for g in ("all", "twins", "invented", "relationship", "other_goals"):
            x = s.get(g) or {}
            cols += [f"{x.get('mean', 0):.1f}", f"{x.get('diff') or 0:+.2f}"] + ([f"{x.get('se', 0):.2f}"] if g == "all" else [])
        allg = s.get("all") or {}
        cols += [str(allg.get("no_deal", 0)), f"{allg.get('rounds', 0):.1f}"]
        print(f"{cols[0]:<22} " + " ".join(f"{c:>7}" if i not in (2,) else f"{c:>5}" for i, c in enumerate(cols[1:], 1)))
    print(f"\nrun folder: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
