"""Targeted tests of the persistence layer (sellm/endgame.py) on real suppliers, one session at a time.

    uv run python experiments/persistence.py --cases P01 P11 --knobs past_target=true creep=0.25 --label "E1 creep 0.25"

Practice cases cost quota (one session each); D01 and D02 are free. Each row is appended to
experiments/results/2026-10-10-persistence.json; run scripts/pull-runs afterwards (the label is set here).
"""

import argparse
import importlib.util
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "experiments" / "results" / "2026-10-10-persistence.json"
LABELS = ROOT / "runs" / "labels.json"


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--cases", nargs="+", required=True)
    ap.add_argument("--knobs", nargs="*", default=[], help="key=value, e.g. past_target=true creep=0.25")
    ap.add_argument("--label", required=True)
    args = ap.parse_args()
    from arena_kit.cli import load_env, pull_first

    load_env()
    pull_first()  # never play on outdated code
    from arena_kit.client import ArenaClient
    from arena_kit.data import DataPackage
    from sellm.endgame import make_agent

    spec = importlib.util.spec_from_file_location("ab_sandbox", ROOT / "experiments" / "ab_sandbox.py")
    ab = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ab)
    knobs = {}
    for item in args.knobs:
        key, _, value = item.partition("=")
        try:
            knobs[key] = json.loads(value)
        except ValueError:
            knobs[key] = value
    package = DataPackage(os.environ.get("ARENA_DATA", "data/package"))
    package.lookup("")
    client = ArenaClient()
    rows = json.loads(OUT.read_text(encoding="utf-8")) if OUT.is_file() else []
    for case in args.cases:
        row = ab.play_case(client, f"case:{case.split(':')[-1]}", make_agent(package, **knobs))
        row.update(label=args.label, knobs=knobs)
        rows.append(row)
        OUT.write_text(json.dumps(rows, indent=1, default=str), encoding="utf-8")
        labels = json.loads(LABELS.read_text(encoding="utf-8")) if LABELS.is_file() else {}
        labels[row["session_id"]] = f"PERSIST {args.label} {json.dumps(knobs, sort_keys=True)}"
        LABELS.write_text(json.dumps(labels, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        threads = []
        for sid, t in (row.get("threads") or {}).items():
            ours = [p[0] if p else None for p in t["our_prices"]]
            threads.append(f"{sid.split(':')[-1]} theirs {t['their_prices']} ours {ours} {t['status']}")
        shown = ("unit_price", "payment_days", "contract_months", "effective_date")
        terms = {k: v for k, v in (row.get("terms") or {}).items() if k in shown}
        head = f"{case} score {row.get('score'):.3f} {row.get('end_reason')} {terms}"
        print(f"{head} | {'; '.join(threads)} | {row['session_id']} {row.get('notes') or ''}", flush=True)


if __name__ == "__main__":
    main()
