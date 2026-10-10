# ruff: noqa: E501  (long sentences and messages)
"""The negotiator behind `--agent sellm`.

Every decision is a pure function of the case file and the threads: what we asked before is read
from our own e-mails in the thread, nothing is counted in the object. So a second call for the same
state returns the same move, a fresh agent picks a case up after a crash, and `agent.fallback` is
the agent itself (its numbers need no LLM).

The price path follows what real suppliers did in the sandbox (docs/LOG.md Sat 18:22 and
experiments/RESULTS.md section 3):
- a supplier gives back a share of each step we make, for about six of our messages, then says
  `final_offer`; nothing is gained after that;
- an opening about 10 % or more below its floor costs half of those rounds; 5-7 % below does not;
- so: open a few percent below our estimate of its floor, concede in equal visible steps that reach
  the estimate after five of them, never close the remaining gap ourselves, accept its final offer.

Everything is measured in our total cost C, so the ask stays comparable when the non-price terms
change: we ask for its own terms where they cost us nothing to accept, cover the whole need, and
move to the structure of whichever of its sheets is cheapest for us.
"""

import itertools
import logging
import math
import os
import re
from datetime import date

from arena_kit.agents.llm import ID_RE
from arena_kit.cost import RELATIONSHIP_GOALS, closing_terms, complete_offer, must_haves_ok, supplier_value, total_cost
from arena_kit.docs import quote_terms, standard_terms
from arena_kit.play import ENDED, moves_left

from .writer import compose

log = logging.getLogger("sellm")

DEFAULTS = dict(
    open_below=0.06,  # we open this share below our target (steps of 1.2 %: 0.60 on D01 gave 0.95, 0.55 gave 0.89)
    rounds_to_floor=5,  # equal steps; the ask reaches the floor estimate after this many
    keep_below=0.006,  # never ask closer than this share to its standing offer: it should make the last move
    floor_share=None,  # our target as a share of its opening when no should-cost exists; None: TARGET_SHARE
    rate_guess=0.08,  # its cost of money when the dossier does not say (ours: no bias on payment days)
    claims="bank",  # none | bank (one new checked figure per e-mail)
    max_holds=1,  # holding e-mails to keep the best RFQ thread alive while the others still move, then we take it
    writer="template",
)
# Where deals could end, as a share of the supplier's opening price, when no should-cost of its own
# plant exists. Two numbers on purpose (few cases, so no finer split): cases with a relationship term,
# where the best deal stays above the supplier's cost (D01, P01, P02, P03: 0.92-0.98), and all others
# (P05, P07, P08, P11, D02: 0.82-0.93). The held-out cases P04, P10, P18 were not used. A prior of
# this kind is wrong by up to 10 % for a single supplier; the path below is built to lose little then
# (sensitivity: docs/LOG.md Sat 19:40), and a should-cost or dossier estimate replaces it where one exists.
TARGET_SHARE = {True: 0.945, False: 0.86}
# COUNTRY: for a later use of generic estimates
COUNTRY = {
    "AT": 1.05,
    "CH": 1.05,
    "CZ": 0.825,
    "PL": 0.825,
    "HU": 0.825,
    "TR": 0.75,
    "CN": 0.7,
}  # data/package/company.md
TOO_LOW = re.compile(
    r"far below|well below|below a feasible|not feasible, as they do not reflect|operational limits", re.I
)
ASKS_DATA = re.compile(r"which figures is that based on|send us the data|data supporting your assumptions", re.I)
READY = ("final_offer", "agreed")
EPS = 1e-6


def structures(case):
    """Every combination of the negotiable non-price fields over the case's options."""
    fields = [f for f in case["negotiable"] if f != "unit_price"]
    options = [case.get("term_options", {}).get(f) or [None] for f in fields]
    for combo in itertools.product(*options):
        yield {f: v for f, v in zip(fields, combo, strict=True) if v is not None or f == "index_clause"}


