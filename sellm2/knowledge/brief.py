# ruff: noqa: E501  (long sentences and messages)
"""What we know about one supplier in one case, built at the first move from the package, the case
file and the opening e-mails. Lean: only what the decisions and the arguments read.

Rules (calibrated Sat 18:30 against all 46 detailed suppliers' texts, docs/PLAN.md section 10):
- signals: a kind's strength is the number of distinct pieces of evidence, at most 3; noise news
  never counts; a news item found by its topic and its words counts once;
- cost of money: measured from cash-discount terms, else job shop or short of cash 0.25, group
  0.065, family 0.09, other 0.10, plus 0.05 for a bad or worsening credit index;
- should-cost: matched on part AND supplier (a case fact first, then its own plant, then a generic
  German estimate times the country factor); another plant's estimate is never this supplier's.
"""

import re
from dataclasses import dataclass, field

from arena_kit.docs import standard_terms

from .source import source

COUNTRY_FACTOR = {"AT": 1.05, "CH": 1.05, "CZ": 0.825, "PL": 0.825, "HU": 0.825, "TR": 0.75, "CN": 0.70}
OWNER_RATE = {"group": 0.065, "family": 0.09}
JOB_SHOP_RATE, OTHER_RATE, CREDIT_SURCHARGE = 0.25, 0.10, 0.05
JOB_SHOP_STAFF = 80
TEXT_RULES = {
    "cash_short": r"pay (?:our invoices )?(?:within|earlier|faster)|payment within \d+ days|\bliquidity\b|\bbanks?\b"
    r"|\bcash\b",
    "wants_volume": r"customers with volume|\bidle\b|short hours|free capacity|fill (?:our|the) (?:capacity|plant)"
    r"|new customers",
    "capacity_tight": r"\ballocation\b|fully booked|capacity is (?:tight|limited)|sold out|full order book",
    "list_price_fixed": r"head-office directive|list conditions|discounts not possible|price list"
    r"|frozen all price reductions|no room on price",
    "material_hedged": r"material covered until",
    "partnership": r"partnership|kept supplying|old price|long-standing|for generations",
    "margin_floor": r"lowers? our margin|cannot sign|below (?:our )?cost",
    "quality_problem": r"\b8D\b|\bcomplaints?\b|\breject|\bdefects?\b",
    "delivery_problem": r"late deliver|\bdelays?\b|\bbacklog\b",
    "ownership_change": r"new owner|successor|succession|restructur|refocus",
    "approval_ladder": r"head office|headquarters|\bapproval\b|pricing committee",
    "informal_costing": r"own spreadsheet|not followed|last updated|does the costing|where we get our index figures",
    "price_claim": r"\b[A-Z][A-Z0-9.-]+ (?:rose|fell) \d+(?:\.\d+)? % in twelve months",
}
RULES = {k: re.compile(v, re.I) for k, v in TEXT_RULES.items()}
NEWS_TOPICS = {
    "cash_short": {"credit_downgrade", "credit_watch", "short_time_work"},
    "wants_volume": {"free_capacity"},
    "capacity_tight": {"allocation", "full_order_book", "big_order", "chip_shortage"},
    "ownership_change": {"new_owner", "succession", "restructuring", "refocus"},
}
OTD_LEVELS = ((55, 3), (65, 2), (75, 1))
PPM_HIGH = 1500
LEGAL_FORM = re.compile(r"\s+(GmbH.*|e\.K\.|KG|AG|s\.r\.o\.|a\.s\.|Kft\.|Sp\. z o\.o\.|Co\., Ltd\.|Ltd\.?)$")


@dataclass
class PartBrief:
    part: str
    price_unit: int = 1
    current_price: float | None = None
    should_cost: dict | None = None  # {ref, unit_cost, plant_specific, confidence_pct}
    low_12m: float | None = None  # its lowest own price of the last twelve months
    below_full_cost: bool = False  # history says it once sold below full cost
    alternatives: int = 0  # other approved sources and rival quotes

    @property
    def own_cost(self):
        """(ref, unit cost per price unit) of its own plant, or None."""
        sc = self.should_cost
        return (sc["ref"], sc["unit_cost"]) if sc and sc["plant_specific"] else None


