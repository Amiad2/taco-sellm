"""Scenarios beyond the twins, so a strategy is tested on what the final may bring, not only on the
15 suppliers we have met. The final has new suppliers and settings, and up to a third combine
supplier and case types practice never shows.

- `data`: a practice case file we never played (P06, P09, P12-P17, P19; `sellm/lab/cases/`), as it
  is, with its real supplier from the data package: standard terms from the vendor master, defect
  rate from the scorecard, cost of money from the credit index, the floor from the plant's
  should-cost where there is one, the opening from the trigger letter's asked price where it says.
- `invented`: any case file mutated - another goal, 1-7 negotiable fields of any kind (incoterm and
  tooling included), new options, must-haves of every operator, alternatives, RFQs of 2-3 bidders -
  with suppliers drawn from the 46 detailed suppliers.

Every supplier gets an **archetype** from the brief (family firm, group with an approval ladder, job
shop short of cash, near-monopolist, trader, quality-troubled, capacity-tight, generous), drawn from
its data where that says something (owner type, size, credit index) and at random otherwise, with
dynamics in ranges around what the backtest fitted. **Edge cases** are tagged on the scenario:
an opening that breaks a must-have, walking away as the best move, short round limits, a bidder
that does not bid, facts that exist only in the case, prices per 100 pieces, a three-year horizon,
single orders, a falling index, and more.
"""

import copy
import json
import math
import random
from pathlib import Path

from arena_kit.cost import RELATIONSHIP_GOALS, closing_terms, must_haves_ok, total_cost

from .persona import Persona, best_package
from .table import Scenario

CASES = Path(__file__).with_name("cases")
GOALS = ["stabilise", "secure_supply", "quality_first", "leverage", "routine"]
TYPES = ["price_increase", "renewal", "rfq", "bundling", "raw_material", "capacity", "quality"]
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

# ranges per archetype: (low, high) for floats and ints; scalars as they are
ARCHETYPES = {
    "family": dict(first_step=(0.2, 0.5), mirror=(0.5, 0.85), cap=(0.003, 0.01), cap_decay=(0.75, 1.0),
                   patience=(5, 7), tone_walk=(0.1, 0.35), ultimatum=(0.3, 0.5), rate=(0.07, 0.12),
                   claim_w=(0.05, 0.25), discloses=0.2, traits=["family"]),
    "group": dict(first_step=(0.1, 0.35), mirror=(0.3, 0.6), cap=(0.002, 0.006), cap_decay=(0.7, 1.0),
                  patience=(4, 7), approval_at=(0.25, 0.6), tone_walk=(0.0, 0.1), rate=(0.05, 0.08),
                  claim_w=(0.0, 0.15), discloses=0.1),
    "job_shop": dict(first_step=(0.2, 0.6), mirror=(0.5, 0.85), cap=(0.005, 0.02), cap_decay=(0.6, 0.9),
                     patience=(3, 6), withdraw_on_wait=(0.6, 1.0), rate=(0.15, 0.4), claim_w=(0.05, 0.3),
                     discloses=0.4, traits=["cash_short"]),
    "monopolist": dict(first_step=(0.01, 0.08), mirror=(0.1, 0.3), cap=(0.001, 0.003), cap_decay=(0.6, 0.9),
                       patience=(3, 5), walk_on_push=(0.6, 0.9), tone_walk=(0.3, 0.6), rate=(0.05, 0.09),
                       claim_w=(0.0, 0.05), discloses=0.0),
    "trader": dict(first_step=(0.15, 0.4), mirror=(0.4, 0.7), cap=(0.003, 0.01), patience=(4, 6),
                   rate=(0.06, 0.1), claim_w=(0.05, 0.2), discloses=0.2, traits=["hedged"]),
    "quality": dict(first_step=(0.1, 0.4), mirror=(0.4, 0.7), cap=(0.003, 0.01), patience=(4, 7),
                    rate=(0.08, 0.2), claim_w=(0.1, 0.35), discloses=0.3),
    "capacity": dict(first_step=(0.02, 0.2), mirror=(0.2, 0.5), cap=(0.002, 0.006), patience=(3, 6),
                     rate=(0.06, 0.1), claim_w=(0.0, 0.1), discloses=0.1, traits=["capacity_tight"]),
    "generous": dict(first_step=(0.5, 0.8), mirror=(0.7, 0.9), cap=(0.01, 0.03), patience=(5, 7),
                     rate=(0.06, 0.15), claim_w=(0.1, 0.3), discloses=0.5),
}  # fmt: skip
EDGES = [
    "opening_breaks_must_have",
    "walk_away_best",
    "short_rounds",
    "no_bid",
    "case_facts",
    "per_100",
    "three_years",
    "single_order",
    "falling_index",
    "all_fields",
    "price_only",
    "current_contract",
]


