# ruff: noqa: E501  (long lines in a research script)
"""Does today's `--agent sellm` (sellm.agent.KNOBS) send, case by case, exactly the e-mails of the session
that measured its rules? Practice suppliers answer identical e-mails identically, so where it does, that
session's score is its score; where it does not, the case needs a session.

    uv run python -m experiments.combined_replay

Reference per case: the newest session whose label names one of the versions below (newest first).
"""

import glob
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from experiments.structure_args import states, summary  # noqa: E402

# labels of sessions played by the rules now in KNOBS, the most specific first
REFERENCES = [
    "OMAR E2 {\"idx_recent\": 2.0} sellm.agent omars_branch@c8c0eb5",  # P18 (E2 = E2g on 70740)
    "jonathans_branch@67001e7",  # the full run with the clause offer (P02 and the nine others)
    "@7a49c38",
]


def main():
    from arena_kit.data import DataPackage
    from sellm.agent import make_agent

    package = DataPackage(os.environ.get("ARENA_DATA", "data/package"))
    records = [json.loads(Path(p).read_text(encoding="utf-8")) for p in sorted(glob.glob(str(ROOT / "runs" / "practice" / "*" / "*.json")))]
    total, open_cases = 0.0, []
    for cid in sorted({r["case_id"] for r in records}):
        found = None
        for ref in REFERENCES:
            cands = [r for r in records if r["case_id"] == cid and ref in (r.get("label") or "") and "no hedge guard" not in r["label"]]
            if cid == "case:P05":
                cands = [r for r in records if r["case_id"] == cid and ref in (r.get("label") or "")]
            if cands:
                found = cands[-1]
                break
        if not found:
            print(f"{cid}: no reference session")
            continue
        case, agent, diff = found["case"], make_agent(package), None
        for sid, threads in states(found):
            a = agent.decide(case, threads, None if len(threads) > 1 else None)
            ours = next((m for m in found["threads"][sid]["messages"][len(threads[sid]):] if m.get("from") == "buyer" or m.get("action")), None)
            if len(threads) > 1:
                break  # an RFQ's order of threads is the runner's: not replayed here
            if ours is None:
                break
            sent = {k: ours.get(k) for k in ("body", "term_sheets") if ours.get(k) is not None}
            got = a["message"]
            if ours.get("action") or got.get("action"):
                same = (ours.get("action") or {}).get("type") == (got.get("action") or {}).get("type")
            else:
                same = got.get("body") == sent.get("body") and [s["terms"] for s in got.get("term_sheets") or []] == [s["terms"] for s in sent.get("term_sheets") or []]
            if not same:
                diff = (sid, summary(a))
                break
        score = (found["state"].get("result") or {}).get("score") or 0.0
        label = (found.get("label") or "")[:60]
        if diff is None and len(found["threads"]) == 1:
            total += score
            print(f"{cid}: same e-mails as '{label}' -> {score:.3f}")
        else:
            open_cases.append(cid)
            print(f"{cid}: needs a session (reference '{label}' {score:.3f}; first difference {diff})")
    print(f"sum of replayed scores {total:.3f}; not replayed: {open_cases}")


if __name__ == "__main__":
    main()