@dataclass
class Brief:
    sid: str
    coverage: str = "case_only"  # full | thin | case_only
    name: str | None = None
    country: str | None = None
    owner_type: str | None = None
    terms: dict = field(default_factory=dict)  # vendor master: payment_days, skonto, incoterm, lead time
    signals: dict = field(default_factory=dict)  # kind -> strength 1..3
    evidence: dict = field(default_factory=dict)  # kind -> [refs]
    cash_pressure: str | None = None  # low | medium | high (None: we hold no data on it)
    archetype: str = "other"
    cost_of_money: float = 0.08
    rate_basis: str = "our own rate, no data"
    parts: dict = field(default_factory=dict)  # part -> PartBrief
    contact: str | None = None
    warnings: list = field(default_factory=list)

    def signal(self, kind):
        return self.signals.get(kind, 0)

    @property
    def known(self):
        return self.coverage == "full"


# -- helpers ------------------------------------------------------------------------------------------
def _month(m, back):
    y, mo = map(int, m.split("-")[:2])
    n = y * 12 + mo - 1 - back
    return f"{n // 12:04d}-{n % 12 + 1:02d}"


def case_facts(case):
    facts = (case or {}).get("facts") or {}
    if isinstance(facts, list):
        facts = {f["id"]: {k: v for k, v in f.items() if k != "id"} for f in facts if isinstance(f, dict) and f.get("id")}
    return facts if isinstance(facts, dict) else {}


def thread_of(threads, sid):
    t = (threads or {}).get(sid) if isinstance(threads, dict) else None
    if isinstance(t, dict):
        t = t.get("messages")
    return [m for m in t if isinstance(m, dict)] if isinstance(t, list) else []


def first_reply(messages):
    return next((m for m in messages if m.get("from") != "buyer"), None)


def contact_name(message):
    """The name above the 'Role, Company' line of the signature."""
    if not message:
        return None
    role = (message.get("from_name") or "").partition(",")[0].strip()
    lines = [ln.strip() for ln in (message.get("body") or "").splitlines()]
    name = None
    for i, line in enumerate(lines):
        if role and line.startswith(role + ","):
            name = next((x for x in reversed(lines[:i]) if x), None)
    if name and (len(name.split()) > 4 or any(ch.isdigit() for ch in name)):
        return None
    return name


# -- the builder -----------------------------------------------------------------------------------
def build(package, sid, parts, case=None, threads=None):
    """The brief of `sid` for `parts` in `case` (opening e-mails from `threads`). Never raises."""
    b = Brief(sid=sid)
    try:
        _build(b, source(package), sid, list(parts or []), case if isinstance(case, dict) else {}, threads)
    except Exception as e:  # a field less, never a lost move
        b.warnings.append(f"{type(e).__name__}: {e}")
    return b


def _alias(src, sid):
    """A blocked vendor record whose company lives on under a detailed record of the same name."""
    row = src.one("SELECT name, blocked FROM suppliers WHERE id = ?", (sid,))
    if not row or not row.get("blocked"):
        return sid
    stem = LEGAL_FORM.sub("", row.get("name") or "").strip()
    for other in src.q("SELECT id, name FROM suppliers WHERE detail = 'full' AND blocked = 0 ORDER BY id"):
        if stem and LEGAL_FORM.sub("", other["name"]).strip() == stem:
            return other["id"]
    return sid


