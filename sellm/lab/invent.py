"""Invented suppliers on generated cases, against overfitting to the 15 suppliers we know.

The final has new suppliers and settings, and up to a third combine supplier and case types that
practice never shows. So a scenario here takes the buyer side of a known case (need, horizon, rates),
changes its goal, its negotiable fields (any of them, incoterm and tooling included), their options,
the must-haves and the alternative, and puts in one to three suppliers drawn from the data package
(name, country, standard terms, credit index, defect rate) with random economics and dynamics in the
ranges the backtest found plausible. The floor is set first, so C_best follows from it.
"""

import copy
import math
import random

from arena_kit.cost import RELATIONSHIP_GOALS, must_haves_ok, total_cost

from .persona import Persona, best_package
from .table import Scenario

GOALS = ["stabilise", "secure_supply", "quality_first", "leverage", "routine"]
FIELDS = [
    "payment_days",
    "effective_date",
    "contract_months",
    "volume_per_year",
    "lead_time_days",
    "index_clause",
    "incoterm",
    "ppm_commitment",
    "chargeback_eur_per_complaint",
    "tooling_eur",
]
STYLE = {"family": "family", "founder": "casual", "private": "casual", "group": "corporate"}


def suppliers(package):
    """The detailed suppliers of the data package with what a persona needs."""
    rows = package.query(
        "select s.id, s.name, s.country, s.payment_days, s.standard_lead_time_days, s.incoterm,"
        " i.owner_type, i.credit_index, i.equity_ratio_pct from suppliers s join supplier_intel i"
        " on i.supplier_id = s.id where s.detail = 'full'",
        limit=1000,
    )
    out = []
    for r in rows:
        sc = package.query("select ppm from scorecards where supplier_id = ? order by quarter desc limit 1", (r["id"],))
        out.append({**r, "ppm": sc[0]["ppm"] if sc else None})
    return out


def _options(rng, field, b, base):
    need = b["need_per_year"]
    if field == "payment_days":
        return [14, 30, 45, 60, 90]
    if field == "effective_date":
        months = ["2026-11-01", "2026-12-01", "2027-01-01", "2027-02-01", "2027-04-01"]
        return sorted(rng.sample(months, rng.randint(2, 4)))
    if field == "contract_months":
        return [12, 24, 36] if b["horizon_years"] >= 2 else [0, 12]
    if field == "volume_per_year":
        return [round(need * 0.85), need, round(need * 1.2)]
    if field == "lead_time_days":
        return sorted(rng.sample([14, 21, 28, 35, 42, 49, 56], 4))
    if field == "index_clause":
        series = rng.choice(base.get("drivers") or ["LCI-C"])
        share = rng.choice([0.2, 0.3, 0.45])
        return [None] + [
            {"series": series, "material_share": share, "deadband_pct": d, "base_month": "2026-08"} for d in (0, 3, 5)
        ]
    if field == "incoterm":
        return ["EXW", "FCA", "DAP"]
    if field == "ppm_commitment":
        return [300, 800, 1500, 2500]
    if field == "chargeback_eur_per_complaint":
        return [0, 150, 300, 500]
    if field == "tooling_eur":
        return [0, 5000, 15000]
    raise ValueError(field)


