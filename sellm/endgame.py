# ruff: noqa: E501  (long sentences and messages)
"""How long and how hard we keep asking: a layer over the negotiator, in its own file.

`Persistent` is `sellm.negotiator.Negotiator` with other stop and pace rules. It changes nothing
else: structure, first ask, arguments, e-mails and the close all come from the negotiator, and the
numbers (target, cost estimate) from the calculator and the dossier behind it. It overrides one
method, `plan`, and reads `opening_structure`, `aim`, `value`, `supplier` and `quoted`
(tests/test_endgame.py pins that seam).

Why: with the negotiator of Sat 21:50 the supplier ended six of the ten practice cases itself
(`final_offer` after 3-6 of our messages) - and we ended the other four, three of them by asking a
price it took at once (P11 45.09 against its 45.50, P18 5.50 against 5.60, and P01 in a test). A
price taken at once was too high an ask. Two rules of ours cause that:

- `enough`: in a case with a relationship term we stop when its offer reaches our target, although
  the target rests on a cost estimate that was too high in three of four checkable cases;
- the pace: after the fourth message a step closes most of the remaining gap by itself, also when
  the supplier has stopped answering our steps.

Knobs (all off by default, so `Persistent()` plays exactly like the negotiator):
- `past_target`  keep asking past the relationship target while the supplier is open and its last
                 offer was lower than the one before, down to the target a cost estimate lower by
                 `estimate_error` (5 %) would give
- `creep`        a fraction: no step closes more than this share of the gap to its price (None: the
                 negotiator's pace)
"""

import math

from arena_kit.cost import complete_offer

from .negotiator import EPS, Negotiator, _key

DEFAULTS = dict(past_target=False, estimate_error=0.05, creep=None)


class Persistent(Negotiator):
    def __init__(self, package=None, writer=None, **knobs):
        own = {k: knobs.pop(k) for k in list(knobs) if k in DEFAULTS}
        super().__init__(package, writer=writer, **knobs)
        self.e = {**DEFAULTS, **own}
        self.name = "persistent " + " ".join(f"{k}={v}" for k, v in {**own, **knobs}.items())

    def plan(self, case, v, rival=math.inf):
        plan = super().plan(case, v, rival)
        if self.e["creep"] and v.asks:
            plan = self.crept(case, v, plan)
        if self.e["past_target"] and plan["enough"]:
            plan = self.past(case, v, plan)
        return plan

    # -- stop rule -------------------------------------------------------------------------------
    def low_target(self, case, v, s0, aim):
        """Where our total cost would be lowest if its cost were lower than we estimate by `estimate_error`."""
        full = aim["full_cost"] * (1 - self.e["estimate_error"])
        v0 = self.value(case, v, {**s0, "unit_price": 0.0})
        v1 = self.value(case, v, {**s0, "unit_price": 1.0})
        if v1 <= v0:
            return aim["target"]
        floor = (full - v0) / (v1 - v0)
        supplier = {**self.supplier(case, v), "full_cost": full}
        grid = [floor + (aim["target"] - floor) * i / 250 for i in range(251)]
        return min(grid, key=lambda p: v.c({**s0, "unit_price": p}, supplier))

    def past(self, case, v, plan):
        if v.status != "open" or v.left <= 1:
            return plan
        s0 = self.opening_structure(case, v)
        low = self.low_target(case, v, s0, self.aim(case, v, s0))
        offers = [v.c(v.filled(m["term_sheets"][0]["terms"])) for m in v.theirs if m.get("term_sheets")]
        moved = len(offers) < 2 or offers[-1] < offers[-2] - EPS
        if moved and offers[-1] > v.c({**s0, "unit_price": low}) * (1 + EPS):
            return {**plan, "enough": False}
        return plan

    # -- pace ------------------------------------------------------------------------------------
    def crept(self, case, v, plan):
        """The same ask, but no further up than `creep` of the way to the price it quotes for this
        structure. With nothing visible left to give, the plan says `capped` as the negotiator's does."""
        s = plan["structure"]
        last = complete_offer(case, v.asks[-1])
        if {f: x for f, x in last.items() if f != "unit_price"} != s:
            return plan  # a new structure: the negotiator's price for it stands
        quoted = self.quoted(case, v).get(_key(s))
        if quoted is None or quoted <= last["unit_price"]:
            return plan
        ceiling = quoted * (1 - self.k["keep_below"])
        price = min(
            last["unit_price"] + self.e["creep"] * (quoted - last["unit_price"]), ceiling, plan["sheet"]["unit_price"]
        )
        price = round(max(price, last["unit_price"]), 2)
        if price <= last["unit_price"] + EPS and ceiling >= last["unit_price"] + 0.01:
            price = round(last["unit_price"] + 0.01, 2)  # the smallest step it can see
        return {
            **plan,
            "sheet": complete_offer(case, {**s, "unit_price": price}),
            "capped": price <= last["unit_price"] + EPS,
        }


def make_agent(package=None, writer=None, **knobs):
    """The negotiator with the persistence knobs given (none: identical to `sellm.agent.make_agent`)."""
    from .agent import KNOBS

    return Persistent(package, writer=writer, **{**KNOBS, **knobs})