def _build(b, src, sid, parts, case, threads):
    facts = case_facts(case)
    data_sid = _alias(src, sid) if src.pkg is not None else sid
    row = src.one(
        "SELECT s.*, i.owner_type, i.group_parent, i.staff, i.equity_ratio_pct, i.credit_index, "
        "i.credit_index_12m_ago FROM suppliers s LEFT JOIN supplier_intel i ON i.supplier_id = s.id WHERE s.id = ?",
        (data_sid,),
    )
    if row:
        b.coverage = "full" if row.get("detail") == "full" else "thin"
        b.name, b.country, b.owner_type = row.get("name"), row.get("country"), row.get("owner_type")
        b.terms = {k: row.get(k) for k in ("payment_days", "skonto_days", "skonto_pct", "incoterm")}
        b.terms["lead_time_days"] = row.get("standard_lead_time_days")
    opening = first_reply(thread_of(threads, sid))
    b.contact = contact_name(opening)
    if opening:  # the quote PDF's standard terms win over the vendor master
        for k, v in standard_terms([opening]).items():
            if k in ("payment_days", "incoterm", "lead_time_days"):
                b.terms[k] = v

    # parts ------------------------------------------------------------------------------------
    for pid in parts:
        pb = PartBrief(part=pid, price_unit=int(src.price_units.get(pid) or 1))
        cur = src.one(
            "SELECT * FROM price_conditions WHERE supplier_id = ? AND part_id = ? "
            "ORDER BY (valid_to IS NULL) DESC, valid_from DESC LIMIT 1",
            (data_sid, pid),
        )
        if cur and cur.get("price") is not None:
            pb.current_price = float(cur["price"]) * pb.price_unit / (cur.get("price_unit") or 1)
        pb.should_cost = _should_cost(src, facts, data_sid, sid, pid, b.country, pb.price_unit)
        pb.low_12m, pb.below_full_cost = _recent_low(src, data_sid, pid)
        pb.alternatives = len(src.q("SELECT supplier_id FROM sourcing WHERE part_id = ? AND supplier_id != ?", (pid, data_sid)))
        pb.alternatives += len(src.q("SELECT id FROM quotes WHERE part_id = ? AND supplier_id != ?", (pid, data_sid)))
        b.parts[pid] = pb
    alt = (case.get("buyer") or {}).get("alternative") or {}
    rivals = [s for s in case.get("suppliers") or [] if s != sid and first_reply(thread_of(threads, s))]
    case_alt = bool(rivals) or alt.get("kind") == "current_contract"
    if alt.get("kind") == "quote":
        owner = (facts.get(alt.get("ref")) or src.fact(alt.get("ref")) or {}).get("supplier")
        case_alt = case_alt or owner != sid

    # signals ----------------------------------------------------------------------------------
    items = {}  # kind -> {(ref, label)}

    def add(kind, ref, label):
        items.setdefault(kind, set()).add((ref, label))

    texts = []  # (ref, text)
    if b.coverage != "case_only":
        known_docs = set()
        for d in src.q("SELECT * FROM documents WHERE supplier_id = ? ORDER BY date, id", (data_sid,)) + src.released_rows(
            "documents", data_sid
        ):
            known_docs.add(d["id"])
            texts.append((d["id"], src.text(d["id"])))
            if d.get("asked_pct") not in (None, ""):
                add("price_claim", d["id"], "letter")
        news = src.q("SELECT * FROM news WHERE supplier_id = ? ORDER BY date, id", (data_sid,)) + src.released_rows(
            "news", data_sid
        )
        for n in news:
            if n.get("topic") == "noise":
                continue
            texts.append((n["id"], f"{n.get('headline') or ''}. {n.get('body') or ''}"))
            for kind, topics in NEWS_TOPICS.items():
                if n.get("topic") in topics:
                    add(kind, n["id"], "text")
        for q in src.q("SELECT id, remarks FROM quotes WHERE supplier_id = ? ORDER BY quote_date, id", (data_sid,)):
            if q.get("remarks"):
                texts.append((q["id"], q["remarks"]))
        if b.terms.get("skonto_pct"):
            add("cash_short", f"{data_sid}#skonto", "skonto")
        if row and (row.get("owner_type") == "group" or row.get("group_parent")):
            add("approval_ladder", f"{data_sid}#group", "group")
        for pid in parts:
            hist = src.q(
                "SELECT event_id, note FROM negotiation_history WHERE supplier_id = ? AND part_id = ? ORDER BY date, event_id",
                (data_sid, pid),
            )
            below = [h for h in hist if "below full cost" in (h.get("note") or "").lower()]
            if below:
                add("wants_volume", below[-1]["event_id"], "history")
            pb = b.parts[pid]
            sc = pb.should_cost
            if sc and sc["plant_specific"] and pb.current_price and sc["unit_cost"]:
                if pb.current_price / sc["unit_cost"] <= 1.0:
                    add("margin_floor", f"{sc['ref']}#below", "below")
        card = src.one("SELECT * FROM scorecards WHERE supplier_id = ? ORDER BY quarter DESC LIMIT 1", (data_sid,))
        if card:
            if card.get("colour") in ("amber", "red"):
                add("quality_problem", card["id"], "colour")
            if (card.get("ppm") or 0) > PPM_HIGH:
                add("quality_problem", card["id"], "ppm")
            if card.get("open_8d_overdue"):
                add("quality_problem", card["id"], "8d")
            if card.get("otd_pct") is not None and card["otd_pct"] < OTD_LEVELS[-1][0]:
                add("delivery_problem", card["id"], "otd")
    else:
        known_docs, card = set(), None
    # what the case adds: briefing, trigger document, its own documents and news, the opening e-mail
    if case:
        if case.get("briefing"):
            texts.append((f"{case.get('case_id') or 'case'}#briefing", str(case["briefing"])))
        trigger = case.get("trigger_doc")
        if isinstance(trigger, str) and trigger not in known_docs:
            fact = facts.get(trigger) or {}
            text = src.text(trigger) or fact.get("text") or fact.get("body") or fact.get("title")
            if text and fact.get("supplier") in (None, sid, data_sid):
                texts.append((trigger, text))
        for ref, f in sorted(facts.items()):
            if not isinstance(f, dict) or f.get("supplier") not in (sid, data_sid):
                continue
            if ref.startswith("doc:") and ref not in known_docs:
                texts.append((ref, f.get("text") or f.get("body") or ""))
                if f.get("asked_pct") is not None:
                    add("price_claim", ref, "letter")
            if ref.startswith("news:") and f.get("topic") != "noise":
                texts.append((ref, f"{f.get('headline') or f.get('title') or ''}. {f.get('body') or f.get('text') or ''}"))
                for kind, topics in NEWS_TOPICS.items():
                    if f.get("topic") in topics:
                        add(kind, ref, "text")
    if opening:
        sheets = opening.get("term_sheets") or []
        ref = (sheets[0].get("term_sheet_id") if sheets else None) or f"{sid}#opening"
        texts.append((ref, opening.get("body") or ""))
    for ref, text in texts:
        for kind, rx in RULES.items():
            if text and rx.search(text):
                add(kind, ref, "text")
    otd = (card or {}).get("otd_pct")
    for kind, found in items.items():
        unique = {(ref, "text" if label == "news" else label) for ref, label in found}
        strength = min(3, len(unique))
        if kind == "delivery_problem" and otd is not None:
            strength = max(strength, next((s for limit, s in OTD_LEVELS if otd < limit), 0))
        b.signals[kind] = strength
        b.evidence[kind] = sorted({r for r, _ in unique})

    # economics --------------------------------------------------------------------------------
    if b.coverage == "case_only":
        return
    cash = b.signal("cash_short")
    credit, before = (row or {}).get("credit_index"), (row or {}).get("credit_index_12m_ago")
    if b.terms.get("skonto_pct") or cash >= 2:
        b.cash_pressure = "high"
    elif ((row or {}).get("equity_ratio_pct") or 100) < 25 or (credit or 0) >= 250 or (credit and before and credit > before):
        b.cash_pressure = "medium"
    else:
        b.cash_pressure = "low"
    has_alt = case_alt or any(p.alternatives for p in b.parts.values())
    owner = (row or {}).get("owner_type")
    if ("capacity_tight" in b.signals or "list_price_fixed" in b.signals) and not has_alt:
        b.archetype = "monopolist"
    elif owner == "group":
        b.archetype = "group"
    elif ((row or {}).get("staff") or JOB_SHOP_STAFF) < JOB_SHOP_STAFF or b.cash_pressure == "high":
        b.archetype = "job_shop"
    elif owner == "family":
        b.archetype = "family"
    elif (row or {}).get("category") == "raw material":
        b.archetype = "trader"
    pct, early, net = b.terms.get("skonto_pct"), b.terms.get("skonto_days"), b.terms.get("payment_days")
    if pct and early is not None and net and net > early:
        b.cost_of_money, b.rate_basis = round(pct / 100 * 360 / (net - early), 4), "measured from its cash discount"
        return
    if b.archetype == "job_shop" or cash >= 2:
        rate, b.rate_basis = JOB_SHOP_RATE, "job shop or short of cash"
    else:
        rate, b.rate_basis = OWNER_RATE.get(owner, OTHER_RATE), f"owner type {owner or 'unknown'}"
    if (credit or 0) >= 300 or (credit and before and credit - before >= 20):
        rate += CREDIT_SURCHARGE
        b.rate_basis += ", credit index"
    b.cost_of_money = round(rate, 4)


