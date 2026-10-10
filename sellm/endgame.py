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
- `past_creep`   a fraction, used with `past_target` once its offer is at or below our target: no
                 step closes more than this share of the gap (0: the smallest visible step, we
                 hold our price). Whatever happens there, its standing offer is one the negotiator
                 would have accepted already
- `creep`        a fraction: no step closes more than this share of the gap to its price (None: the
                 negotiator's pace)
- `push_final`, `fast_pay`, `pay_probe`, `signal_facts`, `soft_give`: see DEFAULTS; tests of what a
                 supplier gives for what it wants (experiments/PERSISTENCE.md section 6)
- `zone`         a fraction: once the supplier repeats its offer (`stall_after` times) we ask this
                 share below it at once. Suppliers took asks about 1 % below their standing offer
                 (P01 1.03 %, P11 0.90 %, P18 1.8 %; P11 not 1.08 %), and one that stalls says
                 `final_offer` a few messages later (P04 after 3, P11 after 7) - creeping towards it
                 then loses the race (P11: 0.710 against 0.778)
"""

import math

from arena_kit.cost import complete_offer

from . import calculator
from .negotiator import EPS, Negotiator, _key, log

DEFAULTS = dict(
    past_target=False,
    estimate_error=0.05,
    past_creep=None,
    creep=None,
    zone=None,
    stall_after=1,
    push_final=None,  # a fraction: after its first final offer, ask once this share below it instead of accepting
    fast_pay=False,  # a supplier the dossier calls short of cash: the fastest payment in the first ask
    pay_probe=False,  # first ask as two offers of equal cost to us that differ in payment days only
    signal_facts=False,  # a supplier that wants volume hears the forecast first
    soft_give=False,  # ... and is offered a fixed call-off schedule in the first e-mail (not binding)
)
SOFT_GIVE = (
    "We can give you a fixed call-off schedule and a rolling twelve-month forecast, so that you can plan your capacity."
)
PREFER = {"wants_volume": ("fc",)}  # dossier signal -> the kinds of fact (sellm/claims.py) that speak to it


class Persistent(Negotiator):
    def __init__(self, package=None, writer=None, **knobs):
        own = {k: knobs.pop(k) for k in list(knobs) if k in DEFAULTS}
        super().__init__(package, writer=writer, **knobs)
        self.e = {**DEFAULTS, **own}
        self.name = "persistent " + " ".join(f"{k}={v}" for k, v in {**own, **knobs}.items())

    # -- what the supplier wants (tests of Sat 23:15, see experiments/PERSISTENCE.md section 6) --------
    def signal(self, case, v, kind):
        found = self.intel(case, v)
        if found.get("coverage") != "full":
            return 0
        return max(
            (sig.get("strength") or 1 for sig in found.get("signals") or [] if sig.get("kind") == kind), default=0
        )

    def opening_structure(self, case, v):
        s = super().opening_structure(case, v)
        if self.e["fast_pay"] and "payment_days" in s:
            if self.signal(case, v, "cash_short") or self.cash(case, v) in ("medium", "high"):
                days = [
                    d
                    for d in case.get("term_options", {}).get("payment_days") or []
                    if v.valid({**s, "payment_days": d, "unit_price": 1.0})
                ]
                if days and min(days) < s["payment_days"]:
                    s = {**s, "payment_days": min(days)}
                    self._memo[(case.get("case_id"), v.sid, "s0")] = s
        return s

    def persona(self, case, v):
        """Which personas this supplier has and what follows (sellm/personas.py): a description of the rules, not a rule."""
        from .personas import describe

        return describe(self.intel(case, v))

    def ask(self, case, v, views, live, rival=math.inf):
        draft = super().ask(case, v, views, live, rival)
        if draft.get("kind") != "ask" or v.asks:
            return draft
        key = (case.get("case_id"), v.sid, "persona-logged")
        if key not in self._memo:  # once per supplier, in the run's log: why the first ask looks as it does
            self._memo[key] = True
            for line in self.persona(case, v)["lines"]:
                log.info("%s %s: %s", case.get("case_id"), v.sid, line)
        sheet = draft["sheets"][0]
        if self.e["pay_probe"] and len(draft["sheets"]) == 1 and "payment_days" in sheet:
            other = self.other_payment(case, v, sheet)
            if other:
                draft = {**draft, "sheets": [sheet, other]}
        if self.e["soft_give"] and self.signal(case, v, "wants_volume"):
            draft = {**draft, "arguments": [SOFT_GIVE, *(draft.get("arguments") or [])]}
        return draft

    def other_payment(self, case, v, sheet):
        """The same package with the other payment days - its quoted ones if we ask for later, else
        the latest - at the price that costs us the same."""
        options = case.get("term_options", {}).get("payment_days") or []
        quoted = v.filled(v.opening["term_sheets"][0]["terms"]).get("payment_days") if v.opening else None
        days = quoted if quoted is not None and quoted != sheet["payment_days"] else max(options, default=None)
        if days is None or days == sheet["payment_days"] or days not in options:
            return None
        structure = {f: x for f, x in sheet.items() if f != "unit_price"}
        price = calculator.price_for(case, v.std, {**structure, "payment_days": days}, v.c(sheet))
        if price is None or price <= 0:
            return None
        other = complete_offer(case, {**structure, "payment_days": days, "unit_price": round(price, 2)})
        return other if v.valid(other) else None

    def banked(self, case, v, cited, ours_here, price):
        """The negotiator's next fact, except that the kinds of fact the dossier's signals point to come first."""
        kinds = [k for sig, ks in PREFER.items() if self.signal(case, v, sig) for k in ks]
        if not (self.e["signal_facts"] and kinds):
            return super().banked(case, v, cited, ours_here, price)
        try:
            from . import claims

            def topic(ref):
                head = ref.split(":", 1)[0]
                return {"ctr": "doc"}.get(head, head)

            used = {topic(i) for i in cited}
            with calculator.LOCK:
                found = claims.arguments(
                    case, v.sid, self.intel(case, v), package=self.package, used=cited, price=price
                )
            for a in sorted(found, key=lambda a: a["kind"] not in kinds):  # stable: the bank's order within each group
                if a["kind"] == "quote" or a["sentence"] in ours_here or not a.get("ids") or topic(a["ids"][0]) in used:
                    continue
                if "ppm" in a["sentence"]:
                    continue
                return [a["sentence"]]
        except Exception as e:  # an argument less, never a lost move
            log.warning("%s %s: argument bank failed (%s: %s)", case.get("case_id"), v.sid, type(e).__name__, e)
        return []

    # -- after its final offer ---------------------------------------------------------------------
    def push_price(self, case, v):
        """One ask below its first final offer, or None: we asked since, no message is left, or there is no room."""
        if not self.e["push_final"] or v.status != "final_offer" or v.left <= 1:
            return None
        first = next(i for i, m in enumerate(v.events) if m.get("from") != "buyer" and m.get("status") == "final_offer")
        if any(m.get("from") == "buyer" and m.get("term_sheets") for m in v.events[first + 1 :]):
            return None
        terms = v.filled(v.standing[1])
        if terms.get("unit_price") is None or not v.valid(terms):
            return None
        price = round(terms["unit_price"] * (1 - self.e["push_final"]), 2)
        last = complete_offer(case, v.asks[-1]) if v.asks else None
        if last and all(last.get(f) == x for f, x in terms.items() if f != "unit_price"):
            price = max(price, last["unit_price"])
        return price if price < terms["unit_price"] - 0.005 else None

    def ready(self, case, v, rival=math.inf):
        if self.push_price(case, v) is not None:
            return False
        return super().ready(case, v, rival)

    def plan(self, case, v, rival=math.inf):
        plan = super().plan(case, v, rival)
        push = self.push_price(case, v)
        if push is not None:
            s = {f: x for f, x in v.filled(v.standing[1]).items() if f != "unit_price"}
            return {
                **plan,
                "sheet": complete_offer(case, {**s, "unit_price": push}),
                "structure": s,
                "capped": False,
                "enough": False,
            }
        if v.asks and v.status == "open":
            stalled = self.e["zone"] and self.stalls(case, v, plan["structure"]) >= self.e["stall_after"]
            if stalled:
                plan = self.zoned(case, v, plan)
            elif self.e["creep"]:
                plan = self.crept(case, v, plan)
        if self.e["past_target"] and plan["enough"]:
            plan = self.past(case, v, plan)
            if not plan["enough"] and self.e["past_creep"] is not None and v.asks:
                plan = self.crept(case, v, plan, self.e["past_creep"])
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
    def stalls(self, case, v, s):
        """How many times in a row it has repeated its price for the structure we ask on."""
        prices = []
        for m in v.theirs:
            sheets = m.get("term_sheets") or []
            if not sheets:
                continue
            terms = v.filled(sheets[0]["terms"])
            same = {f: x for f, x in terms.items() if f != "unit_price"} == s
            prices.append(terms.get("unit_price") if same else None)
        count = 0
        while len(prices) - count >= 2 and prices[-1 - count] is not None and prices[-2 - count] is not None:
            if prices[-2 - count] - prices[-1 - count] > 0.005:
                break
            count += 1
        return count

    def zoned(self, case, v, plan):
        """It has stopped moving: ask just below its offer now, where suppliers have said yes at once."""
        s = plan["structure"]
        last = complete_offer(case, v.asks[-1])
        quoted = self.quoted(case, v).get(_key(s))
        if quoted is None or {f: x for f, x in last.items() if f != "unit_price"} != s:
            return plan
        price = round(quoted * (1 - self.e["zone"]), 2)
        if price <= last["unit_price"] + EPS:
            return plan  # we are in the zone already: the negotiator's rule decides (step or take its offer)
        return {**plan, "sheet": complete_offer(case, {**s, "unit_price": price}), "capped": False}

    def crept(self, case, v, plan, share=None):
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
        share = self.e["creep"] if share is None else share
        price = min(last["unit_price"] + share * (quoted - last["unit_price"]), ceiling, plan["sheet"]["unit_price"])
        price = round(max(price, last["unit_price"]), 2)
        if price <= last["unit_price"] + EPS and ceiling >= last["unit_price"] + 0.01:
            price = round(last["unit_price"] + 0.01, 2)  # the smallest step it can see
        return {
            **plan,
            "sheet": complete_offer(case, {**s, "unit_price": price}),
            "capped": price <= last["unit_price"] + EPS,
        }


def make_agent(package=None, writer=None, **knobs):
    """The layer with exactly the knobs given, for tests and experiments (none: the negotiator's
    moves). What `--agent sellm` plays is set in `sellm.agent.KNOBS`."""
    return Persistent(package, writer=writer, **knobs)
