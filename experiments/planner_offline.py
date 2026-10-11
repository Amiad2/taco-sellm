# ruff: noqa: E501
"""Would the model have found the trade without a test session? `sellm.planner` over the saved
openings of every played case, several times each (no arena session, only LLM calls).

    SELLM_MODEL=gpt-6-sol uv run python experiments/planner_offline.py --repeat 3

Rows: experiments/results/2026-10-11-planner-offline.json. Reading: experiments/LLM-PLANNER.md.
"""

import argparse
import glob
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "experiments" / "results" / "2026-10-11-planner-offline.json"


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument(
        "--cases",
        nargs="*",
        default=["P01", "P02", "P03", "P04", "P05", "P07", "P08", "P10", "P11", "P18", "D01", "D02"],
    )
    ap.add_argument("--repeat", type=int, default=3)
    args = ap.parse_args()
    from arena_kit.cli import load_env

    load_env()
    from sellm import llm, planner
    from sellm.intel import dossier
    from sellm.negotiator import Thread

    jobs = []
    for name in args.cases:
        files = sorted(glob.glob(str(ROOT / "runs" / "*" / name / "*.json")))
        if not files:
            continue
        record = json.loads(Path(files[-1]).read_text(encoding="utf-8"))
        case = record["case"]
        openings = {s: t["messages"][:1] for s, t in record["threads"].items()}
        for sid, events in openings.items():
            view = Thread(case, sid, events)
            quoted = view.filled(view.opening["term_sheets"][0]["terms"])
            found = dossier(sid, case.get("parts") or [], case, openings)
            for k in range(args.repeat):
                jobs.append((name, sid, k, case, events[0], found, quoted))

    def run(job):
        name, sid, k, case, opening, found, quoted = job
        try:
            p = planner.plan(case, opening, found, quoted, timeout_s=40.0)
        except llm.LLMError as e:
            p = {"error": str(e), "wants": [], "dropped": []}
        return {"case": name, "supplier": sid, "run": k, "quoted": quoted, **p}

    with ThreadPoolExecutor(max_workers=6) as pool:
        rows = list(pool.map(run, jobs))
    OUT.write_text(json.dumps(rows, indent=1, default=str), encoding="utf-8")
    for name in args.cases:
        for sid in sorted({r["supplier"] for r in rows if r["case"] == name}):
            mine = [r for r in rows if r["case"] == name and r["supplier"] == sid]
            print(
                f"\n{name} {sid}  quoted { ({f: (x if not isinstance(x, dict) else 'clause') for f, x in mine[0]['quoted'].items() if f != 'unit_price'}) }"
            )
            for r in mine:
                wants = (
                    "; ".join(
                        f"{w['field']}={(w['value'] if not isinstance(w['value'], dict) else 'clause db' + str(w['value'].get('deadband_pct')))} [{w['evidence'][:70]}]"
                        for w in r["wants"]
                    )
                    or "-"
                )
                dropped = "; ".join(f"{d.get('field')}:{d.get('why')}" for d in r.get("dropped") or [])
                print(
                    f"   run {r['run']}: {wants}"
                    + (f"  | dropped {dropped}" if dropped else "")
                    + (
                        f"  | {r.get('error')}"
                        if r.get("error")
                        else f"  | {r.get('seconds')} s | {r.get('note', '')[:110]}"
                    )
                )


if __name__ == "__main__":
    main()