def load_cases(folder=CASES):
    return {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in sorted(Path(folder).glob("*.json"))}


def supplier_pool(package):
    """The detailed suppliers of the data package with what a persona needs."""
    rows = package.query(
        "select s.id, s.name, s.country, s.payment_days, s.standard_lead_time_days, s.incoterm,"
        " i.owner_type, i.staff, i.credit_index, i.equity_ratio_pct from suppliers s join supplier_intel i"
        " on i.supplier_id = s.id where s.detail = 'full'",
        limit=1000,
    )
    out = {}
    for r in rows:
        sc = package.query("select ppm from scorecards where supplier_id = ? order by quarter desc limit 1", (r["id"],))
        out[r["id"]] = {**r, "ppm": sc[0]["ppm"] if sc else None}
    return out


def _drivers(package, parts):
    rows = package.query(
        f"select distinct series_id from cost_drivers where part_id in ({','.join('?' * len(parts))})", tuple(parts)
    )
    return [r["series_id"] for r in rows]


def _u(rng, spec):
    if isinstance(spec, tuple):
        lo, hi = spec
        return rng.randint(lo, hi) if isinstance(lo, int) and isinstance(hi, int) else rng.uniform(lo, hi)
    return spec


def archetype_for(rng, sup):
    """From the supplier's data where it says something, else at random."""
    if rng.random() < 0.6:
        owner, staff, credit = sup.get("owner_type"), sup.get("staff") or 100, sup.get("credit_index") or 200
        if owner == "family":
            return "family"
        if owner == "group":
            return "group"
        if staff < 80 or credit > 230:
            return "job_shop"
    return rng.choice(list(ARCHETYPES))


