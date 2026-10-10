# ruff: noqa  (analysis script of the Sat 21:15 review session: read-only against the arena, run from the repo root with the env of .env; see experiments/PRACTICE-ARMS.md)
"""Every cited fact and what the arena said: per session in a time window (epoch since), straight from the API."""
import sys, re, collections
from arena_kit.client import ArenaClient
from arena_kit.agents.llm import ID_RE
c = ArenaClient()
since = float(sys.argv[1]); until = float(sys.argv[2]) if len(sys.argv) > 2 else 9e12
tally = collections.Counter()
for r in sorted(c.sessions("practice"), key=lambda r: (r["case_id"], r["created_at"])):
    if not (since <= r["created_at"] <= until) or r["status"] != "ended": continue
    st = c.session(r["session_id"])
    for s in st.get("threads") or {}:
        th = c.thread(r["session_id"], s); msgs = th.get("messages", th)
        pending = None
        for m in msgs:
            if m.get("from") == "buyer":
                body = m.get("body") or ""
                # split into sentences that carry an ID
                pending = [x.strip() for x in re.split(r"(?<=[.!?])\s+(?=[A-Z])", body) if ID_RE.search(x)]
            else:
                cr = m.get("claim_results") or []
                if pending is not None:
                    for i, res in enumerate(cr):
                        kind = None
                        sent = pending[res["index"]] if res.get("index") is not None and res["index"] < len(pending) else "?"
                        k = ID_RE.search(sent); kind = k.group(0).split(":")[0] if k else "?"
                        tally[(kind, res["result"])] += 1
                        print(f"{r['case_id'][5:]:4} {kind:6} {res['result']:13} {sent[:150]}")
                    pending = None
print()
for (k, res), n in sorted(tally.items()):
    print(f"{k:6} {res:13} {n}")
