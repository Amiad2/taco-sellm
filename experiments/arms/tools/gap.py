# ruff: noqa  (analysis script of the Sat 21:15 review session: read-only against the arena, run from the repo root with the env of .env; see experiments/PRACTICE-ARMS.md)
"""For every finished practice session since T: where did we end vs. C_best, and what price on the SAME structure
would have reached C_best? Also: was any alternative sheet of the supplier cheaper by C than what we took?"""

import sys, json
from arena_kit.client import ArenaClient
from arena_kit.cost import total_cost, complete_offer
from arena_kit.docs import quote_terms, standard_terms

since = float(sys.argv[1])
only = sys.argv[2].split(",") if len(sys.argv) > 2 and sys.argv[2] != "-" else None
c = ArenaClient()
for r in sorted(c.sessions("practice"), key=lambda r: r["case_id"]):
    if r["created_at"] < since or r["status"] != "ended":
        continue
    cid = r["case_id"].split(":")[1]
    if only and cid not in only:
        continue
    sid = r["session_id"]
    st = c.session(sid)
    res = st.get("result") or {}
    case = st.get("case") or {}
    if not case:
        case = next(x for x in c.cases("practice") if x["case_id"] == r["case_id"])
    if not res.get("deal"):
        print(cid, "no deal", r["score"])
        continue
    sup = res["supplier_id"]
    th = c.thread(sid, sup)
    msgs = th.get("messages", th)
    # standard terms from the opening quote PDF
    std = {}
    for m in msgs:
        for att in m.get("attachments") or []:
            pass
    sess = st
    # reuse kit helper: standard_terms(events) works on messages with attachment texts -> fetch texts
    events = []
    for m in msgs:
        mm = dict(m)
        atts = []
        for att in m.get("attachments") or []:
            try:
                raw = c.attachment(sid, att["attachment_id"])
                from arena_kit.docs import read_document as attachment_text

                atts.append({**att, "text": attachment_text(att.get("name", ""), raw)})
            except Exception as e:
                atts.append(att)
        mm["attachments"] = atts
        events.append(mm)
    opening = next(m for m in events if m.get("term_sheets") and m.get("from") != "buyer")
    std0 = {}
    for att in opening.get("attachments") or []:
        if att.get("name", "").startswith("quote") and att.get("text"):
            std0 = quote_terms(att["text"]).get("standard", {})
    std = {**std0, **standard_terms(events)}
    deal = res["terms"]
    c_deal = res["c_deal"]
    c_best = res["c_best"]
    c_open = res["c_open"]
    # price on the deal's structure that would hit C_best
    s = {k: v for k, v in deal.items() if k != "unit_price"}
    c0 = total_cost(case, {**s, "unit_price": 0.0}, std)
    c1 = total_cost(case, {**s, "unit_price": 1.0}, std)
    p_best = (c_best - c0) / (c1 - c0)
    # every supplier sheet seen, priced by C (not just standing)
    seen = []
    for m in events:
        if m.get("from") == "buyer":
            continue
        for sh in m.get("term_sheets") or []:
            t = complete_offer(case, {**std, **{k: v for k, v in sh["terms"].items() if v is not None}})
            seen.append((total_cost(case, t, std), t))
    best_seen = min(seen, key=lambda x: x[0])
    print(
        f"{cid}: score {r['score']:.3f} | deal P={deal['unit_price']} pd={deal.get('payment_days')} mo={deal.get('contract_months')} | "
        f"price on that structure reaching C_best: {p_best:.2f} ({100 * (deal['unit_price'] / p_best - 1):+.1f}% above) | "
        f"range C_open-C_best {c_open - c_best:,.0f} ({100 * (c_open - c_best) / c_open:.1f}% of C)"
    )
    mine = total_cost(case, complete_offer(case, {**std, **deal}), std)
    if best_seen[0] < mine - 1:
        t = best_seen[1]
        print(
            f"     !! a cheaper sheet was on the table: C {best_seen[0]:,.0f} vs deal {mine:,.0f} (saves {mine - best_seen[0]:,.0f} = {100 * (mine - best_seen[0]) / (c_open - c_best):.1f}% of the score range): "
            f"P={t['unit_price']} pd={t.get('payment_days')} mo={t.get('contract_months')} vol={t.get('volume_per_year')} lt={t.get('lead_time_days')}"
        )