def _distance(a, b):
    if a == b:
        return 0.0
    if isinstance(a, bool) or isinstance(b, bool) or a is None or b is None:
        return 1.0
    if isinstance(a, int | float) and isinstance(b, int | float):
        return min(1.0, abs(a - b) / max(abs(b), 1.0))
    try:
        return min(1.0, abs((date.fromisoformat(a) - date.fromisoformat(b)).days) / 365)
    except (TypeError, ValueError):
        return 1.0


class Thread:
    """One supplier's thread, read once: what it offers, what we asked, what closes on its standard terms."""

    def __init__(self, case, sid, events):
        self.case, self.sid, self.events = case, sid, events
        self.theirs = [m for m in events if m.get("from") != "buyer"]
        self.ours = [m for m in events if m.get("from") == "buyer"]
        self.opening = next((m for m in self.theirs if m.get("term_sheets")), None)
        self.last = self.theirs[-1] if self.theirs else {}
        self.status = self.last.get("status")
        self.sheets = [s for s in self.last.get("term_sheets") or [] if s.get("terms")]
        self.asks = [m["term_sheets"][0]["terms"] for m in self.ours if m.get("term_sheets")]
        self.holds = sum(1 for m in self.ours if not m.get("term_sheets") and not m.get("action"))
        self.left = moves_left(case, events)
        std0 = {}
        for att in (self.opening or {}).get("attachments") or []:
            if att.get("name", "").startswith("quote") and att.get("text"):
                std0 = quote_terms(att["text"]).get("standard", {})
                break
        self.std0 = std0  # as quoted at the opening: the yardstick C_open is priced with these
        self.std = {**std0, **standard_terms(events)}  # later PDFs leave out what the offer now states

    @property
    def standing(self):
        """(term_sheet_id, terms) of its standing offer: only the first sheet can be accepted."""
        return (self.sheets[0].get("term_sheet_id"), self.sheets[0]["terms"]) if self.sheets else (None, {})

    def filled(self, terms):
        """Its sheet with every negotiable field: what it leaves out closes on its standard terms."""
        return complete_offer(self.case, {**self.std, **{k: v for k, v in terms.items() if v is not None}})

    def c(self, terms, estimate=None):
        if not terms or terms.get("unit_price") is None:
            return math.inf
        return total_cost(self.case, terms, self.std, estimate)

    def valid(self, terms):
        return bool(terms) and terms.get("unit_price") is not None and must_haves_ok(self.case, terms, self.std)

    def coverage(self, terms):
        """Share of the need over the horizon that a deal on these terms covers."""
        b, t = self.case["buyer"], closing_terms(self.case, terms, self.std)
        years = min(t["contract_months"] / 12 if t["contract_months"] else 1.0, b["horizon_years"])
        return min(t["volume_per_year"], b["need_per_year"]) * years / (b["need_per_year"] * b["horizon_years"])