def make_persona(rng, case, sup, full_cost, archetype, opening_value=None, opening_price=None):
    """A supplier in `case`: its standard terms from the data, dynamics from its archetype, its floor
    `full_cost` (value per unit) and an opening `opening_value` (or `opening_price` at its standard)."""
    arch = ARCHETYPES[archetype]
    neg = [f for f in case["negotiable"] if f != "unit_price"]
    opts = case["term_options"]
    std = {}
    for f in neg:
        o = [x for x in opts.get(f, []) if x is not None or f == "index_clause"]
        if not o:
            continue
        if f == "payment_days":
            std[f] = sup.get("payment_days") or 30  # its own term, even if not an option
        elif f == "lead_time_days":
            std[f] = sup.get("standard_lead_time_days") or min(o)
        elif f == "incoterm":
            std[f] = sup.get("incoterm") or rng.choice(o)
        elif f == "ppm_commitment":
            std[f] = max(o) if archetype != "quality" else max(o) * 2
        elif f == "chargeback_eur_per_complaint":
            std[f] = min(o)
        elif f == "index_clause":
            std[f] = next((x for x in o if x), None) if archetype == "trader" or rng.random() < 0.4 else None
        elif f == "volume_per_year":
            std[f] = min(o) if archetype == "capacity" else rng.choice(o)
        elif f == "contract_months":
            std[f] = min(o)
        else:
            std[f] = rng.choice(o)
    ppm = sup.get("ppm") or rng.choice([200, 600, 1500])
    if archetype == "quality":
        ppm = max(ppm, rng.choice([2500, 4000, 6500]))
    pdf = {"ppm_commitment": ppm, "chargeback_eur_per_complaint": 0.0}
    pdf = {k: v for k, v in pdf.items() if k not in neg and k not in case.get("fixed_terms", {})}
    standard = closing_terms(case, std, pdf)
    standard.pop("unit_price", None)
    credit = sup.get("credit_index") or 200
    rate = _u(rng, arch["rate"]) * (0.8 + max(0, credit - 140) / 250)
    premiums = {}
    if "lead_time_days" in neg:
        premiums["lead_time_days"] = full_cost * rng.uniform(0.002, 0.008 if archetype == "capacity" else 0.004)
    if "index_clause" in neg and (archetype == "trader" or rng.random() < 0.5):
        premiums["fixed_price"] = full_cost * rng.uniform(0.005, 0.03)
    if "ppm_commitment" in neg:
        premiums["ppm_commitment"] = full_cost * rng.uniform(0.005, 0.04 if archetype == "quality" else 0.02)
    if "contract_months" in neg and rng.random() < 0.5:
        premiums["contract_months"] = full_cost * rng.uniform(-0.005, 0.02)
    if "volume_per_year" in neg and rng.random() < 0.6:
        lo, hi = (-0.04, -0.005) if archetype == "capacity" else (-0.01, 0.04)
        premiums["volume_per_year"] = full_cost * rng.uniform(lo, hi)
    p = Persona(
        supplier_id=sup["id"],
        name=sup["name"],
        opening={},
        standard=standard,
        pdf_standard=pdf,
        full_cost=full_cost,
        rate=round(min(0.45, rate), 3),
        ppm_real=ppm,
        premiums={k: round(v, 4) for k, v in premiums.items()},
        first_step=_u(rng, arch["first_step"]),
        mirror=_u(rng, arch["mirror"]),
        patience=_u(rng, arch["patience"]),
        cap=_u(rng, arch["cap"]),
        cap_decay=_u(rng, arch.get("cap_decay", (0.6, 1.0))),
        walk_on_push=_u(rng, arch.get("walk_on_push", (0.2, 0.6))),
        claim_kinds=rng.sample(["idx", "cost", "sc", "qn", "fc", "quote", "offer", "doc", "po"], rng.randint(0, 4)),
        claim_w=_u(rng, arch["claim_w"]),
        ultimatum=_u(rng, arch.get("ultimatum", (0.4, 0.8))),
        leak=rng.uniform(0.4, 0.9),
        tone_walk=_u(rng, arch.get("tone_walk", (0.0, 0.2))),
        withdraw_on_wait=_u(rng, arch.get("withdraw_on_wait", (0.2, 0.6))),
        approval_at=_u(rng, arch["approval_at"]) if "approval_at" in arch else None,
        noise=rng.uniform(0.05, 0.2),
        discloses=rng.random() < arch["discloses"],
        alternatives=rng.random() < 0.8,
        asks_data=rng.random() < 0.7,
        archetype=archetype,
        style=STYLE.get(sup.get("owner_type"), "corporate"),
        sender=f"sales@{sup['id'].split(':', 1)[1]}",
        sender_name=f"Sales, {sup['name']}",
        traits=list(arch.get("traits", [])),
    )
    if "capacity_tight" in p.traits and "lead_time_days" in neg:
        options = sorted(o for o in opts["lead_time_days"] if o is not None)
        if len(options) > 2:
            p.hard_limits = {"lead_time_days": [">=", options[1]]}
    elif rng.random() < 0.15 and "payment_days" in neg:
        p.hard_limits = {"payment_days": ["<=", rng.choice([45, 60])]}
    stated = {f: standard[f] for f in rng.sample(neg, rng.randint(0, len(neg))) if f in standard}
    price = opening_price if opening_price is not None else p.price_for(case, stated, opening_value)
    p.opening = {**stated, "unit_price": round(max(price, 0.01), 2)}
    return p


def _options(rng, field, b, drivers):
    need = b["need_per_year"]
    if field == "payment_days":
        return [14, 30, 45, 60, 90]
    if field == "effective_date":
        months = ["2026-11-01", "2026-12-01", "2027-01-01", "2027-02-01", "2027-04-01"]
        return sorted(rng.sample(months, rng.randint(2, 4)))
    if field == "contract_months":
        h = b["horizon_years"]
        return [12, 24, 36] if h >= 2 else rng.choice([[0, 12], [6, 12], [12, 24]])
    if field == "volume_per_year":
        return [round(need * 0.85), need, round(need * 1.2)]
    if field == "lead_time_days":
        return sorted(rng.sample([14, 21, 28, 35, 42, 49, 56, 70], 4))
    if field == "index_clause":
        series = rng.choice(drivers or ["LCI-C"])
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


