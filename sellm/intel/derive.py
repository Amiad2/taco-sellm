"""The rules that turn package rows into the dossier's derived fields (docs/PLAN.md section 10)."""

import re

DATA_TODAY = "2026-09-30"  # "today" in the data package (company.md)
WINDOW_START = "2025-10-01"  # the last 12 months of the data
COUNTRY_FACTOR = {"AT": 1.05, "CH": 1.05, "CZ": 0.825, "PL": 0.825, "HU": 0.825, "TR": 0.75, "CN": 0.70}
GENERIC_BAND_PCT = 15
JOB_SHOP_STAFF = 80
TREND_POINTS = 2.0
BAND = re.compile(r"^\s*(?:(?P<lo>\d+(?:\.\d+)?)-(?P<hi>\d+(?:\.\d+)?)|>\s*(?P<gt>\d+(?:\.\d+)?))\s*M EUR\s*$")
OWNER_RATE = {"group": 0.065, "family": 0.09}
JOB_SHOP_RATE = 0.25
OTHER_RATE = 0.10
CREDIT_SURCHARGE = 0.05


def r(x, digits):
    return None if x is None else round(float(x), digits)


def mean(values):
    values = [v for v in values if v is not None]
    return sum(values) / len(values) if values else None


def add_months(month, n):
    y, m = map(int, month.split("-"))
    total = y * 12 + (m - 1) + n
    return f"{total // 12:04d}-{total % 12 + 1:02d}"


# -- parts ----------------------------------------------------------------------------------------
def pick_should_cost(rows, sid):
    """This supplier's own plant estimate, else the generic one; never another supplier's plant."""
    own = [x for x in rows if x.get("supplier_id") == sid]
    generic = [x for x in rows if not x.get("supplier_id")]
    row = (own or generic or [None])[0]
    if row is None:
        return None
    return {
        "id": row["id"],
        "unit_cost": r(row["unit_cost"], 2),
        "price_unit": int(row.get("price_unit") or 1),
        "plant_specific": bool(own),
        "cost_base": row.get("cost_base"),
        "confidence_pct": row.get("confidence_pct"),
        "material_eur": r(row.get("material_eur"), 2),
        "conversion_eur": r(row.get("conversion_eur"), 2),
        "overhead_eur": r(row.get("overhead_eur"), 2),
    }


def per_unit(value, from_unit, to_unit):
    return value * (to_unit or 1) / (from_unit or 1)


def floor_estimate(sc, country, part_price_unit):
    if not sc:
        return None
    cost = per_unit(sc["unit_cost"], sc["price_unit"], part_price_unit or sc["price_unit"])
    if sc["plant_specific"]:
        value, band = cost, (sc["confidence_pct"] or 5) / 100
        basis = f"plant-specific should-cost {sc['id']}"
    else:
        factor = COUNTRY_FACTOR.get(country, 1.0)
        value, band = cost * factor, GENERIC_BAND_PCT / 100
        basis = f"generic {sc['cost_base']} should-cost {sc['id']} x {factor} ({country})"
    return {"value": r(value, 2), "low": r(value * (1 - band), 2), "high": r(value * (1 + band), 2), "basis": basis}


def price_to_should_cost(price, sc):
    if not (price and sc and sc["unit_cost"]):
        return None
    ours = price["price"] / (price.get("price_unit") or 1)
    theirs = sc["unit_cost"] / (sc["price_unit"] or 1)
    return r(ours / theirs, 4)


def history_summary(rows):
    events = [{k: row.get(k) for k in ("event_id", "date", "type", "asked_pct", "settled_pct", "note")} for row in rows]
    pairs = [
        (e["asked_pct"], e["settled_pct"])
        for e in events
        if e["asked_pct"] is not None and e["settled_pct"] is not None
    ]
    return {
        "events": events,
        "mean_asked_pct": r(mean(e["asked_pct"] for e in events), 2),
        "mean_settled_pct": r(mean(e["settled_pct"] for e in events), 2),
        "mean_give_pct": r(mean(a - s for a, s in pairs), 2),
        "below_full_cost": any("below full cost" in (e["note"] or "").lower() for e in events),
    }


def window(points, months):
    """Change over the last `months` months of a series {month: (value, id)}: (pct, [id_start, id_end])."""
    if not points:
        return None, []
    end = max(points)
    start = add_months(end, -months)
    if start not in points or not points[start][0]:
        return None, []
    return r((points[end][0] / points[start][0] - 1) * 100, 2), [points[start][1], points[end][1]]


def drivers(rows, series):
    out = []
    for row in rows:
        points = series.get(row["series_id"], {})
        last = max(points) if points else None
        c12, ids12 = window(points, 12)
        c6, ids6 = window(points, 6)
        out.append(
            {
                "series": row["series_id"],
                "weight": r(row.get("weight"), 4),
                "last_month": last,
                "last_value": points[last][0] if last else None,
                "change_12m_pct": c12,
                "ids_12m": ids12,
                "change_6m_pct": c6,
                "ids_6m": ids6,
            }
        )
    return sorted(out, key=lambda d: (-(d["weight"] or 0), d["series"]))


