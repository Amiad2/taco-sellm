"""The dossier contract, schema v1 (docs/PLAN.md section 10): names, enums, an empty dossier, a validator."""

SCHEMA_VERSION = 1
COVERAGE = ("full", "thin", "case_only")
CASH_PRESSURE = ("low", "medium", "high")
ARCHETYPES = ("family", "group", "job_shop", "monopolist", "trader", "other")
SIGNAL_KINDS = (
    "cash_short",
    "wants_volume",
    "capacity_tight",
    "list_price_fixed",
    "material_hedged",
    "partnership",
    "margin_floor",
    "quality_problem",
    "delivery_problem",
    "ownership_change",
    "approval_ladder",
    "price_claim",
    "informal_costing",
)
CORE_FIELDS = (
    "schema_version",
    "supplier_id",
    "coverage",
    "standard_terms",
    "economics",
    "signals",
    "parts",
    "citable",
)
STANDARD_TERMS_SOURCES = ("vendor_master", "quote_pdf", None)
DEFAULT_COST_OF_MONEY = 0.10

IDENTITY_KEYS = (
    "name",
    "country",
    "category",
    "legal_form",
    "founded",
    "owner_type",
    "group_parent",
    "staff",
    "turnover_eur",
    "turnover_band",
    "turnover_estimated",
    "equity_ratio_pct",
    "credit_index",
    "credit_index_12m_ago",
    "vda63_grade",
    "certifications",
    "abc_class",
    "supplier_since",
    "blocked",
)
STANDARD_TERMS_KEYS = ("payment_days", "skonto_days", "skonto_pct", "incoterm", "lead_time_days", "source")
ECONOMICS_KEYS = (
    "cost_of_money",
    "cost_of_money_basis",
    "cash_pressure",
    "archetype",
    "archetype_basis",
    "our_spend_eur",
    "our_share_of_turnover_pct",
    "we_pay_late_days",
    "discount_taken_share_pct",
)
PART_KEYS = (
    "description",
    "category",
    "material_group",
    "grade",
    "uom",
    "price_unit",
    "planned_lead_time_days",
    "abc_class",
    "sourcing",
    "current_price",
    "history",
    "should_cost",
    "floor_estimate",
    "price_to_should_cost",
    "drivers",
    "forecast",
    "alternatives",
)
TOP_KEYS = (
    "schema_version",
    "supplier_id",
    "coverage",
    "built_from",
    "identity",
    "contact",
    "standard_terms",
    "economics",
    "signals",
    "contract",
    "parts",
    "performance",
    "citable",
    "documents",
    "news",
    "market_news",
    "stated_drivers",
    "opening_offer",
    "case_facts",
    "own_quotes",
    "profile_text",
    "warnings",
)


def empty_history():
    return {
        "events": [],
        "mean_asked_pct": None,
        "mean_settled_pct": None,
        "mean_give_pct": None,
        "below_full_cost": False,
    }


def empty_part():
    part = dict.fromkeys(PART_KEYS)
    part.update(history=empty_history(), drivers=[], alternatives=[])
    return part


def empty_dossier(supplier_id, part_ids=()):
    """A valid dossier that knows nothing yet: the rules' outcome for a supplier without data."""
    identity = dict.fromkeys(IDENTITY_KEYS)
    identity.update(certifications=[], turnover_estimated=False, blocked=False)
    economics = dict.fromkeys(ECONOMICS_KEYS)
    economics.update(
        cost_of_money=DEFAULT_COST_OF_MONEY,
        cost_of_money_basis="rule: no data on this supplier",
        cash_pressure="low",
        archetype="other",
        archetype_basis="no data",
        our_spend_eur={},
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "supplier_id": supplier_id,
        "coverage": "case_only",
        "built_from": {"package": None, "facts_sha256": None, "sunday_release": False, "case_id": None},
        "identity": identity,
        "contact": None,
        "standard_terms": dict.fromkeys(STANDARD_TERMS_KEYS),
        "economics": economics,
        "signals": [],
        "contract": None,
        "parts": {p: empty_part() for p in part_ids},
        "performance": None,
        "citable": [],
        "documents": [],
        "news": [],
        "market_news": [],
        "stated_drivers": [],
        "opening_offer": None,
        "case_facts": {},
        "own_quotes": [],
        "profile_text": "",
        "warnings": [],
    }


