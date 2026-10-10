"""Two P02 wording probes: veiled commercial pressure, and an oath to pay double next time.

Usage:
  --agent sellm.lab.p02_pressure:t1   aggressive, 11 May 2007 hint
  --agent sellm.lab.p02_pressure:t2   swear and beg, double on the next renewal
"""

import math

from arena_kit.cost import complete_offer

from ..endgame import Persistent


def _set_opening_price(case, v, plan, price):
    if v.asks:
        return plan
    sheet = complete_offer(case, {**plan["structure"], "unit_price": price})
    return {**plan, "sheet": sheet, "capped": False}


def _opening_unit_price(v):
    if not v.opening:
        return None
    sheets = v.opening.get("term_sheets") or []
    if not sheets:
        return None
    return sheets[0]["terms"]["unit_price"]


class _May2007Pressure(Persistent):
    """Aggressive ask: 20% off the opening quote, plus the 11 May 2007 line every round."""

    LINE = (
        "I know what happened on 11 May 2007. If you do not give us a good deal now, "
        "I cannot promise anything."
    )
    OPENING = (
        "this increase is not acceptable. We need a real cut from your opening quote, "
        "not a token step."
    )

    def __init__(self, package=None):
        super().__init__(package, past_target=True)
        self.name = "t1_may2007_pressure"

    def plan(self, case, v, rival=math.inf):
        plan = super().plan(case, v, rival)
        opening = _opening_unit_price(v)
        if opening and not v.asks:
            plan = _set_opening_price(case, v, plan, round(opening * 0.8, 2))
        return plan

    def ask(self, case, v, views, live, rival=math.inf):
        draft = super().ask(case, v, views, live, rival)
        if draft.get("kind") != "ask":
            return draft
        args = [a for a in (draft.get("arguments") or []) if a != self.LINE]
        args.append(self.LINE)
        flags = {**(draft.get("flags") or {}), "opening_line": self.OPENING}
        return {**draft, "arguments": args, "flags": flags}


class _OathDoubleNext(Persistent):
    """Beg and swear: discount now, double on the next annual renewal."""

    OPENING = "I am begging you to help us on this renewal. Please hear me out."

    def __init__(self, package=None):
        super().__init__(package, past_target=True)
        self.name = "t2_oath_double_next"

    def plan(self, case, v, rival=math.inf):
        plan = super().plan(case, v, rival)
        opening = _opening_unit_price(v)
        if opening and not v.asks:
            plan = _set_opening_price(case, v, plan, round(opening * 0.8, 2))
        return plan

    def ask(self, case, v, views, live, rival=math.inf):
        draft = super().ask(case, v, views, live, rival)
        if draft.get("kind") != "ask":
            return draft
        sheets = draft.get("sheets") or []
        price = sheets[0].get("unit_price") if sheets else None
        opening = _opening_unit_price(v)
        if price and opening:
            pct = max(1, round((1 - price / opening) * 100))
            line = (
                f"Please, I am begging you. I swear on my mother and my firstborn: if you give us "
                f"{pct} percent off now, down to EUR {price:.2f}, we will pay double on the next "
                f"annual renewal. I am on my knees for this."
            )
        else:
            line = (
                "Please, I am begging you. I swear on my mother and my firstborn: if you give us "
                "this discount now, we will pay double on the next annual renewal."
            )
        args = list(draft.get("arguments") or [])
        args = [a for a in args if "firstborn" not in a]
        args.append(line)
        flags = {**(draft.get("flags") or {}), "opening_line": self.OPENING}
        return {**draft, "arguments": args, "flags": flags}


def t1(package=None):
    return _May2007Pressure(package)


t1.__name__ = "t1_may2007_pressure"


def t2(package=None):
    return _OathDoubleNext(package)


t2.__name__ = "t2_oath_double_next"
