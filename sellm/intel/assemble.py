"""Assemble a supplier's dossier from the package (docs/PLAN.md section 10); signals come from signals.py."""

import re

from . import derive
from .extract import split_ids
from .schema import empty_dossier, empty_part

MARKET_TOPICS = (
    (re.compile(r"\bcopper\b", re.I), {"electrical"}),
    (re.compile(r"\b(power|energy|electricity)\b", re.I), None),
    (re.compile(r"\bcastings?\b", re.I), {"castings"}),
    (re.compile(r"1\.4404|\balloy\b|\bstainless\b", re.I), {"raw material", "machined parts"}),
    (re.compile(r"\bsteel\b", re.I), {"raw material", "machined parts", "sheet metal", "C-parts"}),
    (re.compile(r"\b(electronic|boards?|chips?)\b", re.I), {"electrical"}),
    (re.compile(r"\b(labour|labor|wages?)\b", re.I), None),
)


def build_part(src, sid, pid, country):
    part, warnings = empty_part(), []
    row = src.part(pid) or {}
    if not row:
        warnings.append(f"{pid}: not in the material master")
    for k in ("description", "category", "material_group", "grade", "uom", "planned_lead_time_days", "abc_class"):
        part[k] = row.get(k)
    part["price_unit"] = int(row["price_unit"]) if row.get("price_unit") is not None else None
    so = src.sourcing_row(sid, pid)
    if so:
        part["sourcing"] = {k: so.get(k) for k in ("status", "quota_pct", "approved_since", "tooling_owner")}
    price = src.current_price(sid, pid)
    if price:
        part["current_price"] = {
            "price": derive.r(price["price"], 2),
            "price_unit": int(price.get("price_unit") or 1),
            "valid_from": price.get("valid_from"),
            "valid_to": price.get("valid_to"),
            "event_id": price.get("event_id"),
            "basis": price.get("basis"),
        }
    part["history"] = derive.history_summary(src.history(sid, pid))
    sc = derive.pick_should_cost(src.should_cost(pid), sid)
    if sc and part["price_unit"] and sc["price_unit"] != part["price_unit"]:
        warnings.append(f"{pid}: should-cost per {sc['price_unit']}, part priced per {part['price_unit']}")
    part["should_cost"] = sc
    part["floor_estimate"] = derive.floor_estimate(sc, country, part["price_unit"])
    part["price_to_should_cost"] = derive.price_to_should_cost(part["current_price"], sc)
    part["drivers"] = derive.drivers(src.drivers(pid), src.series)
    part["forecast"] = derive.forecast(*src.forecast(pid), src.facts)
    part["alternatives"] = derive.alternatives(src.other_sources(sid, pid), src.rival_quotes(sid, pid))
    return part, warnings


def identity(row):
    certs = [c.strip() for c in (row.get("certifications") or "").split(";") if c.strip()]
    out = {
        "name": row.get("name"),
        "country": row.get("country"),
        "category": row.get("category"),
        "legal_form": row.get("legal_form"),
        "founded": row.get("founded"),
        "owner_type": row.get("owner_type"),
        "group_parent": row.get("group_parent"),
        "staff": row.get("staff"),
        "turnover_eur": row.get("turnover_eur"),
        "turnover_band": row.get("turnover_band"),
        "equity_ratio_pct": row.get("equity_ratio_pct"),
        "credit_index": row.get("credit_index"),
        "credit_index_12m_ago": row.get("credit_index_12m_ago"),
        "vda63_grade": row.get("vda63_grade"),
        "certifications": certs,
        "abc_class": row.get("abc_class"),
        "supplier_since": row.get("created"),
        "blocked": bool(row.get("blocked")),
    }
    out["turnover_estimated"] = derive.turnover(out)[1]
    return out


def contract(src, sid):
    row = src.contract(sid)
    if not row:
        return None
    return {
        "id": row["id"],
        "valid_from": row.get("valid_from"),
        "valid_to": row.get("valid_to"),
        "notice_days": row.get("notice_days"),
        "price_basis": row.get("price_basis"),
        "payment_days": row.get("payment_days"),
        "incoterm": row.get("incoterm"),
        "index_clauses": [
            {k: c.get(k) for k in ("id", "series", "material_share", "deadband_pct")}
            for c in src.index_clauses(row["id"])
        ],
    }


