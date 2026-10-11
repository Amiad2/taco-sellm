# ruff: noqa: E501  (long sentences and messages)
"""How sellm2 negotiates: one pure function from the case and the threads to the next move.

The move is built in four steps, each from the case file, the e-mails and our data, never from a
case or supplier name:

1. Structure (`opening_structure`, `structure`). Every term sheet the case allows is priced in our
   total cost C at the price the supplier would want for it: levers that are cash to it (payment
   days, start date, Incoterm, tooling, chargeback) through its value function at its cost of money,
   levers that are not (lead time, ppm, deadband) at the premium suppliers charged for them in their
   own alternative sheets. We ask for the structure where the gap between what a lever saves us and
   what it costs the supplier is largest. Payment days follow its cost of money: the latest days from
   a supplier that borrows cheaply, the fastest from one short of cash. After its first answer we
   follow whichever structure it has priced that is cheapest for us.
2. Price (`aim`, `plan`). A target from its full cost (should-cost of its own plant; in strategic and
   bottleneck cases the price where C including the relationship term is lowest) or from a prior
   share of its opening read from its signals. First ask 6 % below the target, never a lowball to a
   supplier whose capacity is tight. Then each step is sized so that our price and its price meet
   after four of our messages, given the share of our steps it has given back so far (the supplier
   model fitted on 237 real replies: it mirrors a share of each step, with a per-round limit, and
   says final_offer after about four to six of our messages). We stay just below its price so it
   makes the last move, and never lower our own price.
3. Argument: one checked fact per e-mail, every round (an argument-free round gets a hold): a rival's
   cheaper offer, its own should-cost, a falling cost driver, a recent fall from the 12-month peak,
   then the bank by case type; one per topic; no material index to a supplier whose material is
   hedged.
4. Close: accept its final offer or its agreement, or the cheapest standing offer once nothing is
   left to ask; take its cheaper alternative sheet by sending it back; never ask after a final offer;
   walk away only to a better alternative.
"""

import logging
import math
import re

from arena_kit.agents.llm import ID_RE
from arena_kit.cost import complete_offer, must_haves_ok
from arena_kit.play import closing_move, live_threads, moves_left

from . import knowledge
from .knobs import KNOBS
from .knowledge.facts import candidates
from .model import EPS, READY, CaseModel, Supplier, Thread, key, strip
from .write import email

log = logging.getLogger("sellm2")

TOO_LOW = re.compile(r"far below|well below|below a feasible|not feasible, as they do not reflect|operational limits", re.I)
ASKS_DATA = re.compile(r"which figures is that based on|send us the data|data supporting your assumptions", re.I)
CASH_FIELDS = ("incoterm", "tooling_eur", "chargeback_eur_per_complaint")  # kept as quoted: cash to it
BANK_ORDER = {
    "quality": ["sc_ppm", "qn", "sc_otd", "cost", "idx", "doc", "po", "fc", "news", "quote"],
    "capacity": ["fc", "sc_otd", "cost", "idx", "doc", "po", "news", "sc_ppm", "qn", "quote"],
    "rfq": ["quote", "cost", "idx", "fc", "sc_otd", "sc_ppm", "po", "doc", "news", "qn"],
}
DEFAULT_ORDER = ["doc", "idx", "cost", "po", "fc", "sc_otd", "sc_ppm", "qn", "news", "quote"]
NOT_MATERIAL = ("LCI-", "PPI-D35")  # labour and energy series: a material hedge does not cover them