class Negotiator:
    def __init__(self, package=None, writer=None, chat=None, dossier=None, **knobs):
        self.k = {**DEFAULTS, **knobs}
        if writer:
            self.k["writer"] = writer
        self.package, self.chat, self.dossier = package, chat, dossier
        self.fallback = self  # the numbers need no LLM, so the fallback is this agent
        self.stats = {"moves": 0, "errors": 0, "fallbacks": 0}
        self.name = "sellm " + " ".join(f"{k}={v}" for k, v in knobs.items())
        self._memo = {}

    # -- the kit's interface ---------------------------------------------------------------------
    def decide(self, case, threads, focus=None):
        """`focus` (one loop per thread) asks for a move in that thread."""
        try:
            draft = self.move(case, threads, focus)
            decision = self.message(case, threads, draft)
            self.stats["moves"] += 1
            return decision
        except Exception:
            if os.environ.get("SELLM_STRICT") == "1":
                raise
            self.stats["errors"] += 1
            log.exception("%s: the negotiator failed, sending a safe move", case.get("case_id"))
            return self.rescue(case, threads, focus)

    def rescue(self, case, threads, focus):
        """When our own code fails: a holding e-mail (valid, restarts the clock, the offer stands),
        or, with no message left, the kit's closing move. Never an exception to the runner."""
        from arena_kit.play import closing_move, live_threads

        live = live_threads(threads)
        sid = focus if focus in live else (live[0] if live else next(iter(threads)))
        if live and moves_left(case, threads[sid]) > 1:
            body = "Dear Sir or Madam,\n\nthank you for your offer. We are reviewing it internally and will revert shortly."
            return {
                "supplier_id": sid,
                "message": {"subject": f"Re: {case['title']}"[:300], "body": body, "term_sheets": []},
            }
        if live:
            return closing_move(case, threads)
        return {"supplier_id": sid, "message": {"action": {"type": "walk_away"}}}

    # -- the decision ----------------------------------------------------------------------------
    def move(self, case, threads, focus=None):
        """What to do next, as a draft: kind (ask, take_alternative, hold, accept, walk_away), the
        thread, the term sheets and the argument sentences."""
        views = {sid: Thread(case, sid, events) for sid, events in threads.items()}
        live = [v for v in views.values() if v.theirs and v.status not in ENDED]
        if not live:
            return {"kind": "walk_away", "sid": next(iter(threads))}
        key = (case.get("case_id"), "cheapest")
        if key not in self._memo:  # openings never change: the market level an RFQ bidder has to beat
            opened = [v.opening["term_sheets"][0]["terms"].get("unit_price") for v in views.values() if v.opening]
            self._memo[key] = min((p for p in opened if p), default=None)
        cost = {v.sid: self.offer_cost(case, v) for v in live}
        leader = min(live, key=lambda v: cost[v.sid]).sid
        agreed = [v for v in live if v.status == "agreed" and cost[v.sid] < math.inf]
        if agreed:  # it offers exactly our terms: take the cheapest such offer
            return self.close(case, views, live, cost, prefer=min(agreed, key=lambda v: cost[v.sid]).sid)
        movable = sorted((v for v in live if not self.ready(case, v)), key=lambda v: (len(v.ours), cost[v.sid]))
        if focus is not None and focus in views and views[focus] in live:
            v = views[focus]
            if v in movable:
                return self.ask(case, v, views, live)
            others = [m for m in movable if m.sid != focus]
            if v.sid == leader and others:  # the best offer must not time out while the others go on
                if v.holds < self.k["max_holds"] and v.left > 1:
                    return {"kind": "hold", "sid": v.sid, "sheets": [], "n": len(v.asks)}
                return self.close(case, views, live, cost, prefer=v.sid)
        if movable:  # with `focus` on a finished thread this is a move for another one: its own loop sends it
            return self.ask(case, movable[0], views, live)
        return self.close(case, views, live, cost)

    def offer_cost(self, case, v):
        """C of its standing offer, the relationship term priced with our estimate; inf if it cannot be taken."""
        sheet_id, terms = v.standing
        if not sheet_id or not v.valid(terms):
            return math.inf
        return v.c(terms, self.estimate(case, v))

    def ready(self, case, v):
        """Nothing more to ask in this thread: take or leave its standing offer."""
        if v.status in READY:
            return self.better_alternative(case, v) is None
        if v.left <= 0:
            return True
        if v.standing[1].get("unit_price") is None:
            return False  # it has not named a price yet
        plan = self.plan(case, v)
        return plan["capped"] or plan["enough"]

    def close(self, case, views, live, cost, prefer=None):
        """Accept the cheapest standing offer that keeps the must-haves, unless the alternative is the
        better deal. A deal no better than the opening scores 0, as walking away without an
        alternative does: then the deal is taken (a tie goes to more deals)."""
        alt = case["buyer"].get("alternative") or {}
        c_alt = total_cost(case, alt["terms"]) if (alt.get("terms") or {}).get("unit_price") else math.inf
        takable = [v for v in live if cost[v.sid] < math.inf]
        walk = {"kind": "walk_away", "sid": live[0].sid}
        if not takable:
            return walk
        best = next((v for v in takable if v.sid == prefer), None) or min(takable, key=lambda v: cost[v.sid])
        if c_alt < cost[best.sid]:
            cheaper = min(takable, key=lambda v: cost[v.sid])
            if c_alt < cost[cheaper.sid]:
                return walk
            best = cheaper
        return {"kind": "accept", "sid": best.sid, "accept_id": best.standing[0]}

    def ask(self, case, v, views, live):
        alt = self.better_alternative(case, v)
        if alt is not None:  # its own second package, sent back as ours: it answers `agreed`
            return {"kind": "take_alternative", "sid": v.sid, "sheets": [alt], "n": len(v.asks)}
        plan = self.plan(case, v)
        body_before = [m.get("body") or "" for m in v.theirs[:-1]]
        prices = [self.offer_cost_plain(v, m) for m in v.theirs if m.get("term_sheets")]
        flags = {
            "they_moved": len(prices) > 1 and prices[-1] < prices[-2] - EPS,
            "asked_for_data": bool(ASKS_DATA.search(v.last.get("body") or "")),
            "repeat_data_request": any(ASKS_DATA.search(b) for b in body_before),
        }
        if not v.asks and v.opening:
            theirs = v.filled(v.opening["term_sheets"][0]["terms"]).get("contract_months")
            ours = plan["sheet"].get("contract_months")
            if "contract_months" in case["negotiable"] and ours and theirs is not None and ours > theirs:
                flags["commitment"] = f"{ours} months"
        arguments = self.arguments(case, v, views, live, plan["sheet"]) if self.k["claims"] == "bank" else []
        return {
            "kind": "ask",
            "sid": v.sid,
            "sheets": [plan["sheet"]],
            "arguments": arguments,
            "n": len(v.asks),
            "flags": flags,
        }

    @staticmethod
    def offer_cost_plain(v, message):
        return v.c(v.filled(message["term_sheets"][0]["terms"]))

    def better_alternative(self, case, v):
        """At its final offer: one of its other sheets that is cheaper for us in total cost, keeps
        the must-haves, and that we have not sent back yet."""
        if v.status != "final_offer" or len(v.sheets) < 2 or v.left < 1:
            return None
        _, standing = v.standing
        base = v.c(v.filled(standing)) if standing.get("unit_price") is not None else math.inf
        best = None
        for sheet in v.sheets[1:]:
            terms = v.filled(sheet["terms"])
            if not v.valid(terms):
                continue
            c = v.c(terms)
            if c < base * (1 - 0.002) and (best is None or c < best[0]):
                best = (c, terms)
        if best is None or (v.asks and complete_offer(case, v.asks[-1]) == best[1]):
            return None
        return best[1]

    # -- the numbers -----------------------------------------------------------------------------
    def plan(self, case, v):
        """Our next ask in this thread: the structure, the sheet, whether we can still move without
        meeting its price (`capped`), and whether its offer is already as good as we want it
        (`enough`: strategic and bottleneck cases only, where a lower price costs us more in the
        relationship term than it saves)."""
        s0 = self.opening_structure(case, v)
        s = self.structure(case, v, s0)
        aim = self.aim(case, v, s0)
        step = aim["target"] * self.k["open_below"] / max(1, self.k["rounds_to_floor"])
        boost = min(6, 2 * sum(1 for m in v.theirs if TOO_LOW.search(m.get("body") or "")))
        path_price = aim["target"] * (1 - self.k["open_below"]) + (len(v.asks) + boost) * step
        target = v.c({**s0, "unit_price": path_price})  # the path, in our cost
        _, standing = v.standing
        their = v.c(v.filled(standing)) if standing.get("unit_price") is not None else math.inf
        last = v.c(v.asks[-1]) if v.asks else -math.inf
        target = min(target, their * (1 - self.k["keep_below"]))
        capped = bool(v.asks) and target <= last * (1 + EPS)
        target = max(target, last)
        c0, c1 = v.c({**s, "unit_price": 0.0}), v.c({**s, "unit_price": 1.0})
        price = (target - c0) / (c1 - c0) if c1 > c0 else path_price
        sheet = complete_offer(case, {**s, "unit_price": max(0.01, price)})
        enough = aim["stop_at_target"] and their <= v.c({**s0, "unit_price": aim["target"]}) * (1 + EPS)
        return {"sheet": sheet, "capped": capped, "enough": enough, "target": aim["target"], "structure": s}

    def opening_structure(self, case, v):
        """The terms of our first ask: its own terms, changed only where that covers the whole need
        or keeps a must-have. (Not the longest contract: suppliers charge for a term longer than
        they like, as the P07 supplier said of three years.)"""
        key = (case.get("case_id"), v.sid, "s0")
        if key in self._memo:
            return self._memo[key]
        theirs = v.opening["term_sheets"][0]["terms"] if v.opening else {}
        base = {f: x for f, x in v.filled(theirs).items() if f != "unit_price"}
        need = case["buyer"]["need_per_year"]
        candidates = []
        for s in structures(case):
            s = {f: x for f, x in complete_offer(case, {**base, **s, "unit_price": 1.0}).items() if f != "unit_price"}
            if must_haves_ok(case, {**s, "unit_price": 1.0}, v.std):
                candidates.append(s)
        if not candidates:
            self._memo[key] = base
            return base

        def rank(s):  # cover the need, commit no more than the need, else stay as close to its terms as possible
            t = closing_terms(case, {**s, "unit_price": 1.0}, v.std)
            away = sum(_distance(s.get(f), base.get(f)) for f in s)
            return (
                -round(v.coverage({**s, "unit_price": 1.0}), 6),
                max(0, t["volume_per_year"] - need),
                round(away, 6),
                t["contract_months"],
            )

        self._memo[key] = min(candidates, key=rank)
        return self._memo[key]

    def structure(self, case, v, s0):
        """After its first answer: the structure of whichever of its sheets is cheapest for us at the
        price it quotes - its standing sheet, an alternative, or its opening if our own structure
        turned out dearer than that - provided it keeps the must-haves. Our total cost decides (it
        prices uncovered need at the fallback), so a shorter contract wins only where buying the
        rest elsewhere is really cheaper. Our ask stays the same in cost; only a clear gain (0.2 %)
        changes the structure."""
        if not v.asks:
            return s0
        previous = {f: x for f, x in complete_offer(case, v.asks[-1]).items() if f != "unit_price"}
        quoted = [sheet["terms"] for sheet in v.sheets]
        if v.opening and len(v.theirs) > 1:
            quoted.append(v.opening["term_sheets"][0]["terms"])
        options = []
        for raw in quoted:
            terms = v.filled(raw)
            if terms.get("unit_price") is None or not v.valid(terms):
                continue
            options.append((v.c(terms), {f: x for f, x in terms.items() if f != "unit_price"}))
        if not options:
            return previous
        stay = next((o for o in options if o[1] == previous), options[0])
        best = min(options, key=lambda o: o[0])
        return best[1] if best[0] < stay[0] * (1 - 0.002) else stay[1]

    def full_standard(self, case, v):
        """Its standard terms with every field the cost and value functions read."""
        theirs = v.opening["term_sheets"][0]["terms"] if v.opening else {}
        std = {**{f: x for f, x in theirs.items() if f != "unit_price" and x is not None}, **v.std}
        out = closing_terms(case, std, std)
        out.pop("unit_price", None)
        return out

    def supplier(self, case, v):
        key = (case.get("case_id"), v.sid, "supplier")
        if key not in self._memo:
            self._memo[key] = {"standard": self.full_standard(case, v), "interest_rate": self.rate(case, v)}
        return self._memo[key]

    def rate(self, case, v):
        return self.k["rate_guess"]

    def value(self, case, v, terms):
        return supplier_value(case, terms, self.supplier(case, v))

    def aim(self, case, v, s0):
        """Where we want the price to end, on our opening structure, and our estimate of its full cost.

        With a should-cost estimate of its own plant: its full cost; in strategic and bottleneck
        cases the price above it where our total cost is lowest (below that, the relationship term
        costs more than the price saves). Without one: a share of the opening, by category goal -
        in an RFQ a share of the cheapest opening, the level every bidder has to beat."""
        key = (case.get("case_id"), v.sid, "aim")
        if key in self._memo:
            return self._memo[key]
        b = case["buyer"]
        relationship = (
            b.get("category_goal") in RELATIONSHIP_GOALS
            and b.get("relationship_eur_per_point")
            and b.get("sustainable_margin_pct")
        )
        _, standing = v.standing
        own = v.opening["term_sheets"][0]["terms"].get("unit_price") if v.opening else None
        reference = (
            own or standing.get("unit_price") or b.get("current_unit_price") or b.get("fallback_unit_price") or 1.0
        )
        market = self._memo.get((case.get("case_id"), "cheapest")) or reference
        v0 = self.value(case, v, {**s0, "unit_price": 0.0})
        v1 = self.value(case, v, {**s0, "unit_price": 1.0})
        estimate = self.should_cost(case, v.sid)
        if estimate and v1 > v0:
            source, full = estimate[0], estimate[1]
            target = (full - v0) / (v1 - v0)  # the price that pays it exactly its full cost
            if relationship:
                supplier = {**self.supplier(case, v), "full_cost": full}
                top = max(reference, target * 1.25)
                grid = [target + (top - target) * i / 250 for i in range(251)]
                target = min(grid, key=lambda p: v.c({**s0, "unit_price": p}, supplier))
        else:
            source = "prior"
            share = self.k["floor_share"] or TARGET_SHARE[bool(relationship)]
            target = share * min(reference, market)
            full = self.value(case, v, {**s0, "unit_price": target})
            if relationship:  # the prior is where deals ended, which lies above its full cost
                one_pct = b["need_per_year"] * target / 100
                gap = (
                    5.0 if b["relationship_eur_per_point"] <= one_pct else 5 * one_pct / b["relationship_eur_per_point"]
                )
                full *= 1 - max(0.0, b["sustainable_margin_pct"] - gap) / 100
        target = min(target, reference * 0.985)
        if not (math.isfinite(target) and target > 0):
            target = reference * 0.9
        self._memo[key] = {"target": target, "full_cost": full, "source": source, "stop_at_target": bool(relationship)}
        return self._memo[key]

    def should_cost(self, case, sid):
        """(fact ID, unit cost) of this supplier's own plant for a single-part case, else None. A
        generic estimate or another plant's is neither its floor nor citable to it."""
        if len(case.get("parts") or []) != 1:
            return None
        part = case["parts"][0]
        number = part.split(":", 1)[1]
        for ref, fact in (case.get("facts") or {}).items():
            if ref.startswith("cost:") and fact.get("unit_cost") and fact.get("part") in (part, number, None):
                if fact.get("supplier") in (None, sid) and fact.get("supplier_id") in (None, sid):
                    return ref, float(fact["unit_cost"])
        if not self.package:
            return None
        try:
            rows = self.package.query("select id, supplier_id, unit_cost from should_cost where part_id = ?", (part,))
        except Exception:
            return None
        own = next((r for r in rows if r.get("supplier_id") == sid and r.get("unit_cost")), None)
        return (own["id"], float(own["unit_cost"])) if own else None

    def estimate(self, case, v):
        """The supplier as the relationship term needs it (strategic and bottleneck goals only)."""
        if case["buyer"].get("category_goal") not in RELATIONSHIP_GOALS or not v.opening:
            return None
        if v.opening["term_sheets"][0]["terms"].get("unit_price") is None:
            return None
        aim = self.aim(case, v, self.opening_structure(case, v))
        return {**self.supplier(case, v), "full_cost": aim["full_cost"]}

    # -- the arguments ---------------------------------------------------------------------------
    def arguments(self, case, v, views, live, sheet):
        """At most one new argument per e-mail, its figure next to its ID in one sentence. An ID
        counts once per case; a rival's standing offer may be cited to each other bidder."""
        ours_here = " ".join(m.get("body") or "" for m in v.ours)
        cited = {i for w in views.values() for m in w.ours for i in ID_RE.findall(m.get("body") or "")}
        _, standing = v.standing
        price = standing.get("unit_price")
        rivals = [w for w in live if w.sid != v.sid and w.standing[0] and w.valid(w.standing[1])]
        if rivals and price is not None:
            rival = min(rivals, key=lambda w: w.standing[1]["unit_price"])
            offer_id, terms = rival.standing
            if terms["unit_price"] < price and offer_id not in ours_here:
                return [f"We hold a competing offer at EUR {terms['unit_price']:.2f} per unit ({offer_id})."]
        estimate = self.should_cost(case, v.sid)
        if estimate and estimate[0] not in cited:
            if price is not None and price > estimate[1] * 1.02 and sheet["unit_price"] >= estimate[1]:
                return [
                    f"Our bottom-up estimate of the full cost is EUR {estimate[1]:.2f} per unit before margin ({estimate[0]})."
                ]
        for ref, sentence in self.index_claims(case):
            if ref not in cited:
                return [sentence]
        return []

    def index_claims(self, case):
        """Cost-driver indices of the case's parts that fell over the last twelve months of their series."""
        key = (case.get("case_id"), "idx")
        if key in self._memo:
            return self._memo[key]
        out = []
        parts = case.get("parts") or []
        if self.package and parts:
            try:
                marks = ",".join("?" * len(parts))
                rows = self.package.query(
                    f"select distinct series_id from cost_drivers where part_id in ({marks})", tuple(parts)
                )
                for r in rows:
                    ids = self.package.ids(f"idx:{r['series_id']}@")
                    if len(ids) < 13:
                        continue
                    a, b = ids[-13], ids[-1]
                    change = (self.package.lookup(b)["value"] / self.package.lookup(a)["value"] - 1) * 100
                    if change < -0.5:  # worded as the kit's worked example, which the arena verified
                        months = (a.split("@", 1)[1], b.split("@", 1)[1])
                        out.append(
                            (
                                b,
                                f"The index {r['series_id']} changed {change:+.1f} % from {months[0]} to {months[1]} ({a}, {b}).",
                            )
                        )
            except Exception:  # an argument less, never a lost move
                log.warning("%s: index arguments not available", case.get("case_id"))
        self._memo[key] = out
        return out

    # -- the message -----------------------------------------------------------------------------
    def message(self, case, threads, draft):
        sid, kind = draft["sid"], draft["kind"]
        if kind == "walk_away":
            return {"supplier_id": sid, "message": {"action": {"type": "walk_away"}}}
        if kind == "accept":
            return {"supplier_id": sid, "message": {"action": {"type": "accept", "term_sheet_id": draft["accept_id"]}}}
        view = Thread(case, sid, threads[sid])
        sheets = []
        for terms in draft.get("sheets") or []:
            terms = complete_offer(case, terms)
            if terms.get("unit_price") and terms not in sheets and must_haves_ok(case, terms, view.std):
                sheets.append(terms)
        sheets = sheets[:3]
        if kind != "hold" and not sheets:  # nothing valid to ask: keep the thread alive instead
            draft = {**draft, "kind": "hold", "sheets": []}
        body, meta = compose(
            case, {**draft, "sheets": sheets}, threads[sid], self.chat if self.k["writer"] == "llm" else None
        )
        if meta.get("fallback"):
            self.stats["fallbacks"] += 1
            log.warning("%s %s: e-mail written by the template (%s)", case.get("case_id"), sid, meta["fallback"])
        log.info("%s %s: %s %s", case.get("case_id"), sid, draft["kind"], [s.get("unit_price") for s in sheets])
        return {
            "supplier_id": sid,
            "message": {
                "subject": f"Re: {case['title']}"[:300],
                "body": body[:8000],
                "term_sheets": [{"terms": s} for s in sheets],
            },
        }
