# ruff: noqa: E501  (keyword patterns)
"""What the lab's supplier reads out of our e-mail besides term sheets and data: tone, threats,
leaks, questions. Keyword rules - cheap, deterministic, and easy to game, so a strategy that wins
only through wording here proves nothing (docs/PLAN.md section 6)."""

import re

RULES = {
    "ultimatum": r"\bunacceptable\b|\b(or|otherwise) we (will |shall )?(go|move|switch|look|turn) (elsewhere|to (another|a different|other))"
    r"|\btake it or leave it\b|\blast chance\b|\bfinal warning\b|\bwe will terminate\b|\bwalk away\b",
    "hostile": r"\b(ridiculous|outrageous|absurd|greedy|insult(ing)?|exploit(ing)?|rip.?off)\b",
    "appreciation": r"\b(appreciate|grateful|thank you|thanks|long.standing|partnership|valued?|reliable partner|fair(ness)?)\b",
    "urgency": r"\b(urgent(ly)?|asap|as soon as possible|line stop|running out|we need (it|them|the parts) by|immediately|critical shortage)\b",
    "budget": r"\b(our|the) budget (is|of|for|allows)\b|\bwe can (only )?afford\b|\bmaximum we can pay\b",
    "no_alternative": r"\b(no|without an?) (alternative|other (supplier|source)|second source)\b|\bonly supplier\b|\bwe depend on you\b",
    "competition": r"\b(other|alternative|competing|second.source) (offers?|quotes?|suppliers?|bids?)\b|\bbenchmark\b",
    "asks_breakdown": r"\b(cost )?break.?down\b|\bcost (structure|split|bridge|drivers)\b|\bcalculation\b",
    "asks_variants": r"\b(variant|alternative design|design change|cheaper (option|design|material)|value engineering)\b",
    "asks_capacity": r"\b(capacity|lead time|delivery schedule|earliest)\b",
    "asks_margin": r"\b(your )?margin\b",
    "quality": r"\b(ppm|defect|quality|complaint|8d|reject)",
}
COMPILED = {k: re.compile(v, re.I) for k, v in RULES.items()}


def read(body, reader=None):
    """{feature: bool} for one e-mail, plus its length in words. `reader`: an optional callable
    (e.g. an LLM, see `llm_reader`) whose features override the keyword rules."""
    text = body or ""
    out = {k: bool(r.search(text)) for k, r in COMPILED.items()}
    if reader is not None and text.strip():
        try:
            out.update({k: bool(v) for k, v in reader(text).items() if k in out})
        except Exception:  # the keyword rules stand
            pass
    out["leak"] = out["urgency"] or out["budget"] or out["no_alternative"]
    out["questions"] = text.count("?")
    out["words"] = len(text.split())
    return out


LLM_PROMPT = """You are a supplier's sales manager reading a buyer's e-mail. Answer with one JSON object
of booleans, nothing else:
{"ultimatum": threatens to leave or calls the offer unacceptable,
 "hostile": insulting or disrespectful,
 "appreciation": sincere appreciation of the relationship,
 "urgency": reveals the buyer is in a hurry or short of parts,
 "budget": reveals a budget or a maximum price,
 "no_alternative": reveals the buyer has no other supplier,
 "competition": credibly mentions competing offers,
 "asks_breakdown": asks for a cost breakdown,
 "asks_variants": asks for cheaper variants,
 "asks_capacity": asks about capacity or lead time,
 "asks_margin": asks about the supplier's margin,
 "quality": is about quality, defects or ppm}"""


def llm_reader(complete):
    """A reader that asks an LLM (`complete(system, user) -> str`), cached per text."""
    import json
    import re as _re

    cache = {}

    def read_with_llm(text):
        if text not in cache:
            reply = complete(LLM_PROMPT, text[:4000])
            cache[text] = json.loads(_re.search(r"\{.*\}", reply, _re.S).group(0))
        return cache[text]

    return read_with_llm
