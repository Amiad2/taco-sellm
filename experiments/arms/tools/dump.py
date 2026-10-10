# ruff: noqa  (analysis script of the Sat 21:15 review session: read-only against the arena, run from the repo root with the env of .env; see experiments/PRACTICE-ARMS.md)
"""Compact view of practice sessions straight from the arena API (read-only)."""
import sys, datetime, json
from arena_kit.client import ArenaClient
c = ArenaClient()
KEYS = ("unit_price","payment_days","contract_months","volume_per_year","lead_time_days","effective_date","index_clause","ppm_commitment","chargeback_eur_per_complaint")
def t(terms):
    out=[]
    for k in KEYS:
        if k in terms and terms[k] is not None:
            v=terms[k]
            if isinstance(v,dict): v="idx:"+str(v.get("series"))
            out.append(f"{k.replace('_per_year','').replace('_eur_per_complaint','').replace('contract_months','mo').replace('payment_days','pd').replace('unit_price','P').replace('lead_time_days','lt').replace('effective_date','from').replace('volume','vol')}={v}")
    return " ".join(out)
def main(since, cases=None, bodies=False):
    rows = [r for r in c.sessions("practice") if r["created_at"] >= since and (not cases or r["case_id"].split(":")[1] in cases)]
    for r in sorted(rows, key=lambda r: r["case_id"]):
        sid = r["session_id"]
        st = c.session(sid)
        res = st.get("result") or {}
        print("="*110)
        print(r["case_id"], r["status"], "score", None if r["score"] is None else round(r["score"],3), "deal", res.get("terms") and t(res["terms"]), "| c_deal", res.get("c_deal"), "c_open", res.get("c_open"), "c_best", res.get("c_best"))
        for s in (st.get("threads") or {}):
            th = c.thread(sid, s)
            msgs = th.get("messages", th) if isinstance(th, dict) else th
            print(" --", s)
            for m in msgs:
                who = "US " if m.get("from") == "buyer" else "SUP"
                sheets = [t(x["terms"]) for x in m.get("term_sheets") or []]
                extra = ""
                if m.get("action"): extra = f" ACTION {m['action']}"
                cr = m.get("claim_results")
                print(f"   {who} {m.get('status') or ''} {' || '.join(sheets)}{extra} {('claims='+json.dumps(cr)) if cr else ''}")
                if bodies and m.get("body"):
                    print("       > " + " ".join((m["body"] or "").split())[:420])
if __name__ == "__main__":
    since = float(sys.argv[1]); cases = sys.argv[2].split(",") if len(sys.argv) > 2 and sys.argv[2] != "-" else None
    main(since, cases, bodies=("-b" in sys.argv))
