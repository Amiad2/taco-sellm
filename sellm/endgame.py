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
import re

from arena_kit.cost import complete_offer

from . import calculator
from .negotiator import EPS, Negotiator, Thread, _key, log

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
    # A supplier whose own letter says it is open to discuss call-off planning (dossier wants_planning) is offered
    # that schedule in the first e-mail: the sentence of `soft_give`, which cost nothing where it was not asked for
    plan_give=False,
    # A supplier that answers our fixed-price ask with clause sheets only ("we cannot offer a fixed price for a
    # 36-month contract") is still asked for the fixed price - unless its material is hedged (dossier): P18's
    # supplier then lowered its clause sheets by 0.20 per fact instead of 0.10, and its sheet is taken once our
    # step would meet it (0.657 -> 0.729). P08's, hedged, ended a cent higher that way (0.803 against 0.814).
    hold_fixed=False,
    # A fraction: from the third ask on, to a single supplier, no ask is further below the price it quotes for our
    # structure than this share - an ask far below its offer late in a thread got its final offer (P07: 5.12
    # against 5.48), a closer one a further round
    near=None,
    # With a relationship term, where an index clause is negotiable and the supplier quotes a fixed
    # price: the clause as a second offer in the first ask, at the price where our total cost is lowest.
    # A clause is security for the supplier, not cash: it pays for it with a price far below its cost,
    # which the relationship term then charges us for - and it never goes back up (P02: 351.45 taken
    # = 0.242, 361.35 asked at once = 0.735, fixed price 0.531; experiments/P02-ARGUMENTS.md)
    clause_offer=False,
    # "llm": before the first ask the model reads the supplier (its opening, letters, notes, quote remarks) and
    # names the terms it would give price for, each with the passage it rests on (sellm/planner.py; three calls,
    # two must agree). Code acts on two kinds only, both measured: a faster payment it asked for (`fast_pay`)
    # and an index clause where a relationship term applies (`clause_offer`). Everything else is logged.
    plan=None,
    plan_timeout=12.0,
    plan_only=False,  # a test: the two trades are triggered by the planner alone, not by the dossier's rules
    # With the planner: a cost driver the supplier itself blames for its price (its letter says "energy") and that
    # fell is cited with its larger fall, from its peak of the last twelve months, not over the year. P01: the
    # foundry's letter blames energy, PPI-D351 -6.1 % since November instead of -3.7 % on the year, 0.969 -> 0.997.
    # Not for a supplier that gave no such reason: P11 lost its close with the same sentence (Omar's E4).
    idx_blamed=False,
    # A fraction (0.93): the first ask to a supplier the dossier calls capacity-tight is no lower than this share
    # of its opening price. P10's seal maker answered every lower first ask (24.72, 28.60) with its final offer at
    # once and stayed open at 29.89-29.95 (Amiad's sellm2: 0.647 -> 0.671). A supplier that allocates its
    # volume does not need our order.
    no_lowball=None,
    # How many facts the first e-mail carries (the next ones the agent would cite, one sentence each). Suppliers
    # that walk a price ladder say final_offer after about four of our messages: a fact in hand at the end is lost.
    first_facts=1,
    # RFQ: a bidder that has answered `behind_after` of our asks and still costs us this share more than the best
    # other standing offer is not asked again. The arena answers a session's messages one after another: in P05
    # the loop waited 98 s for a bidder at 33.00 while the one at its final 28.00 timed out and withdrew
    # (0.717 instead of 0.820, Sun 04:25).
    drop_behind=None,
    behind_after=2,
)
CLAUSE_LINE = "With the index clause of the second option the price follows {series} beyond the deadband, so that this risk does not have to be priced in up front."
IDX_LINE = re.compile(
    r"^The index (\S+) changed ([+-][\d.]+) % from (\d{4}-\d{2}) to (\d{4}-\d{2}) \((idx:[^,]+), (idx:[^)]+)\)\.$"
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

    def wants(self, case, v):
        """{field: {"direction", "value", "evidence", "votes"}} from the planner, {} without one. Read
        once per supplier; `prepare` asks for all suppliers of a case at once."""
        key = (case.get("case_id"), v.sid, "wants")
        if key not in self._memo:
            found = {}
            if self.e["plan"] == "llm" and v.opening:
                try:
                    from . import llm, planner

                    if llm.configured():
                        quoted = v.filled(v.opening["term_sheets"][0]["terms"])
                        found = planner.voted(
                            case,
                            v.opening,
                            self.intel(case, v),
                            quoted,
                            timeout_s=self.e["plan_timeout"],
                            drivers=self.drivers(case),
                        )
                        for field, w in found.items():
                            if field == "blames":
                                log.info("%s %s: it blames %s for its price", case.get("case_id"), v.sid, ", ".join(w))
                                continue
                            log.info(
                                '%s %s: it would give price for %s (%s, %d votes) - "%s"',
                                case.get("case_id"),
                                v.sid,
                                field,
                                w["direction"],
                                w["votes"],
                                w["evidence"][:120],
                            )
                    else:
                        log.warning(
                            "%s: plan=llm but no model is configured, playing without a plan", case.get("case_id")
                        )
                except Exception as e:  # a plan less, never a lost move
                    log.warning("%s %s: no plan (%s: %s)", case.get("case_id"), v.sid, type(e).__name__, e)
            self._memo[key] = found
        return self._memo[key]

    def drivers(self, case):
        """[(series, name)] of the cost drivers of the case's parts, for the planner."""
        key = (case.get("case_id"), "drivers")
        if key not in self._memo:
            out, parts = [], case.get("parts") or []
            if self.package and parts:
                try:
                    with calculator.LOCK:
                        marks = ",".join("?" * len(parts))
                        rows = self.package.query(
                            "select distinct d.series_id as series, s.name as name from cost_drivers d "
                            f"left join index_series s on s.id = d.series_id where d.part_id in ({marks}) order by 1",
                            tuple(parts),
                        )
                    out = [(r["series"], r["name"] or "") for r in rows]
                except Exception as e:
                    log.warning("%s: cost drivers not available (%s: %s)", case.get("case_id"), type(e).__name__, e)
            self._memo[key] = out
        return self._memo[key]

    def arguments(self, case, v, views, live, sheet):
        """The negotiator's argument; an index the supplier blames for its price is cited with its larger fall;
        the first e-mail may carry more than one fact (`first_facts`)."""
        out = self.blamed(case, v, super().arguments(case, v, views, live, sheet))
        if not v.asks and out:
            seen = v
            while len(out) < int(self.e["first_facts"] or 1):
                # as if the facts so far had been sent: the next one the agent would cite
                seen = Thread(case, v.sid, [*seen.events[: len(v.events)], {"from": "buyer", "body": " ".join(out)}])
                more = self.blamed(case, v, super().arguments(case, seen, {**views, v.sid: seen}, live, sheet))
                if not more or more[0] in out:
                    break
                out = [*out, more[0]]
        return out

    def blamed(self, case, v, out):
        if not (out and self.e["idx_blamed"] and self.e["plan"] == "llm" and self.package):
            return out
        found = IDX_LINE.match(out[0])
        if not found or found.group(1) not in (self.wants(case, v).get("blames") or {}):
            return out
        series, change, last = found.group(1), float(found.group(2)), found.group(6)
        try:
            with calculator.LOCK:
                ids = self.package.ids(f"idx:{series}@")
                if last != ids[-1] or len(ids) < 13:
                    return out
                peak = max(ids[-13:-1], key=lambda i: self.package.lookup(i)["value"])
                fall = (self.package.lookup(last)["value"] / self.package.lookup(peak)["value"] - 1) * 100
        except Exception as e:
            log.warning("%s: index window not available (%s: %s)", case.get("case_id"), type(e).__name__, e)
            return out
        if fall >= change - 0.5:
            return out
        months = (peak.split("@", 1)[1], last.split("@", 1)[1])
        return [f"The index {series} changed {fall:+.1f} % from {months[0]} to {months[1]} ({peak}, {last}).", *out[1:]]

    def prepare(self, case, threads):
        """The plans of all suppliers of a case, asked for at once before our first e-mail: in an RFQ
        every thread's clock is already running."""
        key = (case.get("case_id"), "planned")
        if self.e["plan"] != "llm" or key in self._memo:
            return
        self._memo[key] = True
        from concurrent.futures import ThreadPoolExecutor

        views = [Thread(case, sid, events) for sid, events in threads.items()]
        openings = (case.get("case_id"), "openings")
        if openings not in self._memo:  # as `move` sets it: the dossier's overlay reads every bidder's opening
            self._memo[openings] = {w.sid: [w.opening] for w in views if w.opening}
        views = [v for v in views if v.opening and v.opening["term_sheets"][0]["terms"].get("unit_price") is not None]
        if len(views) > 1:
            for v in views:
                self.intel(case, v)  # the dossier's own lock is taken one at a time
            with ThreadPoolExecutor(max_workers=len(views)) as pool:
                list(pool.map(lambda v: self.wants(case, v), views))

    def move(self, case, threads, focus=None):
        self.prepare(case, threads)
        return super().move(case, threads, focus)

    def opening_structure(self, case, v):
        s = super().opening_structure(case, v)
        if self.e["fast_pay"] and "payment_days" in s:
            # the planner fills gaps, it does not overrule the dossier: where our data has a cash reading, that decides
            unread = self.e["plan_only"] or self.cash(case, v) is None
            asked = unread and (self.wants(case, v).get("payment_days") or {}).get("direction") == "lower"
            ruled = not self.e["plan_only"] and (
                self.signal(case, v, "cash_short") or self.cash(case, v) in ("medium", "high")
            )
            if asked or ruled:
                days = [
                    d
                    for d in case.get("term_options", {}).get("payment_days") or []
                    if v.valid({**s, "payment_days": d, "unit_price": 1.0})
                ]
                if days and min(days) < s["payment_days"]:
                    s = {**s, "payment_days": min(days)}
                    self._memo[(case.get("case_id"), v.sid, "s0")] = s
        return s

    # -- security instead of price: the index clause (experiments/P02-ARGUMENTS.md) -------------------
    def clause_case(self, case, v):
        """Our estimate of the supplier where the clause offer applies, else None: a relationship term,
        an index clause to negotiate, an opening that quotes a fixed price - and a should-cost of its
        own plant that leaves that price no more than the sustainable margin. Then a fixed price has
        no room left by our own data, and the cost we price the clause with is the highest its own
        quote allows: an estimate that is too low would make us squeeze it without noticing, because
        with a clause its price no longer stops at its cost."""
        if not self.e["clause_offer"] or "index_clause" not in case.get("negotiable", ()) or not v.opening:
            return None
        opening = v.filled(v.opening["term_sheets"][0]["terms"])
        if opening.get("unit_price") is None or opening.get("index_clause"):
            return None
        estimate, own = self.estimate(case, v), self.should_cost(case, v.sid)
        if not estimate:
            return None
        ceiling = self.value(case, v, opening) * (1 - case["buyer"]["sustainable_margin_pct"] / 100)
        if own and own[1] >= ceiling * (1 - 1e-9) and not self.e["plan_only"]:
            return estimate
        if (self.wants(case, v).get("index_clause") or {}).get("direction") == "clause":
            # the planner read that it would pay for a clause, but our data does not say its price is at its
            # cost: price the clause with the highest cost its own quote allows, so that we cannot squeeze it
            return {**estimate, "full_cost": max(estimate["full_cost"], ceiling)}
        return None

    def clause_price(self, case, v, s):
        """The price on structure `s` where our total cost is lowest, the relationship term priced with
        our estimate of its full cost: below it a lower price costs us more than it saves."""
        key = (case.get("case_id"), v.sid, "clause-price", _key(s))
        if key not in self._memo:
            estimate = self.clause_case(case, v) or self.estimate(case, v)
            v0, v1 = self.value(case, v, {**s, "unit_price": 0.0}), self.value(case, v, {**s, "unit_price": 1.0})
            even = (estimate["full_cost"] - v0) / (v1 - v0) if v1 > v0 else None  # pays it exactly its full cost
            if not even or even <= 0:
                self._memo[key] = None
            else:
                grid = [even * (0.85 + 0.15 * i / 600) for i in range(601)]
                self._memo[key] = round(min(grid, key=lambda p: v.c({**s, "unit_price": p}, estimate)), 2)
        return self._memo[key]

    def clause_sheet(self, case, v, sheet):
        """Our first ask again with the index clause that costs us least, at `clause_price` - if that
        is cheaper for us than the fixed price at which the supplier just covers its cost (the lowest
        fixed price it can take). Else None."""
        estimate = self.clause_case(case, v)
        if not estimate or sheet.get("index_clause"):
            return None
        base = {f: x for f, x in sheet.items() if f != "unit_price"}
        ref = v.filled(v.opening["term_sheets"][0]["terms"])["unit_price"]
        options = [{**base, "index_clause": o} for o in case.get("term_options", {}).get("index_clause") or [] if o]
        options = [s for s in options if v.valid({**s, "unit_price": ref})]
        if not options:
            return None
        s = min(options, key=lambda s: v.c({**s, "unit_price": ref}))
        price = self.clause_price(case, v, s)
        v0, v1 = self.value(case, v, {**base, "unit_price": 0.0}), self.value(case, v, {**base, "unit_price": 1.0})
        if price is None or v1 <= v0:
            return None
        fixed = v.c({**base, "unit_price": (estimate["full_cost"] - v0) / (v1 - v0)}, estimate)
        other = complete_offer(case, {**s, "unit_price": price})
        return other if v.valid(other) and v.c(other, estimate) < fixed * (1 - 0.002) else None

    def structure(self, case, v, s0):
        """With the clause offer: a clause it prices below `clause_price` is no structure to follow -
        it never raises a price it has named, and that price costs us more than its fixed one."""
        s = super().structure(case, v, s0)
        if (
            self.e["hold_fixed"]
            and s.get("index_clause")
            and "index_clause" in s0
            and s0["index_clause"] is None
            and not self.clause_case(case, v)
            and not self.signal(case, v, "material_hedged")
        ):
            return s0
        if not s.get("index_clause") or not self.clause_case(case, v):
            return s
        quoted, floor = self.quoted(case, v).get(_key(s)), self.clause_price(case, v, s)
        if quoted is None or floor is None or quoted >= floor - 0.005:
            return s
        fixed = {**s, "index_clause": None}
        return fixed if v.valid({**fixed, "unit_price": quoted}) else s

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
        secured = self.clause_sheet(case, v, sheet)
        if secured:
            line = CLAUSE_LINE.format(series=secured["index_clause"].get("series"))
            draft = {
                **draft,
                "sheets": [sheet, secured, *draft["sheets"][1:]],
                "arguments": [*(draft.get("arguments") or []), line],
            }
        if self.e["pay_probe"] and len(draft["sheets"]) == 1 and "payment_days" in sheet:
            other = self.other_payment(case, v, sheet)
            if other:
                draft = {**draft, "sheets": [sheet, other]}
        if (self.e["soft_give"] and self.signal(case, v, "wants_volume")) or (
            self.e["plan_give"] and self.signal(case, v, "wants_planning")
        ):
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

    def behind(self, case, v, rival):
        """This bidder cannot win any more: after `behind_after` answers its offer is still far above the best other."""
        share = self.e["drop_behind"]
        if not share or rival == math.inf or v.status != "open" or len(v.asks) < self.e["behind_after"]:
            return False
        its = v.filled(v.standing[1]) if v.standing[0] else {}
        return bool(its) and v.valid(its) and v.c(its) > rival * (1 + share)

    def ready(self, case, v, rival=math.inf):
        if self.push_price(case, v) is not None:
            return False
        if self.behind(case, v, rival):
            return True
        return super().ready(case, v, rival)

    def plan(self, case, v, rival=math.inf):
        plan = super().plan(case, v, rival)
        s = plan["structure"]
        if s.get("index_clause") and self.clause_case(case, v):
            floor = self.clause_price(case, v, s)
            if floor and plan["sheet"]["unit_price"] < floor:  # it would take a lower ask, and we would pay for it
                quoted = self.quoted(case, v).get(_key(s))
                plan = {
                    **plan,
                    "sheet": complete_offer(case, {**s, "unit_price": floor}),
                    "capped": quoted is not None and floor >= quoted - 0.005,
                }
        if self.clause_case(case, v) and v.status == "open" and v.standing[1].get("unit_price") is not None:
            its = v.filled(v.standing[1])
            if its.get("index_clause"):  # a clause it prices below what our cost can bear is no offer to stop at
                floor = self.clause_price(case, v, {f: x for f, x in its.items() if f != "unit_price"})
                if floor and its["unit_price"] < floor - 0.005:
                    plan = {**plan, "enough": False}
        if self.e["no_lowball"] and not v.asks and v.opening and self.signal(case, v, "capacity_tight"):
            its = v.opening["term_sheets"][0]["terms"].get("unit_price")
            floor = round(its * self.e["no_lowball"], 2) if its else None
            if floor and plan["sheet"]["unit_price"] < floor:
                plan = {**plan, "sheet": complete_offer(case, {**plan["sheet"], "unit_price": floor})}
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
        if self.e["near"] and len(v.asks) >= 2 and v.status == "open" and len(case.get("suppliers") or []) == 1:
            plan = self.neared(case, v, plan)
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

    def neared(self, case, v, plan):
        """The same ask, but no further below the price it quotes for this structure than `near`."""
        s = plan["structure"]
        quoted = self.quoted(case, v).get(_key(s))
        if quoted is None or plan.get("capped") or plan.get("enough"):
            return plan
        price = round(quoted * (1 - self.e["near"]), 2)
        if price <= plan["sheet"]["unit_price"] + EPS:
            return plan
        return {**plan, "sheet": complete_offer(case, {**s, "unit_price": price})}

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
