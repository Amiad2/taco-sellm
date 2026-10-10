"""Arena check of the lab's price-path findings (experiments/PRICE-PATH.md), one session at a time.

    uv run python -m experiments.price_path_arena --variant horizon_6 --cases P07 P11 P18

The agent is `experiments.price_path.make` (what `--agent sellm` plays plus the variant's switches;
the oracle reads the twins' calibrated floors). Practice cases cost quota (one session each), D01 and
D02 are free. Rows go to experiments/results/2026-10-11-price-path.json, labels to runs/labels.json;
run scripts/pull-runs afterwards.
"""

import argparse
import importlib.util
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "experiments" / "results" / "2026-10-11-price-path.json"
LABELS = ROOT / "runs" / "labels.json"


def main():
    from experiments.price_path import VARIANTS, make

    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--variant", required=True, choices=sorted(VARIANTS))
    ap.add_argument("--cases", nargs="+", required=True)
    args = ap.parse_args()
    from arena_kit.cli import load_env, pull_first

    load_env()
    pull_first()  # never play on outdated code
    from arena_kit.client import ArenaClient
    from arena_kit.data import DataPackage

    spec = importlib.util.spec_from_file_location("ab_sandbox", ROOT / "experiments" / "ab_sandbox.py")
    ab = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ab)
    package = DataPackage(os.environ.get("ARENA_DATA", "data/package"))
    package.lookup("")
    client = ArenaClient()
    knobs = VARIANTS[args.variant]
    rows = json.loads(OUT.read_text(encoding="utf-8")) if OUT.is_file() else []
    for case in args.cases:
        row = ab.play_case(client, f"case:{case.split(':')[-1]}", make(package, **json.loads(json.dumps(knobs))))
        row.update(label=args.variant, knobs=knobs)
        rows.append(row)
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(rows, indent=1, default=str), encoding="utf-8")
        labels = json.loads(LABELS.read_text(encoding="utf-8")) if LABELS.is_file() else {}
        note = "(Omar, sellm.agent + test switches)"
        labels[row["session_id"]] = f"PRICE-PATH {args.variant} {json.dumps(knobs, sort_keys=True)} {note}"
        LABELS.write_text(json.dumps(labels, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        threads = []
        for sid, t in (row.get("threads") or {}).items():
            ours = [p[0] if p else None for p in t["our_prices"]]
            threads.append(f"{sid.split(':')[-1]} theirs {t['their_prices']} ours {ours} {t['status']}")
        score = row.get("score")
        head = f"{case} {args.variant} score {score if score is None else round(score, 3)} {row.get('end_reason')}"
        print(f"{head} | {'; '.join(threads)} | {row['session_id']} {row.get('notes') or ''}", flush=True)


if __name__ == "__main__":
    main()
