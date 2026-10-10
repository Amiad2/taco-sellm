"""profile_text: the dossier in at most 120 words, by template (no LLM), for the negotiator's prompt."""

MAX_WORDS = 120


def _eur(x):
    if x is None:
        return None
    return f"EUR {x / 1e6:.1f} M" if x >= 1e6 else f"EUR {x:,.0f}"


def _pct(x):
    return f"{x:.1f}".rstrip("0").rstrip(".")


def _sentences(d, max_parts, max_signals):
    ident, ec, st = d["identity"], d["economics"], d["standard_terms"]
    who = [x for x in (ident.get("country"), ident.get("owner_type")) if x]
    if ident.get("group_parent"):
        who.append(f"part of {ident['group_parent']}")
    if ident.get("staff"):
        who.append(f"{ident['staff']} staff")
    if ident.get("turnover_eur"):
        who.append(f"turnover {_eur(ident['turnover_eur'])}")
    elif ident.get("turnover_band"):
        who.append(f"turnover {ident['turnover_band']}")
    out = [f"{ident.get('name') or d['supplier_id']}" + (f" ({'; '.join(who)})." if who else ".")]
    spend = ec.get("our_spend_eur") or {}
    if spend:
        fy = max(spend)
        share = ec.get("our_share_of_turnover_pct")
        out.append(
            f"Our spend {fy} {_eur(spend[fy])}" + (f" ({share} % of its turnover)." if share is not None else ".")
        )
    if st.get("payment_days") is not None:
        terms = f"Standard terms: {st['payment_days']} days net"
        if st.get("skonto_pct"):
            terms += f", skonto {st['skonto_pct']} % at {st['skonto_days']} days"
        terms += "".join(f", {x}" for x in [st.get("incoterm")] if x)
        if st.get("lead_time_days") is not None:
            terms += f", lead time {st['lead_time_days']} days"
        out.append(terms + ".")
    out.append(
        f"Cost of money about {_pct(ec['cost_of_money'] * 100)} % a year; cash pressure {ec['cash_pressure']}; "
        f"type {ec['archetype'].replace('_', ' ')}."
    )
    sig = [f"{s['kind'].replace('_', ' ')} ({s['strength']})" for s in d["signals"]][:max_signals]
    out.append("Signals: " + (", ".join(sig) if sig else "none") + ".")
    latest = (d["performance"] or {}).get("latest") or {}
    if latest:
        perf = f"Performance {latest.get('quarter')}: {latest.get('colour')}, OTD {latest.get('otd_pct')} %"
        perf += f", {latest.get('ppm')} ppm"
        if latest.get("open_8d_overdue"):
            perf += f", {latest['open_8d_overdue']} overdue 8D"
        out.append(perf + ".")
    parts = []
    for pid, p in sorted(d["parts"].items())[:max_parts]:
        text = f"{pid} {p.get('description') or ''}".strip()
        price = p.get("current_price")
        if price:
            text += f": price {price['price']} per {price.get('price_unit') or p.get('price_unit') or 1}"
            if p.get("price_to_should_cost") is not None:
                text += f", {p['price_to_should_cost']:.2f}x should-cost"
        parts.append(text)
    if parts:
        out.append("Parts: " + "; ".join(parts) + ".")
    return out


def profile(d):
    for max_parts, max_signals in ((5, 13), (3, 13), (2, 8), (1, 6), (0, 4)):
        text = " ".join(_sentences(d, max_parts, max_signals))
        if len(text.split()) <= MAX_WORDS:
            return text
    return " ".join(text.split()[:MAX_WORDS])