def documents(rows):
    keys = ("id", "date", "kind", "subject", "author", "asked_pct", "asked_price", "effective_date", "notice_days")
    out = [  # an empty cell (rows of the Sunday release come from CSV) is no value
        {
            **{k: (None if row.get(k) == "" else row.get(k)) for k in keys},
            "part_ids": split_ids(row.get("part_ids")),
            "text": row["text"],
        }
        for row in rows
    ]
    return sorted(out, key=lambda d: (d["date"] or "", d["id"]))


def news(rows):
    out = [
        {
            "id": n["id"],
            "date": n.get("date"),
            "topic": n.get("topic"),
            "headline": n.get("headline"),
            "body": n.get("body"),
            "source": n.get("source"),
            "noise": n.get("topic") == "noise",
        }
        for n in rows
    ]
    return sorted(out, key=lambda n: (n["date"] or "", n["id"]))


def market_news(rows, categories):
    out = []
    for n in rows:
        text = f"{n.get('headline') or ''} {n.get('body') or ''}"
        if any(rx.search(text) and (cats is None or cats & categories) for rx, cats in MARKET_TOPICS):
            out.append({"id": n["id"], "date": n.get("date"), "headline": n.get("headline"), "body": n.get("body")})
    return sorted(out, key=lambda n: (n["date"] or "", n["id"]))


def own_quotes(rows):
    keys = ("part_id", "unit_price", "price_unit", "lead_time_days", "payment_days", "incoterm", "remarks")
    out = [{"quote_id": q["id"], "date": q.get("quote_date"), **{k: q.get(k) for k in keys}} for q in rows]
    return sorted(out, key=lambda q: (q["date"] or "", q["quote_id"]))


def build_supplier(src, sid):
    """Everything the package says about one supplier, before signals and the derived economics."""
    d = empty_dossier(sid)
    row = src.supplier(sid)
    d["built_from"] = {
        "package": src.version,
        "facts_sha256": src.facts_sha256,
        "sunday_release": src.pkg.release is not None,
        "case_id": None,
    }
    if row is None:
        d["warnings"].append(f"{sid}: not in the vendor master")
        return d
    d["coverage"] = "full" if row.get("detail") == "full" else "thin"
    d["identity"] = identity(row)
    d["standard_terms"] = {
        "payment_days": row.get("payment_days"),
        "skonto_days": row.get("skonto_days"),
        "skonto_pct": row.get("skonto_pct"),
        "incoterm": row.get("incoterm"),
        "lead_time_days": row.get("standard_lead_time_days"),
        "source": "vendor_master",
    }
    for so in src.sourcing(sid):
        part, warnings = build_part(src, sid, so["part_id"], row.get("country"))
        d["parts"][so["part_id"]] = part
        d["warnings"] += warnings
    d["contract"] = contract(src, sid)
    d["performance"] = derive.performance(
        src.scorecards(sid), src.complaints(sid, derive.WINDOW_START, derive.DATA_TODAY)
    )
    d["documents"] = documents(src.documents(sid))
    d["news"] = news(src.news(sid))
    categories = {row.get("category")} | {p["category"] for p in d["parts"].values() if p["category"]}
    d["market_news"] = market_news(src.market_news(), categories)
    d["own_quotes"] = own_quotes(src.own_quotes(sid))
    spend = {s["fiscal_year"]: derive.r(s["spend"], 2) for s in src.spend(sid)}
    pay = src.payments(sid) or {}
    ec = d["economics"]
    ec["our_spend_eur"] = spend
    ec["our_share_of_turnover_pct"] = derive.share_of_turnover(spend, d["identity"])
    ec["we_pay_late_days"] = derive.r(pay.get("late"), 1) if pay.get("n") else None
    if d["standard_terms"]["skonto_pct"] and pay.get("n"):
        ec["discount_taken_share_pct"] = derive.r(pay["discount"] * 100, 2)
    return d