def invent(rng, bases, pool, name):
    """One scenario: a mutated case from `bases` (Scenarios) with suppliers drawn from `pool`."""
    base = rng.choice(bases)
    case = copy.deepcopy(base.case)
    b = case["buyer"]
    goal = rng.choice(GOALS)
    b["category_goal"] = goal
    price = b.get("current_unit_price") or next(iter(base.personas.values())).opening["unit_price"]
    if goal in RELATIONSHIP_GOALS:
        b["sustainable_margin_pct"] = rng.choice([3, 5, 8, 10])
        b["relationship_eur_per_point"] = round(price * b["need_per_year"] * rng.uniform(0.004, 0.02))
    else:
        b["sustainable_margin_pct"] = b["relationship_eur_per_point"] = None
    fields = rng.sample(FIELDS, rng.randint(2, 4))
    case["negotiable"] = ["unit_price", *fields]
    info = {"drivers": base.drivers}
    case["term_options"] = {f: _options(rng, f, b, info) for f in fields}
    if "index_clause" in fields:
        series = next(o["series"] for o in case["term_options"]["index_clause"] if o)
        b["index_paths"] = {series: round(rng.uniform(-0.06, 0.08), 3)}
    if "incoterm" in fields:
        b["freight_eur_per_unit"] = {"EXW": round(price * 0.03, 2), "FCA": round(price * 0.02, 2), "DAP": 0.0}
    fixed = {
        "payment_days": 30,
        "lead_time_days": b["need_lead_time_days"],
        "volume_per_year": b["need_per_year"],
        "contract_months": round(12 * b["horizon_years"]),
        "effective_date": "2027-01-01",
        "index_clause": None,
        "incoterm": "DAP",
        "tooling_eur": 0,
    }
    case["fixed_terms"] = {k: v for k, v in fixed.items() if k not in fields}
    b["freight_eur_per_unit"].setdefault("DAP", 0.0)
    b["must_haves"] = []
    if rng.random() < 0.4:
        f = rng.choice(fields)
        opts = [o for o in case["term_options"][f] if isinstance(o, int | float)]
        if f in ("lead_time_days", "ppm_commitment") and len(opts) > 1:
            b["must_haves"] = [{"field": f, "op": "<=", "value": sorted(opts)[-2]}]
        elif f == "volume_per_year":
            b["must_haves"] = [{"field": f, "op": ">=", "value": round(b["need_per_year"] * 0.95)}]
    n = 1 if rng.random() < 0.75 else rng.randint(2, 3)
    if n > 1:
        case["type"] = "rfq"
    case["suppliers"], personas = [], {}
    floor_ratio = rng.uniform(0.78, 0.97)
    for sup in rng.sample(pool, n):
        sid = sup["id"]
        case["suppliers"].append(sid)
        personas[sid] = _persona(rng, case, sup, price * floor_ratio * rng.uniform(0.97, 1.03))
    case["case_id"] = f"case:{name}"
    case["title"] = f"Invented {case['type']} ({goal})"
    case["briefing"] = "An invented case for the lab."
    case.pop("trigger_doc", None)
    case["refs"] = [r for r in case.get("refs", []) if not r.startswith(("doc:", "ctr:", "sc:", "quote:"))]
    b["alternative"] = {"kind": "none"}
    c_open = (
        min(
            total_cost(case, p.opening, p.pdf_standard)
            for p in personas.values()
            if must_haves_ok(case, p.opening, p.pdf_standard)
        )
        if any(must_haves_ok(case, p.opening, p.pdf_standard) for p in personas.values())
        else min(total_cost(case, p.opening, p.pdf_standard) for p in personas.values())
    )
    if rng.random() < 0.4:  # an alternative quote, sometimes better than the opening
        p = next(iter(personas.values()))
        alt = {**p.closing(case, p.opening), "unit_price": round(p.opening["unit_price"] * rng.uniform(0.97, 1.08), 2)}
        b["alternative"] = {"kind": "quote", "ref": None, "terms": alt}
    c_best, _ = min(best_package(case, p) for p in personas.values())
    alt_c = total_cost(case, b["alternative"]["terms"]) if b["alternative"].get("terms") else math.inf
    c_best = min(c_best, alt_c)
    if not (c_open - c_best > 0.01 * c_open and math.isfinite(c_best)):
        return None
    return Scenario(
        case=case,
        personas=personas,
        c_open=c_open,
        c_best=c_best,
        kind="invented",
        name=name,
        notes=f"from {base.name}",
        drivers=base.drivers,
    )


