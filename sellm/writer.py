# ruff: noqa: E501  (long sentences and messages)
"""The e-mail around a decision. Code has fixed the term sheets and the arguments; this module
only puts them into words, so the text can never disagree with a term sheet or a data fact.

`template` writes everything from the decision (deterministic, no LLM). The scripted sandbox probes
that reached 0.95 used texts of this kind (experiments/RESULTS.md).
"""

import re

SIGN = "Best regards\nPurchasing, Hollerau Pumpenwerke"
FIELDS = (
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
ROLE_WORDS = re.compile(
    r"\b(owner|manager|sales|director|head|purchasing|engineer|team|gmbh|ag|kg|s\.r\.o|sp\. z)\b", re.I
)


def render_field(field, value):
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


def render_terms(case, terms):
    """One term sheet as a phrase, the negotiable fields in a fixed order, price first."""
    return ", ".join(render_field(f, terms[f]) for f in FIELDS if f in case["negotiable"] and f in terms)


def render_sheets(case, sheets):
    if len(sheets) == 1:
        return render_terms(case, sheets[0])
    return "; ".join(f"option {chr(65 + i)}: {render_terms(case, s)}" for i, s in enumerate(sheets))


CLOSING = re.compile(
    r"gr[uü](ß|ss)|regards|sincerely|faithfully|cordially|cheers|thank|dank|wishes|servus|moin|hallo|hello|dear|^yours|^best$",
    re.I,
)


def contact(events):
    """The person who signs the supplier's e-mails: the line above the role line of the signature."""
    for message in events:
        if message.get("from") == "buyer" or not message.get("body"):
            continue
        lines = [ln.strip() for ln in message["body"].strip().splitlines() if ln.strip()]
        role = (message.get("from_name") or "").strip()
        for i in range(len(lines) - 1, 0, -1):
            if (role and lines[i] == role) or (not role and ROLE_WORDS.search(lines[i])):
                name = lines[i - 1]
                plain = not any(ch.isdigit() for ch in name) and not ROLE_WORDS.search(name)
                # a signature without a person ("Mit freundlichen Grüßen / Sales, ...") has its closing formula there
                if 1 < len(name.split()) <= 4 and plain and not CLOSING.search(name) and not name.endswith(","):
                    return name
                break
    return None


def template(case, draft, events):
    """The whole e-mail from the decision. `draft`: kind, sheets, arguments, flags (see negotiator)."""
    name = contact(events)
    lines = [f"Dear {name}," if name else "Dear Sir or Madam,", ""]
    kind, n, flags = draft["kind"], draft.get("n", 0), draft.get("flags", {})
    terms = render_sheets(case, draft.get("sheets") or [])
    if kind == "hold":
        lines.append(
            "thank you for your offer. We are taking it through our internal approval and will confirm shortly. "
            "There are no further changes from our side."
        )
    elif kind == "take_alternative":
        lines.append(
            f"thank you for the options you sent. We would like to go with your alternative: {terms}. Please confirm."
        )
    else:
        if n == 0:
            lines.append(
                (flags.get("opening_line") or "thank you for your offer and for the reliable cooperation.")
                + " We would like to settle this in a way that works for both sides."
            )
            if flags.get("commitment"):
                lines.append(
                    f"We can commit for the longer term, which gives you planning security: {flags['commitment']}."
                )
        elif flags.get("they_moved"):
            lines.append("thank you for your reply and for moving towards us.")
        else:
            lines.append("thank you for your reply.")
        if flags.get("asked_for_data") and draft.get("arguments"):
            lines.append("You asked which figures we rely on. Here is our basis.")
        lines += list(draft.get("arguments") or [])
        if n == 0:
            lines.append(f"On that basis we propose {terms}.")
        else:
            lines.append(f"We can improve our proposal to {terms}. Could you meet us there?")
    return "\n".join([lines[0], lines[1], " ".join(lines[2:]), "", SIGN])


def compose(case, draft, events, chat=None):
    """(body, meta). The LLM writer plugs in here; until it has shown a gain on the arena, the
    template writes every e-mail."""
    return template(case, draft, events), {"writer": "template"}