def _num(x):
    return isinstance(x, int | float) and not isinstance(x, bool)


def _non_finite(obj, path="d"):
    if isinstance(obj, float) and (obj != obj or obj in (float("inf"), float("-inf"))):
        yield path
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield from _non_finite(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _non_finite(v, f"{path}[{i}]")


def _keys(errors, obj, keys, where):
    if not isinstance(obj, dict):
        errors.append(f"{where}: not an object")
        return False
    missing, extra = set(keys) - set(obj), set(obj) - set(keys)
    if missing:
        errors.append(f"{where}: missing {sorted(missing)}")
    if extra:
        errors.append(f"{where}: unknown {sorted(extra)}")
    return not missing


def _list_of_dicts(errors, obj, where, required=()):
    if not isinstance(obj, list):
        errors.append(f"{where}: not a list")
        return
    for i, item in enumerate(obj):
        if not isinstance(item, dict):
            errors.append(f"{where}[{i}]: not an object")
        elif missing := [k for k in required if k not in item]:
            errors.append(f"{where}[{i}]: missing {missing}")


def _validate_part(errors, pid, part):
    where = f"parts.{pid}"
    if not pid.startswith("part:"):
        errors.append(f"{where}: key is not a part ID")
    if not _keys(errors, part, PART_KEYS, where):
        return
    if part["price_unit"] is not None and not isinstance(part["price_unit"], int):
        errors.append(f"{where}.price_unit: not an integer")
    if part["current_price"] is not None and not _num((part["current_price"] or {}).get("price")):
        errors.append(f"{where}.current_price: no numeric price")
    _keys(errors, part["history"], tuple(empty_history()), f"{where}.history")
    sc = part["should_cost"]
    if sc is not None and not (isinstance(sc, dict) and isinstance(sc.get("id"), str) and _num(sc.get("unit_cost"))):
        errors.append(f"{where}.should_cost: needs id and numeric unit_cost")
    fl = part["floor_estimate"]
    if fl is not None:
        if not (isinstance(fl, dict) and all(_num(fl.get(k)) for k in ("value", "low", "high"))):
            errors.append(f"{where}.floor_estimate: needs numeric value, low, high")
        elif not fl["low"] <= fl["value"] <= fl["high"]:
            errors.append(f"{where}.floor_estimate: value outside its band")
        if not isinstance((fl or {}).get("basis"), str):
            errors.append(f"{where}.floor_estimate: no basis")
    if part["price_to_should_cost"] is not None and not _num(part["price_to_should_cost"]):
        errors.append(f"{where}.price_to_should_cost: not a number")
    _list_of_dicts(errors, part["drivers"], f"{where}.drivers", ("series", "weight", "change_12m_pct", "ids_12m"))
    _list_of_dicts(errors, part["alternatives"], f"{where}.alternatives", ("supplier_id", "private"))
    if any(isinstance(a, dict) and a.get("private") is not True for a in part["alternatives"] or []):
        errors.append(f"{where}.alternatives: every alternative is buyer-private")


def validate(d):
    """Every way `d` breaks the schema v1 contract, as readable strings; empty when it is valid."""
    errors = []
    if not _keys(errors, d, TOP_KEYS, "dossier"):
        return errors
    if d["schema_version"] != SCHEMA_VERSION:
        errors.append(f"schema_version: {d['schema_version']!r}")
    if not (isinstance(d["supplier_id"], str) and d["supplier_id"].startswith("sup:")):
        errors.append(f"supplier_id: {d['supplier_id']!r}")
    if d["coverage"] not in COVERAGE:
        errors.append(f"coverage: {d['coverage']!r}")
    if _keys(errors, d["built_from"], ("package", "facts_sha256", "sunday_release", "case_id"), "built_from"):
        if not isinstance(d["built_from"]["sunday_release"], bool):
            errors.append("built_from.sunday_release: not a bool")
    if _keys(errors, d["identity"], IDENTITY_KEYS, "identity"):
        ident = d["identity"]
        if not isinstance(ident["certifications"], list):
            errors.append("identity.certifications: not a list")
        if not isinstance(ident["turnover_estimated"], bool) or not isinstance(ident["blocked"], bool):
            errors.append("identity: turnover_estimated and blocked are bools")
    if d["contact"] is not None:
        _keys(errors, d["contact"], ("name", "role", "company", "address"), "contact")
    if _keys(errors, d["standard_terms"], STANDARD_TERMS_KEYS, "standard_terms"):
        st = d["standard_terms"]
        if st["source"] not in STANDARD_TERMS_SOURCES:
            errors.append(f"standard_terms.source: {st['source']!r}")
        for k in ("payment_days", "skonto_days", "skonto_pct", "lead_time_days"):
            if st[k] is not None and not _num(st[k]):
                errors.append(f"standard_terms.{k}: not a number")
    if _keys(errors, d["economics"], ECONOMICS_KEYS, "economics"):
        ec = d["economics"]
        if not (_num(ec["cost_of_money"]) and 0 < ec["cost_of_money"] <= 1):
            errors.append(f"economics.cost_of_money: {ec['cost_of_money']!r} is not in (0, 1]")
        if ec["cash_pressure"] not in CASH_PRESSURE:
            errors.append(f"economics.cash_pressure: {ec['cash_pressure']!r}")
        if ec["archetype"] not in ARCHETYPES:
            errors.append(f"economics.archetype: {ec['archetype']!r}")
        if not isinstance(ec["our_spend_eur"], dict) or not all(_num(v) for v in ec["our_spend_eur"].values()):
            errors.append("economics.our_spend_eur: not {fiscal year: number}")
    _list_of_dicts(errors, d["signals"], "signals", ("kind", "strength", "evidence", "excerpt"))
    kinds = [s.get("kind") for s in d["signals"] if isinstance(s, dict)]
    if len(kinds) != len(set(kinds)):
        errors.append("signals: a kind appears twice")
    for s in d["signals"] if isinstance(d["signals"], list) else []:
        if not isinstance(s, dict):
            continue
        if s.get("kind") not in SIGNAL_KINDS:
            errors.append(f"signals: unknown kind {s.get('kind')!r}")
        if s.get("strength") not in (1, 2, 3):
            errors.append(f"signals.{s.get('kind')}: strength {s.get('strength')!r}")
        ev = s.get("evidence")
        if not (isinstance(ev, list) and ev and all(isinstance(e, str) for e in ev) and ev == sorted(set(ev))):
            errors.append(f"signals.{s.get('kind')}: evidence must be a non-empty, sorted, unique list of IDs")
    if d["contract"] is not None and not isinstance(d["contract"], dict):
        errors.append("contract: not an object")
    if not isinstance(d["parts"], dict):
        errors.append("parts: not an object")
    else:
        for pid, part in d["parts"].items():
            _validate_part(errors, pid, part)
    if d["performance"] is not None and not isinstance(d["performance"], dict):
        errors.append("performance: not an object")
    _list_of_dicts(errors, d["citable"], "citable", ("ids", "kind"))
    _list_of_dicts(errors, d["documents"], "documents", ("id", "date", "kind", "text"))
    _list_of_dicts(errors, d["news"], "news", ("id", "date", "topic", "headline", "noise"))
    _list_of_dicts(errors, d["market_news"], "market_news", ("id", "date", "headline"))
    _list_of_dicts(errors, d["stated_drivers"], "stated_drivers", ("series", "stated_change_pct", "matches"))
    _list_of_dicts(errors, d["own_quotes"], "own_quotes", ("quote_id", "part_id", "unit_price"))
    if d["opening_offer"] is not None and not isinstance(d["opening_offer"], dict):
        errors.append("opening_offer: not an object")
    if not isinstance(d["case_facts"], dict):
        errors.append("case_facts: not an object")
    if not isinstance(d["profile_text"], str):
        errors.append("profile_text: not a string")
    if not (isinstance(d["warnings"], list) and all(isinstance(w, str) for w in d["warnings"])):
        errors.append("warnings: not a list of strings")
    errors += [f"{p}: not a finite number" for p in _non_finite(d)]
    return errors
