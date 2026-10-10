"""`uv run python -m sellm.lab <command>`

calibrate                  rebuild sellm/lab/twins.json from runs/ (after new sessions were pulled)
twins                      list the twins: case, suppliers, floor, C_best
backtest [--fit]           replay our real sessions into the twins; --fit tunes their dynamics
                           and writes them to sellm/lab/twins.json
play <case> [--agent naive|llm] [--seed N] [-v]   one negotiation against a twin, printed
"""

import argparse
import json
import logging
import os

from arena_kit.cli import load_env
from arena_kit.data import DataPackage
from arena_kit.play import play

from . import twins
from .table import LocalTable


def package():
    return DataPackage(os.environ.get("ARENA_DATA", "data/package"))


def agent_for(name, pkg):
    from .strategies import registry

    return registry(pkg)[name]()


def tournament(a):
    import gzip
    import time
    from pathlib import Path

    from . import tournament as t

    stamp = time.strftime("%Y%m%d-%H%M")
    out = Path("runs/lab") / f"{stamp}-{a.cmd}{'-' + a.label if a.label else ''}"
    t0 = time.time()
    if a.cmd == "compare":
        rows = t.compare(a.strategies, a.invented, a.seeds, a.workers, a.invent_seed)
        title = f"Lab compare {stamp}: {' vs '.join(a.strategies)}"
        min_scen = 0
    else:
        rows = t.search(a.minutes, a.invented, a.start, a.seeds, a.workers, a.invent_seed, a.seed)
        title = f"Lab search {stamp}: {a.minutes:g} min, {a.start} random variants to start"
        min_scen = len({r["scenario"] for r in rows})
    out.mkdir(parents=True, exist_ok=True)
    text = t.report(rows, title, min_scenarios=min_scen)
    text += f"\nRun: `uv run python -m sellm.lab {' '.join(__import__('sys').argv[1:])}`, {time.time() - t0:.0f} s.\n"
    (out / "report.md").write_text(text, encoding="utf-8")
    with gzip.open(out / "rows.jsonl.gz", "wt", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps({k: v for k, v in r.items() if k != "trace"}, default=str) + "\n")
    best = sorted(t.summarise(rows, min_scen).values(), key=lambda x: -x["mean"])[:10]
    (out / "best.json").write_text(json.dumps(best, indent=1, default=str) + "\n", encoding="utf-8")
    print(text)
    print(f"wrote {out}/")


def show(result, table):
    for sid, t in table.threads.items():
        print(f"--- {sid}")
        for m in t.messages:
            sheets = [s["terms"].get("unit_price") for s in m.get("term_sheets") or []]
            print(f"  supplier {m['status']:<12} {sheets}  {m['body'][:160]!r}")
    keep = ("end_reason", "deal", "supplier_id", "terms", "c_open", "c_deal", "c_best", "score")
    print(json.dumps({k: result.get(k) for k in keep}, indent=1, default=str))


def main(argv=None):
    load_env()
    ap = argparse.ArgumentParser(prog="python -m sellm.lab")
    ap.add_argument("-v", "--verbose", action="store_true")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("calibrate")
    sub.add_parser("twins")
    b = sub.add_parser("backtest")
    b.add_argument("--fit", action="store_true")
    b.add_argument("--write", action="store_true", help="write runs/lab/BACKTEST.md")
    p = sub.add_parser("play")
    p.add_argument("case")
    p.add_argument("--agent", default="naive", choices=["naive", "llm", "calc"])
    p.add_argument("--seed", type=int, default=0)
    for mode in ("compare", "search"):
        t = sub.add_parser(mode)
        if mode == "compare":
            t.add_argument("strategies", nargs="+")
        else:
            t.add_argument("--minutes", type=float, default=10)
            t.add_argument("--start", type=int, default=64, help="random variants in the first round")
            t.add_argument("--seed", type=int, default=0)
        t.add_argument("--invented", type=int, default=150, help="invented scenarios next to the twins")
        t.add_argument("--invent-seed", type=int, default=1)
        t.add_argument("--seeds", type=int, default=2, help="runs per strategy and scenario")
        t.add_argument("--workers", type=int, default=None)
        t.add_argument("--label", default="")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO if a.verbose else logging.WARNING, format="%(message)s")

    if a.cmd == "calibrate":
        scenarios = twins.build(package())
        twins.save(scenarios)
        for s in scenarios:
            print(s.name, s.notes, {k: round(p.full_cost, 2) for k, p in s.personas.items()})
        print(f"wrote {twins.CACHE}")
    elif a.cmd == "twins":
        for s in twins.load():
            floors = {k: round(p.full_cost, 2) for k, p in s.personas.items()}
            print(f"{s.name:5} {s.case['type']:15} {s.case['buyer']['category_goal']:14} floors {floors}  {s.notes}")
    elif a.cmd == "backtest":
        from . import backtest

        pkg, scenarios = package(), twins.load()
        if a.fit:
            _, per = backtest.fit(scenarios, pkg.facts)
            for s in scenarios:
                for p in s.personas.values():
                    for k, v in per[s.name].items():
                        setattr(p, k, v)
            twins.save(scenarios)
            print(f"wrote {twins.CACHE}")
        rows = backtest.evaluate(scenarios, pkg.facts)
        print(backtest.report(rows))
        if a.write:
            backtest.write_report(scenarios, rows, "runs/lab/BACKTEST.md")
            print("wrote runs/lab/BACKTEST.md")
    elif a.cmd in ("compare", "search"):
        tournament(a)
    elif a.cmd == "play":
        pkg = package()
        name = a.case.split(":")[-1]
        scenario = next(s for s in twins.load() if s.name == name)
        table = LocalTable(scenario, pkg.facts, seed=a.seed)
        result = play(table, scenario.case["case_id"], agent_for(a.agent, pkg))
        show(result, table)


if __name__ == "__main__":
    main()