def forecast(ref, row, facts):
    if not ref:
        return None
    fact = facts.get(ref) or {}
    return {
        "id": ref,
        "snapshot_month": (row or {}).get("snapshot_month") or ref.split("@", 1)[-1],
        "volume_next_12m": (row or {}).get("qty_next_12m"),
        "change_pct": fact.get("change_pct"),
        "volume_per_year": fact.get("volume_per_year"),
    }


def alternatives(other_sources, rival_quotes):
    out = [
        {
            "supplier_id": s["supplier_id"],
            "name": s.get("name"),
            "status": s.get("status"),
            "quota_pct": s.get("quota_pct"),
            "quote_id": None,
            "unit_price": None,
            "price_unit": None,
            "date": None,
            "private": True,
        }
        for s in other_sources
    ]
    out += [
        {
            "supplier_id": q["supplier_id"],
            "name": q.get("name"),
            "status": None,
            "quota_pct": None,
            "quote_id": q["id"],
            "unit_price": r(q.get("unit_price"), 2),
            "price_unit": q.get("price_unit"),
            "date": q.get("quote_date"),
            "private": True,
        }
        for q in rival_quotes
    ]
    return sorted(out, key=lambda a: (a["supplier_id"], a["date"] or "", a["quote_id"] or ""))


# -- the supplier ---------------------------------------------------------------------------------
def turnover(identity):
    """(EUR, estimated): the filed turnover, else the middle of its band."""
    if identity.get("turnover_eur"):
        return float(identity["turnover_eur"]), False
    m = BAND.match(identity.get("turnover_band") or "")
    if not m:
        return None, False
    if m["gt"]:
        return float(m["gt"]) * 1e6, True
    return (float(m["lo"]) + float(m["hi"])) / 2 * 1e6, True


def share_of_turnover(spend, identity):
    value, _ = turnover(identity)
    if not spend or not value:
        return None
    return r(spend[max(spend)] / value * 100, 2)


def performance(cards, complaints):
    if not cards:
        return None
    latest, recent = cards[0], cards[:4]
    trend = None
    if len(cards) >= 5 and latest.get("score") is not None and cards[4].get("score") is not None:
        diff = latest["score"] - cards[4]["score"]
        trend = "better" if diff > TREND_POINTS else "worse" if diff < -TREND_POINTS else "flat"
    keys = ("id", "quarter", "otd_pct", "otd_confirmed_pct", "ppm", "score", "class", "colour", "open_8d_overdue")
    return {
        "latest": {k: latest.get(k) for k in keys},
        "mean_4q": {
            "ids": sorted(c["id"] for c in recent),
            "otd_pct": r(mean(c.get("otd_pct") for c in recent), 2),
            "ppm": r(mean(c.get("ppm") for c in recent), 2),
        },
        "trend": trend,
        "qn_12m": len(complaints),
        "qn_supplier_caused_12m": sum(1 for q in complaints if q.get("supplier_caused")),
        "qn_ids_12m": [q["id"] for q in complaints],
    }


def cash_pressure(identity, terms, cash_short):
    if terms.get("skonto_pct") or cash_short >= 2:
        return "high"
    credit, before = identity.get("credit_index"), identity.get("credit_index_12m_ago")
    if (
        (identity.get("equity_ratio_pct") or 100) < 25
        or (credit or 0) >= 250
        or (credit and before and credit > before)
    ):
        return "medium"
    return "low"


def archetype(identity, pressure, kinds, has_alternative, from_stock=False):
    if "capacity_tight" in kinds or "list_price_fixed" in kinds:
        if not has_alternative:
            return "monopolist", "capacity or list price signalled and no alternative source"
    owner = identity.get("owner_type")
    if owner == "group":
        return "group", "owner type group"
    if (identity.get("staff") or JOB_SHOP_STAFF) < JOB_SHOP_STAFF:
        return "job_shop", f"staff {identity['staff']} < {JOB_SHOP_STAFF}"
    if pressure == "high":
        return "job_shop", "cash pressure high"
    if owner == "family":
        return "family", "owner type family"
    if identity.get("category") == "raw material" or from_stock:
        return "trader", "raw material or supply from stock"
    return "other", "no rule applies"


def cost_of_money(identity, terms, arche, cash_short):
    """(yearly rate, basis): measured from skonto terms, else a rule by type, plus a credit surcharge."""
    pct, early, net = terms.get("skonto_pct"), terms.get("skonto_days"), terms.get("payment_days")
    if pct and early is not None and net and net > early:
        return r(pct / 100 * 360 / (net - early), 4), f"skonto {pct} % at {early} vs {net} days (measured)"
    if arche == "job_shop" or cash_short >= 2:
        rate, basis = JOB_SHOP_RATE, "rule: job shop or short of cash"
    else:
        owner = identity.get("owner_type")
        rate, basis = OWNER_RATE.get(owner, OTHER_RATE), f"rule: owner type {owner or 'unknown'}"
    credit, before = identity.get("credit_index"), identity.get("credit_index_12m_ago")
    if (credit or 0) >= 300 or (credit and before and credit - before >= 20):
        rate, basis = rate + CREDIT_SURCHARGE, basis + f", +{CREDIT_SURCHARGE} for credit index {before} -> {credit}"
    return r(rate, 4), basis
