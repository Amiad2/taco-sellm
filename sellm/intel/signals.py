"""Signals: what a supplier needs or fears, read from its texts and data by fixed rules (docs/PLAN.md s. 10)."""

import re

from . import derive

EXCERPT_CHARS = 160
SENTENCE = re.compile(r"(?<=[.!?'])\s+|\n+")
TEXT_RULES = {
    "cash_short": r"pay (?:our invoices )?(?:within|earlier|faster)|payment within \d+ days|\bliquidity\b|\bbanks?\b"
    r"|\bcash\b",
    "wants_volume": r"customers with volume|\bidle\b|short hours|free capacity|fill (?:our|the) (?:capacity|plant)"
    r"|new customers",
    "capacity_tight": r"\ballocation\b|fully booked|capacity is (?:tight|limited)|sold out|full order book",
    "list_price_fixed": r"head-office directive|list conditions|discounts not possible|price list"
    r"|frozen all price reductions|no room on price",
    # Sunday release, a steel trader's letter: "we bought our bright and cold-drawn bar requirement forward at
    # fixed prices until June 2027"
    "material_hedged": r"material covered until|bought .{0,80}forward|(?:covered|bought|secured) at fixed prices"
    r"|at fixed prices until",
    # Sunday release, two letters: "our price list applies without exception ... We remain open to discuss payment
    # terms, call-off planning and contract length"
    "wants_planning": r"open to discuss[^.]{0,80}call-off planning",
    "partnership": r"partnership|kept supplying|old price|long-standing|for generations",
    "margin_floor": r"lowers? our margin|cannot sign|below (?:our )?cost",
    "quality_problem": r"\b8D\b|\bcomplaints?\b|\breject|\bdefects?\b",
    "delivery_problem": r"late deliver|\bdelays?\b|\bbacklog\b",
    "ownership_change": r"new owner|successor|succession|restructur|refocus",
    "approval_ladder": r"head office|headquarters|\bapproval\b|pricing committee",
    "informal_costing": r"own spreadsheet|not followed|last updated|does the costing|where we get our index figures",
    "price_claim": r"\b[A-Z][A-Z0-9.-]+ (?:rose|fell) \d+(?:\.\d+)? % in twelve months",
}
SUBJECT_RULES = {}
NEWS_TOPICS = {
    "cash_short": {"credit_downgrade", "credit_watch", "short_time_work", "insolvency"},
    "wants_volume": {"free_capacity"},
    "capacity_tight": {"allocation", "full_order_book", "big_order", "chip_shortage"},
    "ownership_change": {"new_owner", "succession", "restructuring", "refocus", "acquisition"},
}
# News that ends a shortage: capacity news older than it no longer counts (Sunday release: "semiconductor supply
# back to normal" for a supplier that had warned of a chip shortage in March)
EASES = {"supply_normalises"}
DRIVER_CLAIM = re.compile(
    r"(?P<series>[A-Z][A-Z0-9.-]+) (?P<dir>rose|fell) (?P<chg>\d+(?:\.\d+)?) % in twelve months and is "
    r"(?P<share>\d+(?:\.\d+)?) % of our cost",
    re.I,
)
OTD_LEVELS = ((55, 3), (65, 2), (75, 1))  # latest on-time delivery below x % -> strength
PPM_HIGH = 1500
COMPILED = {k: re.compile(v, re.I) for k, v in TEXT_RULES.items()}
SUBJECTS = {k: re.compile(v, re.I) for k, v in SUBJECT_RULES.items()}


def excerpt(text, rx):
    for sentence in SENTENCE.split(text or ""):
        if rx.search(sentence):
            s = sentence.strip()
            return s if len(s) <= EXCERPT_CHARS else s[: EXCERPT_CHARS - 3].rstrip() + "..."
    return ""


def text_sources(d):
    """(id, date, subject, text) of every text that may carry a signal: never noise or market news."""
    out = [(x["id"], x["date"] or "", x.get("subject") or "", x.get("text") or "") for x in d["documents"]]
    out += [
        (n["id"], n["date"] or "", "", f"{n['headline'] or ''}. {n['body'] or ''}") for n in d["news"] if not n["noise"]
    ]
    out += [(q["quote_id"], q["date"] or "", "", q["remarks"] or "") for q in d["own_quotes"] if q.get("remarks")]
    return out


