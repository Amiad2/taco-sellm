# ruff: noqa  (analysis script of the Sat 21:15 review session: read-only against the arena, run from the repo root with the env of .env; see experiments/PRACTICE-ARMS.md)
"""Replay a variant over recorded arena sessions: where would it have sent something different?"""
import sys, os, json
sys.path.insert(0, ".")
from arena_kit.client import ArenaClient
from arena_kit.data import DataPackage
from arena_kit.docs import read_document as attachment_text
from sellm import variants
since, until, variant = float(sys.argv[1]), float(sys.argv[2]), sys.argv[3]
c = ArenaClient(); pkg = DataPackage(os.environ["ARENA_DATA"]); pkg.lookup("")
for r in sorted(c.sessions("practice"), key=lambda r: r["case_id"]):
    if not (since <= r["created_at"] <= until) or r["status"] != "ended": continue
    st = c.session(r["session_id"]); case = st.get("case") or next(x for x in c.cases("practice") if x["case_id"] == r["case_id"])
    threads = {}
    for s in st.get("threads") or {}:
        th = c.thread(r["session_id"], s); msgs = th.get("messages", th)
        out = []
        for m in msgs:
            mm = dict(m); atts = []
            for att in m.get("attachments") or []:
                try:
                    atts.append({**att, "text": attachment_text(att.get("name", ""), c.attachment(r["session_id"], att["attachment_id"]))})
                except Exception:
                    atts.append(att)
            mm["attachments"] = atts; out.append(mm)
        threads[s] = out
    diffs = []
    for sid, msgs in threads.items():
        for i, m in enumerate(msgs):
            if m.get("from") != "buyer" or m.get("action"): continue
            before = {s: (ms[:i] if s == sid else ms[:i]) for s, ms in threads.items()}
            # other threads: approximate with full history up to the same time is unknowable; use their full lists up to the same index
            others = {s: ms[:min(len(ms), i)] for s, ms in threads.items()}
            others[sid] = msgs[:i]
            try:
                d = getattr(variants, variant)(pkg).decide(case, others, focus=sid)
            except Exception as e:
                diffs.append((sid, i, "ERR " + repr(e)[:80])); continue
            mine = d["message"]
            same_sheets = [x["terms"] for x in mine.get("term_sheets", [])] == [x["terms"] for x in m.get("term_sheets", [])]
            same_body = (mine.get("body") or "").strip() == (m.get("body") or "").strip()
            if not (same_sheets and same_body):
                diffs.append((sid, i, "sheets differ" if not same_sheets else "body differs"))
    print(r["case_id"], "IDENTICAL on every recorded move" if not diffs else f"DIFFERS at {diffs[:3]}")
