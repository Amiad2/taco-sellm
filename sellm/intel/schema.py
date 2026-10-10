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
