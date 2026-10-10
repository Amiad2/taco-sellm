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
    from arena_kit.agents import LLMAgent, NaiveAgent, llm_from_env

    if name == "naive":
        return NaiveAgent()
    return LLMAgent(llm_from_env(), pkg)


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
    p = sub.add_parser("play")
    p.add_argument("case")
    p.add_argument("--agent", default="naive", choices=["naive", "llm"])
    p.add_argument("--seed", type=int, default=0)
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
        print(backtest.report(backtest.evaluate(scenarios, pkg.facts)))
    elif a.cmd == "play":
        pkg = package()
        name = a.case.split(":")[-1]
        scenario = next(s for s in twins.load() if s.name == name)
        table = LocalTable(scenario, pkg.facts, seed=a.seed)
        result = play(table, scenario.case["case_id"], agent_for(a.agent, pkg))
        show(result, table)


if __name__ == "__main__":
    main()
