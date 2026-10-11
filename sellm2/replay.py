# ruff: noqa: E501  (long sentences and messages)
"""Offline diagnosis over the sessions saved in runs/: at every recorded state, what would sellm2
send, and how does it differ from what was sent? Practice suppliers answer identical e-mails
identically, so up to the first difference a session's outcome is known; after it, only a session
tells. No network, no quota.

    python -m sellm2 replay [--label TEXT] [--cases P01 P05 ...] [--knobs '{"lever_prices": false}']
"""

import glob
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sessions(label=None, cases=None, sets=("practice", "sandbox")):
    out = []
    for s in sets:
        for f in sorted(glob.glob(str(ROOT / "runs" / s / "*" / "*.json"))):
            try:
                r = json.loads(Path(f).read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if not isinstance(r, dict) or "case" not in r:
                continue
            if label and label not in (r.get("label") or ""):
                continue
            if cases and r["case_id"].split(":")[-1] not in cases:
                continue
            out.append(r)
    return out


def summary(message):
    """(kind, [(price, structure)]) of a buyer message."""
    if message.get("action"):
        return (message["action"]["type"], [])
    sheets = [s["terms"] for s in message.get("term_sheets") or []]
    if not sheets:
        return ("hold", [])
    return ("ask", [(t.get("unit_price"), tuple(sorted((k, repr(v)) for k, v in t.items() if k != "unit_price"))) for t in sheets])


def replay(record, new_agent):
    """[(sid, index, recorded, ours, same_body)] for every buyer message of the session, in each
    thread with the other threads at their opening (exact for single-supplier cases)."""
    case, threads = record["case"], record["threads"]
    openings = {s: [t["messages"][0]] for s, t in threads.items()}
    out = []
    for sid, t in threads.items():
        msgs = t["messages"]
        for i, m in enumerate(msgs):
            if m.get("from") != "buyer" or i == 0:
                continue
            state = {**openings, sid: msgs[:i]}
            d = new_agent().decide(case, state, focus=sid if len(threads) > 1 else None)
            mine = d["message"]
            if d["supplier_id"] != sid:
                mine = {"action": {"type": f"other:{d['supplier_id']}"}}
            out.append((sid, i, summary(m), summary(mine), (mine.get("body") or "").strip() == (m.get("body") or "").strip()))
    return out


def report(records, new_agent, show=3):
    lines = []
    for r in records:
        rows = replay(r, new_agent)
        score = ((r.get("state") or {}).get("result") or {}).get("score")
        first = next((row for row in rows if row[2] != row[3]), None)
        head = f"{r['case_id']:9} {score if score is None else round(score, 3)!s:6} {r['session_id'][:8]} {(r.get('label') or '')[:50]}"
        if first is None:
            same_text = all(row[4] for row in rows)
            lines.append(f"{head}  SAME MOVES ({len(rows)}){'' if same_text else ', other wording'}")
            continue
        lines.append(f"{head}  DIFFERS at {first[0]} message {first[1]}")
        for sid, i, rec, ours, _ in [row for row in rows if row[2] != row[3]][:show]:
            lines.append(f"      {sid} #{i}: sent {rec[0]} {[(p, dict(s)) for p, s in rec[1]][:2]}")
            lines.append(f"      {'':{len(sid)}}     ours {ours[0]} {[(p, dict(s)) for p, s in ours[1]][:2]}")
    return "\n".join(lines)