def _should_cost(src, facts, data_sid, sid, pid, country, price_unit):
    """A case fact first, then the supplier's own plant, then a generic estimate x country factor."""
    number = pid.split(":", 1)[-1]
    for ref, f in sorted(facts.items()):
        if ref.startswith("cost:") and isinstance(f, dict) and f.get("unit_cost") is not None:
            if f.get("part") in (pid, number) and f.get("supplier") in (None, sid, data_sid):
                cost = float(f["unit_cost"]) * price_unit / (f.get("price_unit") or price_unit)
                return {"ref": ref, "unit_cost": round(cost, 2), "cited": round(float(f["unit_cost"]), 2), "plant_specific": True, "confidence_pct": f.get("confidence_pct") or 5, "from_package": False}  # fmt: skip
    rows = src.q("SELECT * FROM should_cost WHERE part_id = ? ORDER BY id", (pid,))
    own = [r for r in rows if r.get("supplier_id") == data_sid]
    generic = [r for r in rows if not r.get("supplier_id")]
    r = (own or generic or [None])[0]
    if r is None or r.get("unit_cost") is None:
        return None
    cost = float(r["unit_cost"]) * price_unit / (r.get("price_unit") or price_unit)
    cited = cost  # the figure the arena checks: the estimate as recorded
    if not own:
        cost *= COUNTRY_FACTOR.get(country, 1.0)
    return {"ref": r["id"], "unit_cost": round(cost, 2), "cited": round(cited, 2), "plant_specific": bool(own),
            "confidence_pct": r.get("confidence_pct") or (5 if own else 15), "from_package": True}  # fmt: skip


def _recent_low(src, sid, pid):
    """Its lowest own price for the part within twelve months of the newest price condition, unless the
    history says it sold below full cost (then it is no price it can go back to)."""
    rows = src.q("SELECT supplier_id, valid_from, valid_to, price, price_unit FROM price_conditions WHERE part_id = ?", (pid,))
    newest = max((r["valid_from"] for r in rows if r.get("valid_from")), default=None)
    below = any(
        "below full cost" in (h.get("note") or "").lower()
        for h in src.q("SELECT note FROM negotiation_history WHERE part_id = ? AND supplier_id = ?", (pid, sid))
    )
    if not newest:
        return None, below
    since = f"{int(newest[:4]) - 1}{newest[4:]}"
    mine = [float(r["price"]) for r in rows if r["supplier_id"] == sid and r.get("price") is not None
            and (not r.get("valid_to") or r["valid_to"] >= since)]  # fmt: skip
    return (min(mine) if mine else None), below
