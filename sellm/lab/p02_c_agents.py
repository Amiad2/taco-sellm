"""P02 real-supplier probes, using only terms and facts that exist in P02.

Usage: --agent sellm.lab.p02_c_agents:c1   (c1 through c5)
"""

import math

from arena_kit.cost import complete_offer

from ..endgame import Persistent
from ..negotiator import Thread
from .dials import DialNegotiator


def _set_opening_price(case, v, plan, price):
    """Set the first ask explicitly; floor_share is ignored when a should-cost exists."""
    if v.asks:
        return plan
    sheet = complete_offer(case, {**plan["structure"], "unit_price": price})
    return {**plan, "sheet": sheet, "capped": False}


def c1(package=None):
    """Control: keep asking past our target while Nordmark is still moving."""
    return Persistent(package, past_target=True)


c1.__name__ = "c1_past_target"


class _CurrentPriceAnchor(DialNegotiator):
    """Open at P02's actual current unit price, rather than a price from another case."""

    def __init__(self, package=None):
        super().__init__(package)
        self.name = "c2_current_price_anchor"

    def plan(self, case, v, rival=math.inf):
        plan = super().plan(case, v, rival)
        return _set_opening_price(case, v, plan, case["buyer"]["current_unit_price"])


def c2(package=None):
    return _CurrentPriceAnchor(package)


c2.__name__ = "c2_current_price_anchor"


def c3(package=None):
    """Test Nordmark's explicit 30-day payment alternative."""
    return DialNegotiator(package, pay_days=30)


c3.__name__ = "c3_fast_payment"


class _AskForTrade(DialNegotiator):
    """Ask what commercial concession would unlock a lower price."""

    def __init__(self, package=None):
        super().__init__(package)
        self.name = "c4_ask_for_trade"
        self._asked = set()

    def decide(self, case, threads, focus=None):
        draft = super().decide(case, threads, focus=focus)
        if draft is None or draft.get("supplier_id") is None:
            return draft
        sid = draft["supplier_id"]
        v = Thread(case, sid, threads.get(sid, []))
        if len(v.asks) == 1 and sid not in self._asked:
            self._asked.add(sid)
            args = list(draft.get("arguments") or [])
            args.append(
                "We cannot approve the proposed increase at this level. What specific change on our side, "
                "such as 30-day payment, would let you reduce the price further? Please identify the "
                "commercial trade needed for a sustainable agreement."
            )
            draft = {**draft, "arguments": args}
        return draft


def c4(package=None):
    return _AskForTrade(package)


c4.__name__ = "c4_ask_for_trade"


class _FirmCombo(Persistent):
    """Test a firm 20% price target plus a real commercial trade question."""

    def __init__(self, package=None):
        super().__init__(package, past_target=True)
        self.name = "c5_firm_target_and_trade"
        self._asked = set()

    def plan(self, case, v, rival=math.inf):
        plan = super().plan(case, v, rival)
        if not v.asks and v.opening:
            opening_price = v.opening["term_sheets"][0]["terms"]["unit_price"]
            plan = _set_opening_price(case, v, plan, round(opening_price * 0.8, 2))
        return plan

    def decide(self, case, threads, focus=None):
        draft = super().decide(case, threads, focus=focus)
        if draft is None or draft.get("supplier_id") is None:
            return draft
        sid = draft["supplier_id"]
        v = Thread(case, sid, threads.get(sid, []))
        if len(v.asks) == 1 and sid not in self._asked:
            self._asked.add(sid)
            args = list(draft.get("arguments") or [])
            args.append(
                "A 20% reduction from your opening quote is our firm commercial target. If that is not "
                "workable, please state the best price you can support with 30-day payment. We will "
                "review that against the current contract and the second-source quote before approval."
            )
            draft = {**draft, "arguments": args}
        return draft


def c5(package=None):
    return _FirmCombo(package)


c5.__name__ = "c5_firm_target_and_trade"