class Policy:
    def __init__(self, package=None, **knobs):
        self.package = package
        self.k = {**KNOBS, **knobs}
        self._memo = {}

    # ===========================================================================================
    # the move
    # ===========================================================================================
    def move(self, case, threads, focus=None):
        """A draft: {kind: ask | take_alternative | hold | accept | walk_away, sid, sheets, arguments,
        n, flags, reasons}."""
        cm = CaseModel(case)
        views = {sid: Thread(cm, sid, events) for sid, events in threads.items()}
        live = [v for v in views.values() if v.live]
        if not live:
            return {"kind": "walk_away", "sid": next(iter(threads)), "reasons": ["no supplier left"]}
        self._openings(case, views)
        cost = {v.sid: self.offer_cost(cm, v) for v in live}
        plain = {v.sid: (v.c(v.filled(v.standing[1])) if cost[v.sid] < math.inf else math.inf) for v in live}
        rival = {v.sid: min((plain[w.sid] for w in live if w.sid != v.sid), default=math.inf) for v in live}
        movable = sorted((v for v in live if not self.ready(cm, v, rival[v.sid])), key=lambda v: (len(v.ours), cost[v.sid]))
        leader = min(live, key=lambda v: cost[v.sid])
        if focus is not None and focus in views and views[focus] in live:
            v = views[focus]
            if v in movable:
                return self.ask(cm, v, views, live, rival[v.sid])
            if movable:  # it waits while another bidder still moves: keep it from timing out
                if cost[v.sid] < math.inf and v.holds < self.k["max_holds"] and v.left > 1:
                    return {"kind": "hold", "sid": v.sid, "sheets": [], "n": len(v.asks), "reasons": ["waits for the others"]}
                if leader not in movable:
                    return self.close(cm, live, cost)
        if movable:
            return self.ask(cm, movable[0], views, live, rival[movable[0].sid])
        draft = self.close(cm, live, cost)
        if focus is None and len(views) > 1 and draft["kind"] == "accept":
            # A runner that serves one thread at a time lets the others time out, and a timeout
            # replaces the offer ID: a holding e-mail first brings this thread up to date.
            v = views[draft["sid"]]
            if not v.fresh and v.left > 1:
                return {"kind": "hold", "sid": v.sid, "sheets": [], "n": len(v.asks), "reasons": ["refresh the offer ID before accepting"]}
        return draft

    def _openings(self, case, views):
        k = (case.get("case_id"), "openings")
        if k not in self._memo:
            self._memo[k] = {v.sid: [v.opening] for v in views.values() if v.opening}
            prices = [v.opening["term_sheets"][0]["terms"].get("unit_price") for v in views.values() if v.opening]
            self._memo[(case.get("case_id"), "cheapest")] = min((p for p in prices if p), default=None)

    # ===========================================================================================
    # what we know about a supplier
    # ===========================================================================================
    def brief(self, cm, v):
        k = (cm.case.get("case_id"), v.sid, "brief")
        if k not in self._memo:
            if self.package is not None and self.k["data"]:
                with knowledge.LOCK:
                    self._memo[k] = knowledge.build(self.package, v.sid, cm.case.get("parts") or [], cm.case,
                                                    self._memo.get((cm.case.get("case_id"), "openings")) or {})  # fmt: skip
            else:
                self._memo[k] = knowledge.Brief(sid=v.sid)
                self._memo[k].contact = knowledge.contact_name(v.opening)
        return self._memo[k]

    def supplier(self, cm, v):
        k = (cm.case.get("case_id"), v.sid, "supplier")
        if k not in self._memo:
            self._memo[k] = Supplier(cm, v, self.brief(cm, v), rate=None if self.brief(cm, v).known else self.k["rate_guess"])
        return self._memo[k]

    def part(self, cm, v):
        """The brief of the case's only part (a bundle's unit price is not one part's), or None."""
        parts = cm.case.get("parts") or []
        return self.brief(cm, v).parts.get(parts[0]) if len(parts) == 1 else None

    def payment_mode(self, cm, v):
        """latest | fastest | quoted | menu: what we ask for payment days in the first ask."""
        b = self.brief(cm, v)
        if not b.known:
            return "menu"
        if b.cash_pressure in ("medium", "high") or b.signal("cash_short"):
            return "fastest"  # P01: every offer 1.2-2.4 lower with 14 days (+0.054 with past_target)
        if b.cost_of_money >= self.k["fast_rate"]:
            return "fastest"  # a job shop prices days at 17-35 % a year (P05: "faster payment ... much better price")
        return "latest"  # relaxed about cash: P04 0 -> 0.86, P08 0.15 -> 0.53 with 90 days

    # ===========================================================================================
    # 1. structure
    # ===========================================================================================
    def opening_structure(self, cm, v):
        k = (cm.case.get("case_id"), v.sid, "s0")
        if k in self._memo:
            return self._memo[k]
        base = strip(v.opening_terms) if v.opening else {}
        sup = self.supplier(cm, v)
        price = (v.opening_terms.get("unit_price") if v.opening else None) or cm.b.get("current_unit_price") or 1.0
        end = price * self.share(cm, v)
        mode = self.payment_mode(cm, v)
        keep = {f: base[f] for f in CASH_FIELDS if f in base and f in cm.negotiable}
        days = [d for d in cm.options.get("payment_days") or []]
        if "payment_days" in cm.negotiable and "payment_days" in base:
            if mode in ("quoted", "menu") or not days:
                keep["payment_days"] = base["payment_days"]
        ranked = []
        for fixed in (keep, {}):  # its own cash terms where they keep the must-haves, else any valid ones
            seen = set()
            for s in cm.structures(base or None):
                s = strip(cm.sheet({**base, **s, **fixed, "unit_price": 1.0}))
                if mode == "latest" and days and "payment_days" in s and "payment_days" not in fixed:
                    s["payment_days"] = max(days)
                if mode == "fastest" and days and "payment_days" in s and "payment_days" not in fixed:
                    s["payment_days"] = min(days)
                kk = key(s)
                if kk in seen or not cm.ok({**s, "unit_price": 1.0}, v.std):
                    continue
                seen.add(kk)
                p = end + (sup.lever_premium(s, base, end) if self.k["lever_prices"] else 0.0)
                ranked.append((v.c({**s, "unit_price": p}), s))
            if ranked:
                break
        if not ranked:
            self._memo[k] = base
            return base
        ranked.sort(key=lambda r: r[0])
        best_c = ranked[0][0]
        near = [s for c, s in ranked if c <= best_c * (1 + 1e-4)]

        def away(s):
            return sum(0 if s.get(f) == base.get(f) else 1 for f in s)

        best = min(near, key=lambda s: (-(s.get("contract_months") or 0), away(s)))
        if mode == "fastest" and days and "payment_days" in best:  # only days it can take with the must-haves
            ok = [d for d in sorted(days) if cm.ok({**best, "payment_days": d, "unit_price": 1.0}, v.std)]
            if ok:
                best = {**best, "payment_days": ok[0]}
        self._memo[k] = best
        return best

    def structure(self, cm, v, s0):
        """After its first answer: the structure of whichever sheet it has priced (standing, an
        alternative, its opening) is cheapest for us at its price; ours stays unless that gains 0.2 %."""
        if not v.asks:
            return s0
        previous = strip(complete_offer(cm.case, v.asks[-1]))
        raws = [s["terms"] for s in v.sheets]
        if v.opening and len(v.theirs) > 1:
            raws.append(v.opening["term_sheets"][0]["terms"])
        options = []
        for raw in raws:
            t = v.filled(raw)
            if t.get("unit_price") is None or not v.ok(t):
                continue
            options.append((v.c(t), strip(t)))
        if not options:
            return previous
        stay = next((o for o in options if o[1] == previous), options[0])
        best = min(options, key=lambda o: o[0])
        chosen = (best if best[0] < stay[0] * (1 - 0.002) else stay)[1]
        if chosen.get("index_clause") and self.clause_case(cm, v):  # a clause priced below our floor: back to fixed
            quoted, floor = v.quoted().get(key(chosen)), self.clause_price(cm, v, chosen)
            if quoted is not None and floor is not None and quoted < floor - 0.005:
                fixed = {**chosen, "index_clause": None}
                if v.ok({**fixed, "unit_price": quoted}):
                    return fixed
        return chosen

    def better_alternative(self, cm, v):
        """One of its other sheets, cheaper for us by 0.2 %, valid, not sent back yet."""
        if v.status == "agreed" or len(v.sheets) < 2 or v.left < 1:
            return None
        _, standing = v.standing
        base = v.c(v.filled(standing)) if standing.get("unit_price") is not None else math.inf
        best = None
        for sheet in v.sheets[1:]:
            t = v.filled(sheet["terms"])
            if not v.ok(t):
                continue
            c = v.c(t)
            if c < base * (1 - 0.002) and (best is None or c < best[0]):
                best = (c, t)
        if best is None or (v.asks and complete_offer(cm.case, v.asks[-1]) == best[1]):
            return None
        return best[1]

    # ===========================================================================================
    # 2. price
    # ===========================================================================================
    def share(self, cm, v):
        """Where a deal can end as a share of its opening when we hold no cost of its own plant."""
        base = self.k["target_share"][cm.relationship]
        b = self.brief(cm, v)
        if not b.known:
            return base
        if b.signal("list_price_fixed") >= 2 or b.signal("margin_floor") >= 1:
            return max(base, 0.96)
        if b.signal("wants_volume") >= 2:
            return min(base, 0.84)
        return base

    def own_cost(self, cm, v):
        """(ref, its full cost per price unit) from the case file, its own plant or a cost breakdown it
        sent us in this thread; else None."""
        pb = self.part(cm, v)
        if pb and pb.own_cost:
            return pb.own_cost
        if self.k["breakdown"]:
            for m in v.theirs:
                for att in m.get("attachments") or []:
                    found = read_breakdown(att.get("text"))
                    if found and len(cm.case.get("parts") or []) == 1:
                        return (att.get("attachment_id") or "breakdown", found["direct"] + 0.5 * (found["profit"] or 0))
        return None

    def aim(self, cm, v):
        """{target, full, source}: where we want the price to end on our first-ask structure, and our
        estimate of its full cost in value terms."""
        k = (cm.case.get("case_id"), v.sid, "aim")
        if k in self._memo:
            return self._memo[k]
        s0 = self.opening_structure(cm, v)
        sup = self.supplier(cm, v)
        own = v.opening_terms.get("unit_price") if v.opening else None
        _, standing = v.standing
        ref = own or standing.get("unit_price") or cm.b.get("current_unit_price") or cm.b.get("fallback_unit_price") or 1.0
        market = self._memo.get((cm.case.get("case_id"), "cheapest")) or ref
        v0, v1 = sup.value({**s0, "unit_price": 0.0}), sup.value({**s0, "unit_price": 1.0})
        estimate = self.own_cost(cm, v)
        # The premium for non-cash levers (lead time, ppm, deadband) chooses the structure only; the price
        # stays on the measured path, and the supplier reprices the lever in its own counter. A target
        # lowered by the premium would read as a lowball (P05: 0.65 of its opening instead of 0.71).
        premium = 0.0
        if estimate and cm.relationship and v.opening and own:
            # no real opening carried a relationship cost (D01, P01, P02, P03, P10): an estimate that
            # would put its opening below the sustainable margin is too high
            worth = sup.value(v.opening_terms)
            estimate = (estimate[0], min(estimate[1], worth * (1 - cm.b["sustainable_margin_pct"] / 100)))
        if estimate and v1 > v0:
            source, full = "cost", estimate[1] + premium
            target = (full - v0) / (v1 - v0)
            if cm.relationship:
                est = sup.estimate(full)
                top = max(ref, target * 1.25)
                grid = [target + (top - target) * i / 250 for i in range(251)]
                target = min(grid, key=lambda p: v.c({**s0, "unit_price": p}, est))
        else:
            source = "prior"
            share = self.share(cm, v)
            target = share * min(ref, market)
            pb = self.part(cm, v)
            if pb and pb.low_12m and not pb.below_full_cost and share < 0.96:
                target = min(target, pb.low_12m)  # a price it charged within a year
            if v.opening and v1 > v0:
                target = (sup.value({**v.opening_terms, "unit_price": target}) - v0) / (v1 - v0) + premium
            full = sup.value({**s0, "unit_price": target})
            if cm.relationship:  # the prior is where deals ended, above its full cost
                one_pct = cm.b["need_per_year"] * target / 100
                per = cm.b["relationship_eur_per_point"]
                gap = 5.0 if per <= one_pct else 5 * one_pct / per
                full *= 1 - max(0.0, cm.b["sustainable_margin_pct"] - gap) / 100
        target = min(target, ref * 0.985)
        if not (math.isfinite(target) and target > 0):
            target = ref * 0.9
        out = {"target": target, "full": full, "source": source, "s0": s0}
        self._memo[k] = out
        return out

    def estimate(self, cm, v):
        """The supplier for the relationship term (strategic and bottleneck cases only)."""
        if not cm.relationship or not v.opening or v.opening["term_sheets"][0]["terms"].get("unit_price") is None:
            return None
        return self.supplier(cm, v).estimate(self.aim(cm, v)["full"])

    def offer_cost(self, cm, v):
        sheet_id, terms = v.standing
        if not sheet_id or not v.ok(terms):
            return math.inf
        return v.c(terms, self.estimate(cm, v))

    def first_price(self, cm, v, s0):
        aim = self.aim(cm, v)
        price = aim["target"] * (1 - self.k["open_below"])
        if self.brief(cm, v).signal("capacity_tight") and v.opening and self.k["no_lowball_tight"]:
            sup = self.supplier(cm, v)
            same = sup.price_at_value(s0, sup.value(v.opening_terms))
            if same:
                price = max(price, same * (1 - self.k["tight_open_below"]))
        return price

    def plan(self, cm, v, rival=math.inf):
        """Our next ask: {sheet, capped, enough, target, structure}."""
        s0 = self.opening_structure(cm, v)
        s = self.structure(cm, v, s0)
        aim = self.aim(cm, v)
        last = complete_offer(cm.case, v.asks[-1]) if v.asks else None
        _, standing = v.standing
        their = v.c(v.filled(standing)) if standing.get("unit_price") is not None else math.inf
        quoted = v.quoted().get(key(s))
        kb = self.k["keep_below"]
        if quoted is not None:
            ceiling = quoted * (1 - kb)
        elif their < math.inf:
            ceiling = cm.price_for(s, their * (1 - kb), v.std) or math.inf
            if v.asks:
                ceiling = min(ceiling, standing["unit_price"] * (1 - kb))
        else:
            ceiling = math.inf
        if rival < math.inf:
            cap = cm.price_for(s, rival * (1 - kb), v.std)
            if cap is not None:
                ceiling = min(ceiling, cap)
        if last is None:
            price = self.first_price(cm, v, s0)
        elif ceiling < math.inf:
            rounds = max(1, self.k["horizon"] - len(v.asks))
            if TOO_LOW.search(v.last.get("body") or ""):
                rounds = 1  # it calls our ask not serious: close the gap now
            step = (ceiling - last["unit_price"]) / (rounds * (1 + v.pace(self.k["pace"])))
            price = last["unit_price"] + max(step, 0.0)
        else:
            price = last["unit_price"]
        same = last is not None and strip(last) == s
        if same and quoted is not None and self.k["stall_gap"] and v.status == "open" and self.stalled(cm, v, s):
            # A supplier with a fixed list price that repeats its price does not walk down our ladder
            # (P04 held 4.94 against 4.54/4.62/4.74, P03 432.14 for five rounds) and says final_offer at
            # that price. Asking just below it costs nothing more and may be taken (P04: one cent is 0.14).
            price = max(price, quoted * (1 - self.k["stall_gap"]))
            ceiling = max(ceiling, price)
        price = min(price, ceiling)
        if same:
            price = max(price, last["unit_price"])
        if s.get("index_clause") and self.clause_case(cm, v):
            floor = self.clause_price(cm, v, s)
            if floor and price < floor:  # it would take a lower ask, and we would pay for it
                price = floor
        price = round(max(0.01, price), 2)
        capped = same and price <= last["unit_price"] + EPS
        if s.get("index_clause") and self.clause_case(cm, v) and quoted is not None:
            capped = capped or price >= quoted - 0.005
        enough = cm.relationship and their <= v.c({**s0, "unit_price": aim["target"]}) * (1 + EPS)
        if enough and self.clause_case(cm, v) and v.status == "open":
            its = v.filled(standing)
            if its.get("index_clause"):
                floor = self.clause_price(cm, v, strip(its))
                if floor and its["unit_price"] < floor - 0.005:
                    enough = False  # a clause below what our cost can bear is no offer to stop at
        if enough and self.k["past_target"] and v.status == "open" and v.left > 1 and v.moved():
            if their > v.c({**s0, "unit_price": self.low_target(cm, v)}) * (1 + EPS):
                enough = False  # it still moves and our estimate of its cost may be high: one more ask
        sheet = complete_offer(cm.case, {**s, "unit_price": price})
        return {"sheet": sheet, "capped": capped, "enough": enough, "target": aim["target"], "structure": s}

    def stalled(self, cm, v, s):
        """Its last two prices on structure `s` are the same, and its list price is fixed (dossier)."""
        if self.brief(cm, v).signal("list_price_fixed") < 2:
            return False
        prices = [v.filled(m["term_sheets"][0]["terms"]) for m in v.theirs if m.get("term_sheets")]
        prices = [t["unit_price"] for t in prices if strip(t) == s and t.get("unit_price") is not None]
        return len(prices) >= 2 and abs(prices[-1] - prices[-2]) < 0.005

    def low_target(self, cm, v):
        """Where C would be lowest if its full cost were `estimate_error` lower than we think."""
        aim, sup = self.aim(cm, v), self.supplier(cm, v)
        s0 = aim["s0"]
        full = aim["full"] * (1 - self.k["estimate_error"])
        floor = sup.price_at_value(s0, full)
        if floor is None:
            return aim["target"]
        est = sup.estimate(full)
        grid = [floor + (aim["target"] - floor) * i / 250 for i in range(251)]
        return min(grid, key=lambda p: v.c({**s0, "unit_price": p}, est))

    # -- the index clause as security (relationship cases, P02) ---------------------------------
    def clause_case(self, cm, v):
        """Our supplier estimate where the clause offer applies, else None: a relationship term, a
        negotiable index clause, a fixed-price opening, and a cost of its own plant that leaves that
        price no more than the sustainable margin (a fixed price has no room left by our own data)."""
        if not self.k["clause_offer"] or "index_clause" not in cm.negotiable or not v.opening:
            return None
        k = (cm.case.get("case_id"), v.sid, "clause-case")
        if k in self._memo:
            return self._memo[k]
        out = None
        opening = v.opening_terms
        own = self.part(cm, v).own_cost if self.part(cm, v) else None
        est = self.estimate(cm, v)
        if opening.get("unit_price") is not None and not opening.get("index_clause") and est and own:
            ceiling = self.supplier(cm, v).value(opening) * (1 - cm.b["sustainable_margin_pct"] / 100)
            if own[1] >= ceiling * (1 - 1e-9):
                out = est
        self._memo[k] = out
        return out

    def clause_price(self, cm, v, s):
        """The price on clause structure `s` where C (relationship term included) is lowest."""
        k = (cm.case.get("case_id"), v.sid, "clause-price", key(s))
        if k not in self._memo:
            est = self.clause_case(cm, v) or self.estimate(cm, v)
            sup = self.supplier(cm, v)
            even = sup.price_at_value(s, est["full_cost"]) if est else None
            if not even or even <= 0:
                self._memo[k] = None
            else:
                grid = [even * (0.85 + 0.15 * i / 600) for i in range(601)]
                self._memo[k] = round(min(grid, key=lambda p: v.c({**s, "unit_price": p}, est)), 2)
        return self._memo[k]

    def clause_sheet(self, cm, v, sheet):
        """Option B: our first ask with the index clause that costs us least, at `clause_price`, if
        that beats the fixed price at which the supplier just covers its cost."""
        est = self.clause_case(cm, v)
        if not est or sheet.get("index_clause"):
            return None
        base = strip(sheet)
        ref = v.opening_terms["unit_price"]
        options = [{**base, "index_clause": o} for o in cm.options.get("index_clause") or [] if o]
        options = [s for s in options if v.ok({**s, "unit_price": ref})]
        if not options:
            return None
        s = min(options, key=lambda s: v.c({**s, "unit_price": ref}))
        price = self.clause_price(cm, v, s)
        sup = self.supplier(cm, v)
        even = sup.price_at_value(base, est["full_cost"])
        if price is None or even is None:
            return None
        fixed = v.c({**base, "unit_price": even}, est)
        other = complete_offer(cm.case, {**s, "unit_price": price})
        return other if v.ok(other) and v.c(other, est) < fixed * (1 - 0.002) else None

    def menu_sheet(self, cm, v, sheet):
        """For a supplier we hold no data on: the same package with the latest payment days at the
        price that costs us the same - it answers the sheet worth more to it."""
        days = cm.options.get("payment_days") or []
        if "payment_days" not in sheet or self.brief(cm, v).known or not days or self.payment_mode(cm, v) != "menu":
            return None
        late = max(days)
        if late <= sheet["payment_days"]:
            return None
        s = {**strip(sheet), "payment_days": late}
        price = cm.price_for(s, v.c(sheet), v.std)
        if price is None or price <= 0:
            return None
        other = complete_offer(cm.case, {**s, "unit_price": round(price, 2)})
        return other if v.ok(other) and other != sheet else None

    # ===========================================================================================
    # 4. close
    # ===========================================================================================
    def done(self, cm, v, rival=math.inf):
        if v.status in READY:
            return True
        p = self.plan(cm, v, rival)
        return p["capped"] or p["enough"]

    def ready(self, cm, v, rival=math.inf):
        """Nothing more to ask here and none of its other sheets is better."""
        if v.left <= 0:
            return True
        if v.standing[1].get("unit_price") is None:
            return False
        return self.done(cm, v, rival) and self.better_alternative(cm, v) is None

    def close(self, cm, live, cost):
        takable = [v for v in live if cost[v.sid] < math.inf]
        if not takable:
            return {"kind": "walk_away", "sid": live[0].sid, "reasons": ["no valid offer stands"]}
        best = min(takable, key=lambda v: cost[v.sid])
        if cm.c_alt < cost[best.sid]:
            return {"kind": "walk_away", "sid": live[0].sid, "reasons": ["our alternative is cheaper"]}
        return {"kind": "accept", "sid": best.sid, "accept_id": best.standing[0],
                "reasons": [f"cheapest valid standing offer, C {cost[best.sid]:,.0f}"]}  # fmt: skip

    # ===========================================================================================
    # the ask and its argument
    # ===========================================================================================
    def ask(self, cm, v, views, live, rival=math.inf):
        if v.standing[1].get("unit_price") is not None and self.done(cm, v, rival):
            alt = self.better_alternative(cm, v)
            if alt is not None:
                return {"kind": "take_alternative", "sid": v.sid, "sheets": [alt], "n": len(v.asks),
                        "reasons": ["its own alternative sheet is cheaper for us"]}  # fmt: skip
        p = self.plan(cm, v, rival)
        prices = [v.c(v.filled(m["term_sheets"][0]["terms"])) for m in v.theirs if m.get("term_sheets")]
        flags = {
            "they_moved": len(prices) > 1 and prices[-1] < prices[-2] - EPS,
            "asked_for_data": bool(ASKS_DATA.search(v.last.get("body") or "")),
        }
        sheets = [p["sheet"]]
        args = self.arguments(cm, v, views, live, p["sheet"])
        if not v.asks and v.opening:
            theirs, ours = v.opening_terms.get("contract_months"), p["sheet"].get("contract_months")
            if "contract_months" in cm.negotiable and ours and theirs is not None and ours > theirs:
                flags["commitment"] = f"{ours} months"
            secured = self.clause_sheet(cm, v, p["sheet"])
            if secured:
                sheets.append(secured)
                series = secured["index_clause"].get("series")
                args = [*args, f"With the index clause of the second option the price follows {series} beyond the deadband, "
                        "so that this risk does not have to be priced in up front."]  # fmt: skip
            menu = self.menu_sheet(cm, v, p["sheet"])
            if menu:
                sheets.append(menu)
        reasons = [f"target {p['target']:.2f} ({self.aim(cm, v)['source']}), ask {p['sheet']['unit_price']:.2f}"]
        return {"kind": "ask", "sid": v.sid, "sheets": sheets, "arguments": args, "n": len(v.asks), "flags": flags,
                "reasons": reasons}  # fmt: skip

    def hedged(self, cm, v, series):
        return not series.startswith(NOT_MATERIAL) and self.brief(cm, v).signal("material_hedged") > 0

    def arguments(self, cm, v, views, live, sheet):
        """At most one fact per e-mail; one never cited before in this case (a rival's offer may be
        cited to every other bidder)."""
        if not self.k["arguments"]:
            return []
        here = " ".join(m.get("body") or "" for m in v.ours)
        cited = {i for w in views.values() for m in w.ours for i in ID_RE.findall(m.get("body") or "")}
        _, standing = v.standing
        price = standing.get("unit_price")
        rivals = [w for w in live if w.sid != v.sid and w.standing[0] and w.ok(w.standing[1])]
        if rivals and price is not None:
            w = min(rivals, key=lambda w: w.standing[1]["unit_price"])
            offer_id, terms = w.standing
            if terms["unit_price"] < price and offer_id not in here:
                return [f"We hold a competing offer at EUR {terms['unit_price']:.2f} per unit ({offer_id})."]
        facts = self._facts(cm, v)
        own = self.part(cm, v).own_cost if self.part(cm, v) else None
        for f in facts:
            if f.kind == "cost" and f.extra.get("plant_specific") and own and f.ids[0] not in cited:
                if price is not None and price > own[1] * 1.02 and sheet["unit_price"] >= own[1]:
                    return [f.sentence]
        for kind in ("idx", "idx_recent"):
            if kind == "idx_recent" and not self.k["recent_fall"]:
                continue
            for f in facts:
                if f.kind == kind and f.helps and f.ids[-1] not in cited and not self.hedged(cm, v, f.extra["series"]):
                    return [f.sentence]
        return self._banked(cm, v, facts, cited, here, price)

    def _facts(self, cm, v):
        k = (cm.case.get("case_id"), v.sid, "facts")
        if k not in self._memo:
            if self.package is None or not self.k["data"]:
                self._memo[k] = []
            else:
                stated = re.findall(r"([A-Z][A-Z0-9.-]+) (?:rose|fell) \d", (v.opening or {}).get("body") or "")
                with knowledge.LOCK:
                    found = candidates(self.package, cm.case, v.sid, self.brief(cm, v), stated)
                # within a kind: the strongest first; the index facts keep the order of the drivers
                self._memo[k] = found
        return self._memo[k]

    def _banked(self, cm, v, facts, cited, here, price):
        topics = {i.split(":", 1)[0] for i in cited}
        topics = {{"ctr": "doc"}.get(t, t) for t in topics}
        named = set(cm.case.get("refs") or []) | set(knowledge.case_facts(cm.case))
        alt = cm.b.get("alternative") or {}
        if alt.get("ref"):
            named.add(alt["ref"])
        single = len(cm.case.get("parts") or []) == 1
        order = BANK_ORDER.get(cm.case.get("type"), DEFAULT_ORDER)
        ranked = []
        for f in facts:
            kind = "idx" if f.kind in ("idx6", "idx_recent") else f.kind
            if not f.helps or f.private or any(i in cited for i in f.ids) or f.sentence in here:
                continue
            if f.kind == "idx_recent" and not self.k["recent_fall"]:
                continue
            if kind == "idx" and self.hedged(cm, v, f.extra.get("series", "")):
                continue
            if f.case_only and not any(i in named for i in f.ids):
                continue
            if f.kind in ("cost", "quote") and single and price and f.figure is not None:
                if float(f.figure) >= float(price) * (0.98 if f.kind == "cost" else 1.0):
                    continue
            if f.kind == "quote":
                continue  # a quote reveals what we hold
            if f.topic in topics:
                continue  # the arena counts a topic once per case
            rank = order.index(kind) if kind in order else len(order)
            ranked.append((rank, -f.strength, f))
        ranked.sort(key=lambda r: (r[0], r[1]))
        if ranked:
            return [ranked[0][2].sentence]
        return []

    # ===========================================================================================
    # the message
    # ===========================================================================================
    def message(self, case, threads, draft):
        sid, kind = draft["sid"], draft["kind"]
        if kind == "walk_away":
            return {"supplier_id": sid, "message": {"action": {"type": "walk_away"}}}
        if kind == "accept":
            return {"supplier_id": sid, "message": {"action": {"type": "accept", "term_sheet_id": draft["accept_id"]}}}
        cm = CaseModel(case)
        view = Thread(cm, sid, threads[sid])
        sheets = []
        for terms in draft.get("sheets") or []:
            terms = complete_offer(case, terms)
            if terms.get("unit_price") and terms not in sheets and must_haves_ok(case, terms, view.std):
                sheets.append(terms)
        sheets = sheets[:3]
        if kind != "hold" and not sheets:
            draft = {**draft, "kind": "hold", "sheets": []}
        contact = self.brief(cm, view).contact if (case.get("case_id"), sid, "brief") in self._memo else knowledge.contact_name(view.opening)
        body = email(case, {**draft, "sheets": sheets}, contact)
        return {"supplier_id": sid,
                "message": {"subject": f"Re: {case['title']}"[:300], "body": body[:8000],
                            "term_sheets": [{"terms": s} for s in sheets]}}  # fmt: skip

    def rescue(self, case, threads, focus=None):
        """When our own code fails: a holding e-mail (valid, restarts the clock, the offer stands), or
        with no message left the kit's closing move. Never an exception to the runner."""
        live = live_threads(threads)
        sid = focus if focus in live else (live[0] if live else next(iter(threads)))
        if live and moves_left(case, threads[sid]) > 1:
            body = f"Dear Sir or Madam,\n\n{'thank you for your offer. We are reviewing it internally and will revert shortly.'}\n\nBest regards\nPurchasing, Hollerau Pumpenwerke"
            return {"supplier_id": sid, "message": {"subject": f"Re: {case['title']}"[:300], "body": body, "term_sheets": []}}
        if live:
            return closing_move(case, threads)
        return {"supplier_id": sid, "message": {"action": {"type": "walk_away"}}}


PROFIT_ROW = re.compile(r"profit|margin|gewinn|marge", re.I)
TOTAL_ROW = re.compile(r"^(unit )?price|^total|^sum", re.I)


def read_breakdown(text):
    """A supplier's cost breakdown (XLSX as text): {direct, profit} in EUR per unit, or None."""
    if not text or "breakdown" not in text.lower():
        return None
    elements, profit = {}, None
    for line in text.splitlines():
        cells = [c.strip() for c in line.split("|")]
        if len(cells) < 2 or TOTAL_ROW.search(cells[0]):
            continue
        try:
            value = float(cells[1].replace(",", "."))
        except ValueError:
            continue
        if PROFIT_ROW.search(cells[0]):
            profit = value
        else:
            elements[cells[0]] = value
    if not elements:
        return None
    return {"direct": round(sum(elements.values()), 4), "profit": profit}