def _structured(d):
    """{kind: [(id, label, description)]} from the numbers and the vendor master."""
    sid, items = d["supplier_id"], {}

    def add(kind, ref, label, text):
        items.setdefault(kind, []).append((ref, label, text))

    st, ident = d["standard_terms"], d["identity"]
    if st.get("skonto_pct"):
        add(
            "cash_short",
            f"{sid}#skonto",
            "skonto",
            f"Skonto {st['skonto_pct']} % at {st['skonto_days']} days instead of {st['payment_days']}.",
        )
    eased = max(((n["date"] or "") for n in d["news"] if n["topic"] in EASES), default="")
    for n in d["news"]:
        for kind, topics in NEWS_TOPICS.items():
            if not n["noise"] and n["topic"] in topics:
                if kind == "capacity_tight" and eased and (n["date"] or "") < eased:
                    continue
                add(kind, n["id"], "news", n["headline"] or "")
    if ident.get("owner_type") == "group" or ident.get("group_parent"):
        add(
            "approval_ladder",
            f"{sid}#group",
            "group",
            f"Part of a group{': ' + ident['group_parent'] if ident.get('group_parent') else ''}.",
        )
    for pid, part in sorted(d["parts"].items()):
        events = [e for e in part["history"]["events"] if "below full cost" in (e.get("note") or "").lower()]
        if events:
            add("wants_volume", events[-1]["event_id"], "history", f"{pid}: '{events[-1]['note']}'")
        sc, ratio = part["should_cost"], part["price_to_should_cost"]
        if sc and sc["plant_specific"] and ratio is not None and ratio <= 1.0:
            add("margin_floor", f"{sc['id']}#below", "below", f"{pid} is priced at {ratio:.2f} x its should-cost.")
    for doc in d["documents"]:
        if doc.get("asked_pct") is not None:
            add(
                "price_claim",
                doc["id"],
                "letter",
                f"Letter asks {doc['asked_pct']} % from {doc.get('effective_date')}.",
            )
    latest = (d["performance"] or {}).get("latest") or {}
    if latest:
        if latest.get("colour") in ("amber", "red"):
            add("quality_problem", latest["id"], "colour", f"Scorecard {latest['quarter']} is {latest['colour']}.")
        if (latest.get("ppm") or 0) > PPM_HIGH:
            add("quality_problem", latest["id"], "ppm", f"{latest['ppm']} ppm in {latest['quarter']}.")
        if latest.get("open_8d_overdue"):
            add("quality_problem", latest["id"], "8d", f"{latest['open_8d_overdue']} overdue 8D report(s).")
        if latest.get("otd_pct") is not None and latest["otd_pct"] < OTD_LEVELS[-1][0]:
            add(
                "delivery_problem",
                latest["id"],
                "otd",
                f"On-time delivery {latest['otd_pct']} % in {latest['quarter']}.",
            )
    return items


def detect(d, extra=()):
    """The dossier's signals: text rules over its texts (plus `extra` (id, date, subject, text)) and data rules."""
    items = _structured(d)
    texts = {}
    for ref, date, subject, text in [*text_sources(d), *extra]:
        for kind, rx in COMPILED.items():
            sub = SUBJECTS.get(kind)
            if rx.search(text) or (sub and sub.search(subject)):
                items.setdefault(kind, []).append((ref, "text", ""))
                texts.setdefault(kind, []).append((date, ref, excerpt(text, rx) or subject))
    otd = ((d["performance"] or {}).get("latest") or {}).get("otd_pct")
    signals = []
    for kind in sorted(items):
        # one piece of evidence per text: a news item found by its topic and by its words counts once
        unique = sorted({(ref, "text" if label == "news" else label) for ref, label, _ in items[kind]})
        strength = min(3, len(unique))
        if kind == "delivery_problem" and otd is not None:
            strength = max(strength, next((s for limit, s in OTD_LEVELS if otd < limit), 0))
        if texts.get(kind):
            quote = max(texts[kind])[2]
        else:
            quote = next(t for _, _, t in items[kind] if t)
        signals.append(
            {"kind": kind, "strength": strength, "evidence": sorted({r for r, _ in unique}), "excerpt": quote}
        )
    return signals


def apply(d, extra=()):
    """Signals, then what follows from them: cash pressure, archetype, cost of money."""
    d["signals"] = detect(d, extra)
    strength = {s["kind"]: s["strength"] for s in d["signals"]}
    cash = strength.get("cash_short", 0)
    pressure = derive.cash_pressure(d["identity"], d["standard_terms"], cash)
    has_alt = any(p["alternatives"] for p in d["parts"].values())
    from_stock = any("from stock" in (q.get("remarks") or "").lower() for q in d["own_quotes"])
    arche, why = derive.archetype(d["identity"], pressure, set(strength), has_alt, from_stock)
    rate, basis = derive.cost_of_money(d["identity"], d["standard_terms"], arche, cash)
    d["economics"].update(
        cash_pressure=pressure, archetype=arche, archetype_basis=why, cost_of_money=rate, cost_of_money_basis=basis
    )
    return d


def report(dossiers):
    """Markdown: every signal of every supplier with its evidence, for a human to check (verification V11)."""
    lines = ["# Signals report", "", "Mark each line right or wrong. Kinds and rules: docs/PLAN.md section 10.", ""]
    for d in dossiers:
        ec = d["economics"]
        lines.append(f"## {d['supplier_id']} {d['identity'].get('name') or ''}")
        lines.append(
            f"cash pressure {ec['cash_pressure']} · {ec['archetype']} ({ec['archetype_basis']}) · "
            f"cost of money {ec['cost_of_money']} ({ec['cost_of_money_basis']})"
        )
        lines.append("")
        for s in d["signals"]:
            lines.append(f'- [ ] **{s["kind"]}** {s["strength"]} - {", ".join(s["evidence"])} - "{s["excerpt"]}"')
        if not d["signals"]:
            lines.append("- (no signals)")
        lines.append("")
    return "\n".join(lines) + "\n"