def _must_have(rng, case):
    """A must-have on one negotiable field, any operator, satisfiable by some option."""
    opts = case["term_options"]
    fields = [f for f in case["negotiable"] if f != "unit_price" and opts.get(f)]
    if not fields:
        return []
    f = rng.choice(fields)
    values = [o for o in opts[f] if o is not None]
    if not values:
        return []
    if f == "incoterm":
        return [{"field": f, "op": rng.choice(["==", "!="]), "value": rng.choice(["DAP", "EXW"])}]
    if f == "effective_date":
        return [{"field": f, "op": "<=", "value": sorted(values)[len(values) // 2]}]
    if f == "index_clause" or not all(isinstance(v, int | float) for v in values):
        return []
    v = sorted(values)
    if f in ("lead_time_days", "ppm_commitment"):
        return [{"field": f, "op": rng.choice(["<=", "<"]), "value": v[-2] if len(v) > 1 else v[0]}]
    if f in ("volume_per_year", "contract_months", "chargeback_eur_per_complaint", "payment_days"):
        op = rng.choice([">=", ">"])
        return [{"field": f, "op": op, "value": v[1] if op == ">=" else v[0]}]
    return [{"field": f, "op": "<=", "value": v[-1]}]


def _c_open(case, personas):
    bids = [p for p in personas.values() if not p.no_bid]
    ok = [total_cost(case, p.opening, p.pdf_standard) for p in bids if must_haves_ok(case, p.opening, p.pdf_standard)]
    every = [total_cost(case, p.opening, p.pdf_standard) for p in bids]
    return (min(ok) if ok else min(every)) if every else None


def _finish(case, personas, name, kind, drivers, tags, rng, alt_mode=None):
    """C_open, the alternative and C_best; None if the scenario has no room to negotiate."""
    b = case["buyer"]
    c_open = _c_open(case, personas)
    if c_open is None:
        return None
    bids = [p for p in personas.values() if not p.no_bid]
    best = min((best_package(case, p, exact=False) for p in bids), key=lambda x: x[0])
    if not math.isfinite(best[0]):
        return None
    p0 = bids[0]
    base = p0.closing(case, p0.opening)
    if alt_mode == "walk_away_best":  # an alternative cheaper than any deal the suppliers accept
        lo, hi = 0.01, p0.opening["unit_price"] * 2
        for _ in range(40):
            mid = (lo + hi) / 2
            lo, hi = (mid, hi) if total_cost(case, {**base, "unit_price": mid}) < best[0] * 0.98 else (lo, mid)
        b["alternative"] = {"kind": "quote", "ref": None, "terms": {**base, "unit_price": round(lo, 2)}}
    elif alt_mode in ("quote", "current_contract"):
        factor = rng.uniform(1.0, 1.1) if alt_mode == "quote" else rng.uniform(0.97, 1.02)
        price = (b.get("current_unit_price") or p0.opening["unit_price"]) * factor
        b["alternative"] = {"kind": alt_mode, "ref": None, "terms": {**base, "unit_price": round(price, 2)}}
    else:
        b["alternative"] = {"kind": "none"}
    alt = b["alternative"]
    c_alt = total_cost(case, alt["terms"]) if alt.get("terms") else math.inf
    c_best = min(best[0], c_alt)
    if c_open - c_best <= 0.005 * c_open:
        return None
    notes = f"archetypes {sorted({p.archetype for p in personas.values()})}"
    return Scenario(case=case, personas=personas, c_open=c_open, c_best=c_best, kind=kind, name=name,
                    notes=notes, drivers=drivers, tags=tags)  # fmt: skip


def _floor(rng, package, case, sup_id, price_ref):
    """Its full cost: the plant's should-cost if there is one, else a share of the current price."""
    for part in case["parts"]:
        for r in package.query("select unit_cost, supplier_id from should_cost where part_id = ?", (part,)):
            if r["supplier_id"] == sup_id:
                return r["unit_cost"] * rng.uniform(0.96, 1.04)
    return price_ref * rng.uniform(0.82, 0.97)


def data_scenario(rng, package, pool, case, name):
    """A case file we never played, with its own suppliers from the data."""
    case = copy.deepcopy(case)
    b = case["buyer"]
    drivers = _drivers(package, case["parts"])
    price_ref = b.get("current_unit_price") or b["fallback_unit_price"]
    asked = None
    if case.get("trigger_doc") and (doc := package.lookup(case["trigger_doc"])):
        asked = doc.get("asked_price") or (price_ref * (1 + doc["asked_pct"] / 100) if doc.get("asked_pct") else None)
    personas = {}
    for sid in case["suppliers"]:
        sup = pool.get(sid) or {"id": sid, "name": sid}
        full = _floor(rng, package, case, sid, price_ref)
        arch = archetype_for(rng, sup)
        if asked and len(case["suppliers"]) == 1:
            personas[sid] = make_persona(rng, case, sup, full, arch, opening_price=asked * rng.uniform(0.99, 1.01))
        else:
            personas[sid] = make_persona(rng, case, sup, full, arch, opening_value=full * rng.uniform(1.06, 1.3))
    alt = b.get("alternative") or {}
    if alt.get("kind") in ("quote", "current_contract") and (alt.get("terms") or {}).get("unit_price"):
        c_open = _c_open(case, personas)
        best = min(best_package(case, p, exact=False)[0] for p in personas.values())
        c_best = min(best, total_cost(case, alt["terms"]))
        if c_open is None or c_open - c_best <= 0.005 * c_open:
            return None
        return Scenario(case=case, personas=personas, c_open=c_open, c_best=c_best, kind="data", name=name,
                        notes=f"case file {case['case_id']}", drivers=drivers, tags=["case_file"])  # fmt: skip
    return _finish(case, personas, name, "data", drivers, ["case_file"], rng, alt_mode=None)


def invent(rng, package, pool, cases, name, edges=None):
    """A mutated case with suppliers from the pool. `edges`: tags to force (else drawn at random)."""
    case = copy.deepcopy(rng.choice(list(cases.values())))
    b = case["buyer"]
    tags = list(edges) if edges is not None else [e for e in EDGES if rng.random() < 0.12]
    case["type"] = rng.choice(TYPES)
    goal = rng.choice(GOALS)
    b["category_goal"] = goal
    if "per_100" in tags:  # a part priced per 100 pieces: 100 times the price, a hundredth of the need
        for k in ("current_unit_price", "fallback_unit_price"):
            if b.get(k):
                b[k] = round(b[k] * 100, 2)
        b["need_per_year"] = max(10, round(b["need_per_year"] / 100))
        b["freight_eur_per_unit"] = {k: round(v * 100, 2) for k, v in b["freight_eur_per_unit"].items()}
    if "three_years" in tags:
        b["horizon_years"] = 3
    price = b.get("current_unit_price") or b["fallback_unit_price"]
    if goal in RELATIONSHIP_GOALS:
        b["sustainable_margin_pct"] = rng.choice([3, 5, 8, 10])
        b["relationship_eur_per_point"] = round(price * b["need_per_year"] * rng.uniform(0.004, 0.02))
    else:
        b["sustainable_margin_pct"] = b["relationship_eur_per_point"] = None
    drivers = _drivers(package, case["parts"])
    if "price_only" in tags:
        fields = []
    elif "all_fields" in tags:
        fields = rng.sample(FIELDS, rng.randint(5, 7))
    else:
        fields = rng.sample(FIELDS, rng.randint(1, 4))
    if "single_order" in tags and "contract_months" not in fields:
        fields.append("contract_months")
    if "falling_index" in tags and "index_clause" not in fields:
        fields.append("index_clause")
    case["negotiable"] = ["unit_price", *fields]
    case["term_options"] = {f: _options(rng, f, b, drivers) for f in fields}
    if "single_order" in tags:
        case["term_options"]["contract_months"] = [0, 12]
        b["horizon_years"] = 1
    b["index_paths"] = {}
    if "index_clause" in fields:
        series = next(o["series"] for o in case["term_options"]["index_clause"] if o)
        move = rng.uniform(-0.08, -0.02) if "falling_index" in tags else rng.uniform(-0.06, 0.08)
        b["index_paths"] = {series: round(move, 3)}
    if "incoterm" in fields and not any(b["freight_eur_per_unit"].values()):
        b["freight_eur_per_unit"] = {"EXW": round(price * 0.03, 2), "FCA": round(price * 0.02, 2), "DAP": 0.0}
    b["freight_eur_per_unit"].setdefault("DAP", 0.0)
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
    case["round_limit"] = rng.choice([4, 5, 6]) if "short_rounds" in tags else 10
    forced = "opening_breaks_must_have" in tags
    b["must_haves"] = _must_have(rng, case) if rng.random() < 0.45 or forced else []
    n = rng.randint(2, 3) if case["type"] == "rfq" or "no_bid" in tags else 1
    if n > 1:
        case["type"] = "rfq"
    floor = price * rng.uniform(0.78, 0.97)
    personas = {}
    for i, sup in enumerate(rng.sample(list(pool.values()), n)):
        arch = archetype_for(rng, sup)
        full = floor * rng.uniform(0.95, 1.05)
        p = make_persona(rng, case, sup, full, arch, opening_value=floor * rng.uniform(1.06, 1.32))
        p.no_bid = "no_bid" in tags and i == n - 1
        personas[sup["id"]] = p
    if forced and b["must_haves"]:
        m = b["must_haves"][0]
        p = next(iter(personas.values()))
        bad = [
            o
            for o in case["term_options"].get(m["field"], [])
            if o is not None and not must_haves_ok(case, {m["field"]: o, "unit_price": 1.0}, p.pdf_standard)
        ]
        if bad:
            p.opening[m["field"]] = rng.choice(bad)
    case["suppliers"] = list(personas)
    case["case_id"] = f"case:{name}"
    case["title"] = f"Invented {case['type']} ({goal})"
    case["briefing"] = "An invented case for the lab."
    case.pop("trigger_doc", None)
    case["refs"] = []
    if "case_facts" in tags:  # a should-cost that exists only in this case (hidden cases carry such facts)
        fid = f"cost:{case['parts'][0].split(':', 1)[1]}-case"
        case["facts"] = {fid: {"part": case["parts"][0], "unit_cost": round(floor, 2), "price_unit": 1}}
        case["refs"] = [fid]
        for p in personas.values():
            p.claim_kinds = sorted(set(p.claim_kinds) | {"cost"})
    if "walk_away_best" in tags:
        alt_mode = "walk_away_best"
    elif "current_contract" in tags:
        alt_mode = "current_contract"
    else:
        alt_mode = rng.choice([None, None, "quote"])
    return _finish(case, personas, name, "invented", drivers, tags, rng, alt_mode)


def generate(n, package, seed=0, cases=None, data_share=0.25, edges=None):
    """`n` scenarios: about `data_share` from the unplayed case files, the rest invented.
    Deterministic for a seed. `edges`: force these tags on every invented scenario."""
    rng, pool = random.Random(seed), supplier_pool(package)
    cases = cases or load_cases()
    unplayed = {k: v for k, v in cases.items() if not v.get("hosted") and v.get("set") == "practice"}
    out, tries = [], 0
    while len(out) < n and tries < n * 8:
        tries += 1
        name = f"X{seed:02d}-{len(out):03d}"
        try:
            if unplayed and rng.random() < data_share:
                s = data_scenario(rng, package, pool, rng.choice(list(unplayed.values())), name)
            else:
                s = invent(rng, package, pool, cases, name, edges)
        except (ValueError, KeyError, ZeroDivisionError, TypeError):
            s = None
        if s is not None:
            out.append(s)
    return out


def edge_suite(package, per_edge=6, seed=100):
    """Every edge case `per_edge` times, for the stress test."""
    out = []
    for i, edge in enumerate(EDGES):
        out += generate(per_edge, package, seed=seed + i, data_share=0.0, edges=[edge])
    return out