def _persona(rng, case, sup, full_cost):
    neg = [f for f in case["negotiable"] if f != "unit_price"]
    opts = case["term_options"]
    # its own standard: what it would offer if asked nothing
    std = {}
    for f in neg:
        o = [x for x in opts[f] if x is not None or f == "index_clause"]
        if f == "payment_days":
            std[f] = min(o, key=lambda x: abs(x - (sup["payment_days"] or 30)))
        elif f == "lead_time_days":
            std[f] = min(o, key=lambda x: abs(x - (sup["standard_lead_time_days"] or 35)))
        elif f == "index_clause":
            std[f] = rng.choice(o)
        elif f in ("ppm_commitment",):
            std[f] = max(o)
        elif f == "chargeback_eur_per_complaint":
            std[f] = 0
        elif f == "tooling_eur":
            std[f] = rng.choice(o)
        elif f == "incoterm":
            std[f] = rng.choice(["EXW", "FCA", "DAP"])
        else:
            std[f] = rng.choice(o)
    from arena_kit.cost import closing_terms

    pdf = {"ppm_commitment": sup["ppm"] or 500, "chargeback_eur_per_complaint": 0.0}
    pdf = {k: v for k, v in pdf.items() if k not in neg and k not in case["fixed_terms"]}
    standard = closing_terms(case, std, pdf)
    standard.pop("unit_price", None)
    credit = sup.get("credit_index") or 200
    price = full_cost
    premiums = {}
    if "lead_time_days" in neg and rng.random() < 0.6:
        premiums["lead_time_days"] = round(price * rng.uniform(0.0, 0.006), 4)
    if "index_clause" in neg and rng.random() < 0.6:
        premiums["fixed_price"] = round(price * rng.uniform(0.0, 0.03), 4)
    if "ppm_commitment" in neg:
        premiums["ppm_commitment"] = round(price * rng.uniform(0.005, 0.04), 4)
    if "contract_months" in neg and rng.random() < 0.5:
        premiums["contract_months"] = round(price * rng.uniform(-0.005, 0.02), 4)
    if "volume_per_year" in neg and rng.random() < 0.5:
        premiums["volume_per_year"] = round(price * rng.uniform(-0.02, 0.04), 4)
    p = Persona(
        supplier_id=sup["id"],
        name=sup["name"],
        opening={},
        standard=standard,
        pdf_standard=pdf,
        full_cost=full_cost,
        rate=round(min(0.4, 0.05 + max(0, credit - 140) / 100 * 0.12 * rng.uniform(0.5, 1.5)), 3),
        ppm_real=sup["ppm"],
        premiums=premiums,
        first_step=rng.uniform(0.03, 0.6),
        mirror=rng.uniform(0.3, 0.85),
        patience=rng.randint(3, 7),
        cap=rng.uniform(0.002, 0.015),
        cap_decay=rng.uniform(0.6, 1.0),
        walk_on_push=rng.uniform(0.2, 0.7),
        claim_kinds=rng.sample(["idx", "cost", "sc", "qn", "fc", "quote", "offer", "doc", "po"], rng.randint(0, 3)),
        claim_w=rng.uniform(0.0, 0.3),
        ultimatum=rng.uniform(0.3, 0.8),
        leak=rng.uniform(0.4, 0.9),
        discloses=rng.random() < 0.3,
        alternatives=rng.random() < 0.8,
        style=STYLE.get(sup.get("owner_type"), "corporate"),
        sender=f"sales@{sup['id'].split(':', 1)[1]}",
        sender_name=f"Sales, {sup['name']}",
        traits=["family"] if sup.get("owner_type") == "family" else [],
    )
    if rng.random() < 0.25 and neg:  # a hard limit on one lever
        f = rng.choice([x for x in neg if x in ("payment_days", "lead_time_days")] or [None])
        if f == "payment_days":
            p.hard_limits = {f: ["<=", rng.choice([45, 60])]}
        elif f == "lead_time_days":
            p.hard_limits = {f: [">=", sorted(opts[f])[1]]}
    stated = {f: standard[f] for f in rng.sample(neg, rng.randint(0, len(neg))) if f in standard}
    markup = rng.uniform(1.05, 1.3)
    p.opening = {**stated, "unit_price": p.price_for(case, stated, full_cost * markup)}
    return p


def generate(n, bases, package, seed=0):
    """`n` invented scenarios (deterministic for a seed)."""
    rng, pool, out, i = random.Random(seed), suppliers(package), [], 0
    while len(out) < n and i < n * 5:
        i += 1
        s = invent(rng, bases, pool, f"X{seed:02d}-{len(out):03d}")
        if s is not None:
            out.append(s)
    return out
