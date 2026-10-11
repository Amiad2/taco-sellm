# ruff: noqa: E501  (long sentences and messages)
"""The e-mail around a decision. Code has fixed the term sheets and the argument; this only puts them
into words, so the text can never disagree with a sheet or a figure. Deterministic: identical states
give identical e-mails, and the practice suppliers answer identical e-mails identically. The wording
is the one the scripted probes and every measured run used (an LLM writer scored 71.6 against 72.9
and stopped being repeatable)."""

SIGN = "Best regards\nPurchasing, Hollerau Pumpenwerke"
ORDER = (
    "unit_price",
    "payment_days",
    "contract_months",
    "volume_per_year",
    "lead_time_days",
    "effective_date",
    "incoterm",
    "index_clause",
    "tooling_eur",
    "ppm_commitment",
    "chargeback_eur_per_complaint",
)
HOLD = (
    "thank you for your offer. We are taking it through our internal approval and will confirm shortly. "
    "There are no further changes from our side."
)


def field_text(field, value):
    if field == "unit_price":
        return f"EUR {value:.2f} per unit"
    if field == "payment_days":
        return f"payment {value} days net"
    if field == "contract_months":
        return "a single order" if not value else f"a {value}-month contract"
    if field == "volume_per_year":
        return f"{value:,} units per year"
    if field == "lead_time_days":
        return f"a lead time of {value} days"
    if field == "effective_date":
        return f"valid from {value}"
    if field == "incoterm":
        return f"Incoterm {value}"
    if field == "index_clause":
        if not value:
            return "a fixed price without an index clause"
        return (
            f"an index clause on {value.get('series')} ({round(100 * value.get('material_share', 0))} % material share, "
            f"deadband {value.get('deadband_pct')} %, base month {value.get('base_month')})"
        )
    if field == "tooling_eur":
        return f"tooling of EUR {value:,.2f}"
    if field == "ppm_commitment":
        return f"a quality commitment of {value} ppm"
    if field == "chargeback_eur_per_complaint":
        return f"a chargeback of EUR {value:,.2f} per complaint"
    return f"{field} {value}"


def terms_text(case, terms):
    return ", ".join(field_text(f, terms[f]) for f in ORDER if f in case["negotiable"] and f in terms)


def sheets_text(case, sheets):
    if len(sheets) == 1:
        return terms_text(case, sheets[0])
    return "; ".join(f"option {chr(65 + i)}: {terms_text(case, s)}" for i, s in enumerate(sheets))


def email(case, draft, contact=None):
    """The body for a draft {kind, sheets, arguments, n, flags}."""
    lines = [f"Dear {contact}," if contact else "Dear Sir or Madam,", ""]
    kind, n, flags = draft["kind"], draft.get("n", 0), draft.get("flags") or {}
    terms = sheets_text(case, draft.get("sheets") or [])
    body = []
    if kind == "hold":
        body.append(HOLD)
    elif kind == "take_alternative":
        body.append(f"thank you for the options you sent. We would like to go with your alternative: {terms}. Please confirm.")
    else:
        if n == 0:
            body.append("thank you for your offer and for the reliable cooperation. We would like to settle this in a way that works for both sides.")
            if flags.get("commitment"):
                body.append(f"We can commit for the longer term, which gives you planning security: {flags['commitment']}.")
        elif flags.get("they_moved"):
            body.append("thank you for your reply and for moving towards us.")
        else:
            body.append("thank you for your reply.")
        if flags.get("asked_for_data") and draft.get("arguments"):
            body.append("You asked which figures we rely on. Here is our basis.")
        body += list(draft.get("arguments") or [])
        if n == 0:
            body.append(f"On that basis we propose {terms}.")
        else:
            body.append(f"We can improve our proposal to {terms}. Could you meet us there?")
    return "\n".join([lines[0], lines[1], " ".join(body), "", SIGN])
