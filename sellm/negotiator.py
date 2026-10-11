# ruff: noqa: E501  (long sentences and messages)
"""The negotiator behind `--agent sellm`.

Every decision is a pure function of the case file and the threads: what we asked before is read
from our own e-mails in the thread, nothing is counted in the object. So a second call for the same
state returns the same move, a fresh agent picks a case up after a crash, and `agent.fallback` is
the agent itself (its numbers need no LLM).

The price path follows what real suppliers did in the sandbox (docs/LOG.md Sat 18:22 and 20:30,
experiments/RESULTS.md section 3):
- a supplier gives back a share of each step we make (the foundry in D01 about half, the job shop
  in D02 all of it, and it asks for "bigger steps" when ours are small against the gap), for four
  to six of our messages, then says `final_offer`; nothing is gained after that;
- an opening about 10 % or more below its floor costs half of those rounds; 5-7 % below does not;
- so: open a few percent below our estimate of where it can end, then size every step from what
  the thread shows - the gap to its price, the rounds left and the share of our steps it has given
  back so far - so that the two prices meet at the last round. No step size is fixed in advance.
  We never ask at or above its price, and we accept its final offer.

The terms around the price come from the cost calculator (`sellm/calculator.py`): our first ask is
the package that costs us least at the price we expect to end at - C prices uncovered need at the
fallback, so it decides how long and how much to commit, and it wants payment as late as possible.
Payment days are cash to the supplier too: we ask for the latest ones only from a supplier the
dossier calls relaxed about cash, keep the quoted ones for one short of cash, and send both as two
offers that cost us the same when we know nothing about it (a supplier answers the offer worth most
to it). Real suppliers answer on the structure we send and put their price on it (294 of 304
replies in runs/); from then on we ask on whichever structure it has quoted that is cheapest for
us in C. The price path runs in price; C decides between structures and between offers.
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

from . import calculator
from .writer import compose

log = logging.getLogger("sellm")

DEFAULTS = dict(
    open_below=0.06,  # we open this share below our estimate of where it can end
    horizon=4,  # our messages until the prices should meet: suppliers said `final_offer` after 1 to 6 of them (median 4)
    pace=0.5,  # the share of our steps a supplier gives back, until the thread has shown its own
    keep_below=0.006,  # never ask closer than this share to its standing offer: it should make the last move
    floor_share=None,  # our target as a share of its opening when no should-cost exists; None: TARGET_SHARE
    rate_guess=0.08,  # its cost of money when the dossier does not say (ours: no bias on payment days)
    claims="bank",  # none | bank (one new checked figure per e-mail)
    max_holds=2,  # holding e-mails per RFQ thread whose offer waits while the others still move; then we close
    levers="ours",  # first ask: ours (the calculator's cheapest package) | theirs (its terms, need covered)
    dossier=True,  # read its cost of money and cash position from sellm.intel when a dossier exists
    second_choice=False,  # ask once for our cheapest option of a field the supplier changed. Off: measured on
    # practice Sat 21:45 - one supplier gave the wider deadband for nothing (+0.06), another charged its worth or
    # ignored it and said final_offer a round earlier (-0.10 three times)
    recent_cap=True,  # without a cost estimate: aim no higher than its lowest own price of the last twelve months
    bank=True,  # when no rival offer, should-cost or falling index applies: the next fact of sellm.claims
    one_per_topic=True,  # the arena calls a second fact of a topic (forecast, complaint ...) `duplicate`
    ppm="plain",  # ppm figures without a thousands comma ("2,376 ppm" came back contradicted 3 of 3): plain | skip | asis
    signals=True,  # the dossier's signals move the share of its opening we aim at (see `share`)
    writer="template",
    contract="longest",  # where C does not care how long we commit: longest | horizon (the shortest option that covers it)
    idx_recent=None,  # a % (e.g. 2.0): also cite a cost-driver index that fell at least this much from its peak of the last 12 months
    gate=False,  # leave out a fact the supplier's dossier says it will dismiss (see `dismissed`)
)
# Where deals could end, as a share of the supplier's opening price, when no should-cost of its own
# plant exists. Two numbers on purpose (few cases, so no finer split): cases with a relationship term,
# where the best deal stays above the supplier's cost (D01, P01, P02, P03: 0.92-0.98), and all others
# (P05, P07, P08, P11, D02: 0.82-0.97). The held-out cases P04, P10, P18 were not used. A prior of
# this kind is wrong by up to 10 % for a single supplier. It only sets our first ask: every later
# step is sized from the thread itself, and a should-cost of its own plant replaces it where one exists.
TARGET_SHARE = {True: 0.945, False: 0.88}
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
# what a deal is worth to the supplier in cash (arena_kit.cost.supplier_value): we do not ask these for free
CASH_FIELDS = ("payment_days", "incoterm", "tooling_eur", "chargeback_eur_per_complaint")
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


def _key(structure):
    return tuple(sorted((f, repr(x)) for f, x in structure.items()))


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
    def fresh(self):
        """Its last e-mail answers a holding e-mail of ours: the offer ID we see is the current one."""
        if len(self.events) < 2:
            return False
        ours = self.events[-2]
        return ours.get("from") == "buyer" and not ours.get("term_sheets") and not ours.get("action")

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
        if isinstance(dossier, bool):  # make_agent(package, dossier=False): the knob, not an object
            self.k["dossier"] = dossier
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
        key = (case.get("case_id"), "openings")
        if key not in self._memo:  # every bidder's opening e-mail, which the dossier's case overlay reads (rivals too)
            self._memo[key] = {w.sid: [w.opening] for w in views.values() if w.opening}
        key = (case.get("case_id"), "cheapest")
        if key not in self._memo:  # openings never change: the market level an RFQ bidder has to beat
            opened = [v.opening["term_sheets"][0]["terms"].get("unit_price") for v in views.values() if v.opening]
            self._memo[key] = min((p for p in opened if p), default=None)
        cost = {v.sid: self.offer_cost(case, v) for v in live}
        leader = min(live, key=lambda v: cost[v.sid]).sid
        # what a bidder has to beat: the cheapest standing offer of the others (plain C, as the arena scores it)
        plain = {v.sid: v.c(v.filled(v.standing[1])) if cost[v.sid] < math.inf else math.inf for v in live}
        rival = {v.sid: min((plain[w.sid] for w in live if w.sid != v.sid), default=math.inf) for v in live}
        movable = sorted(
            (v for v in live if not self.ready(case, v, rival[v.sid])), key=lambda v: (len(v.ours), cost[v.sid])
        )
        if focus is not None and focus in views and views[focus] in live:
            v = views[focus]
            if v in movable:
                return self.ask(case, v, views, live, rival[v.sid])
            if movable:  # its offer waits while other threads still move: it must not time out meanwhile
                if cost[v.sid] < math.inf and v.holds < self.k["max_holds"] and v.left > 1:
                    return {"kind": "hold", "sid": v.sid, "sheets": [], "n": len(v.asks)}
                if views[leader] not in movable:  # the others have had their extra rounds: take the best offer
                    return self.close(case, views, live, cost)
        if movable:  # with `focus` on a waiting thread this is a move for another one: its own loop sends it
            return self.ask(case, movable[0], views, live, rival[movable[0].sid])
        draft = self.close(case, views, live, cost)
        if focus is None and len(views) > 1 and draft["kind"] == "accept":
            # A runner that serves one thread at a time (the kit's `play()`) lets the others time out,
            # and a timeout replaces the offer ID: accepting the old one is refused (422) and stops the
            # kit's runner. A holding e-mail first brings this thread's state up to date - it is
            # answered at once, or refused as late with the new offer - and then the accept is valid.
            v = views[draft["sid"]]
            if not v.fresh and v.left > 1:
                return {"kind": "hold", "sid": v.sid, "sheets": [], "n": len(v.asks)}
        return draft

    def offer_cost(self, case, v):
        """C of its standing offer, the relationship term priced with our estimate; inf if it cannot be taken."""
        sheet_id, terms = v.standing
        if not sheet_id or not v.valid(terms):
            return math.inf
        return v.c(terms, self.estimate(case, v))

    def done(self, case, v, rival=math.inf):
        """We have nothing more to ask here: it said its last word, or our next step would meet its
        price or no longer beat the best other offer."""
        if v.status in READY:
            return True
        plan = self.plan(case, v, rival)
        return plan["capped"] or plan["enough"]

    def ready(self, case, v, rival=math.inf):
        """Take or leave its standing offer: nothing more to ask, and none of its other sheets is better."""
        if v.left <= 0:
            return True
        if v.standing[1].get("unit_price") is None:
            return False  # it has not named a price yet
        return self.done(case, v, rival) and self.better_alternative(case, v) is None

    def close(self, case, views, live, cost):
        """Accept the cheapest standing offer that keeps the must-haves - whether it is called final,
        agreed or still open - unless the alternative is the better deal. A deal no better than the
        opening scores 0, as walking away without an alternative does: then the deal is taken (a tie
        goes to more deals)."""
        alt = case["buyer"].get("alternative") or {}
        c_alt = total_cost(case, alt["terms"]) if (alt.get("terms") or {}).get("unit_price") else math.inf
        takable = [v for v in live if cost[v.sid] < math.inf]
        if not takable:
            return {"kind": "walk_away", "sid": live[0].sid}
        best = min(takable, key=lambda v: cost[v.sid])
        if c_alt < cost[best.sid]:
            return {"kind": "walk_away", "sid": live[0].sid}
        return {"kind": "accept", "sid": best.sid, "accept_id": best.standing[0]}

    def ask(self, case, v, views, live, rival=math.inf):
        if v.standing[1].get("unit_price") is not None and self.done(case, v, rival):
            alt = self.better_alternative(case, v)
            if alt is not None:  # its own second package, sent back as ours: it answers `agreed`
                return {"kind": "take_alternative", "sid": v.sid, "sheets": [alt], "n": len(v.asks)}
        plan = self.plan(case, v, rival)
        body_before = [m.get("body") or "" for m in v.theirs[:-1]]
        prices = [self.offer_cost_plain(v, m) for m in v.theirs if m.get("term_sheets")]
        flags = {
            "they_moved": len(prices) > 1 and prices[-1] < prices[-2] - EPS,
            "asked_for_data": bool(ASKS_DATA.search(v.last.get("body") or "")),
            "repeat_data_request": any(ASKS_DATA.search(b) for b in body_before),
        }
        if self.k.get("opening_line"):  # experiments on wording only (experiments/ab_sandbox.py)
            flags["opening_line"] = self.k["opening_line"]
        if not v.asks and v.opening:
            theirs = v.filled(v.opening["term_sheets"][0]["terms"]).get("contract_months")
            ours = plan["sheet"].get("contract_months")
            if "contract_months" in case["negotiable"] and ours and theirs is not None and ours > theirs:
                flags["commitment"] = f"{ours} months"
        arguments = self.arguments(case, v, views, live, plan["sheet"]) if self.k["claims"] == "bank" else []
        return {
            "kind": "ask",
            "sid": v.sid,
            "sheets": [plan["sheet"], *(self.menu(case, v, plan["sheet"]) if not v.asks else [])],
            "arguments": arguments,
            "n": len(v.asks),
            "flags": flags,
        }

    @staticmethod
    def offer_cost_plain(v, message):
        return v.c(v.filled(message["term_sheets"][0]["terms"]))

    def better_alternative(self, case, v):
        """When we are done asking: one of its other sheets that is cheaper for us in total cost,
        keeps the must-haves, and that we have not sent back yet. Only its first sheet can be accepted."""
        if v.status == "agreed" or len(v.sheets) < 2 or v.left < 1:
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
    def plan(self, case, v, rival=math.inf):
        """Our next ask in this thread: the structure, the sheet, whether we can still move without
        meeting its price or losing to `rival`, the cost of the best other bidder's standing offer
        (`capped`), and whether its offer is already as good as we want it
        (`enough`: strategic and bottleneck cases only, where a lower price costs us more in the
        relationship term than it saves)."""
        s0 = self.opening_structure(case, v)
        s = self.structure(case, v, s0)
        aim = self.aim(case, v, s0)
        last = complete_offer(case, v.asks[-1]) if v.asks else None
        _, standing = v.standing
        their = v.c(v.filled(standing)) if standing.get("unit_price") is not None else math.inf
        quoted = self.quoted(case, v).get(_key(s))
        if quoted is not None:  # it has put a price on this structure: stay visibly below it
            ceiling = quoted * (1 - self.k["keep_below"])
        elif their < math.inf:  # else stay below its standing offer, in our cost and in price
            c0, c1 = v.c({**s, "unit_price": 0.0}), v.c({**s, "unit_price": 1.0})
            ceiling = (their * (1 - self.k["keep_below"]) - c0) / (c1 - c0) if c1 > c0 else math.inf
            if v.asks:
                ceiling = min(ceiling, standing["unit_price"] * (1 - self.k["keep_below"]))
        else:
            ceiling = math.inf
        if rival < math.inf:  # an ask that does not beat the best other offer is worth nothing to us
            c0, c1 = v.c({**s, "unit_price": 0.0}), v.c({**s, "unit_price": 1.0})
            if c1 > c0:
                ceiling = min(ceiling, (rival * (1 - self.k["keep_below"]) - c0) / (c1 - c0))
        if last is None:
            price = aim["target"] * (1 - self.k["open_below"])
        elif ceiling < math.inf:
            # the two prices should meet at the last round: each round closes our step plus its answer
            rounds = max(1, self.k["horizon"] - len(v.asks))
            if TOO_LOW.search(v.last.get("body") or ""):  # it calls our ask not serious: move at once
                rounds = 1
            step = (ceiling - last["unit_price"]) / (rounds * (1 + self.pace(case, v)))
            price = last["unit_price"] + max(step, 0.0)  # never below our own last price
        else:
            price = last["unit_price"]
        same = last is not None and {f: x for f, x in last.items() if f != "unit_price"} == s
        price = min(price, ceiling)
        if same:  # on an unchanged structure our price never goes back, whatever it quotes
            price = max(price, last["unit_price"])
        price = round(max(0.01, price), 2)
        capped = same and price <= last["unit_price"] + EPS  # no visible step left below its price
        sheet = complete_offer(case, {**s, "unit_price": price})
        enough = aim["stop_at_target"] and their <= v.c({**s0, "unit_price": aim["target"]}) * (1 + EPS)
        return {"sheet": sheet, "capped": capped, "enough": enough, "target": aim["target"], "structure": s}

    def pace(self, case, v):
        """The share of our steps it has given back so far in this thread, on an unchanged structure
        (0.25 to 2); our guess until two of our asks and two of its answers allow a measurement."""
        rounds = []  # (our ask, its answer) per round, as (structure, price)
        asked = None
        for m in v.events:
            sheets = m.get("term_sheets") or []
            if m.get("from") == "buyer":
                asked = complete_offer(case, sheets[0]["terms"]) if sheets else asked
            elif asked is not None and sheets:
                answer = v.filled(sheets[0]["terms"])
                if answer.get("unit_price") is not None:
                    rounds.append((asked, answer))
                asked = None
        same = [
            r
            for r in rounds
            if _key({f: x for f, x in r[0].items() if f != "unit_price"})
            == _key({f: x for f, x in rounds[-1][0].items() if f != "unit_price"})
            and _key({f: x for f, x in r[1].items() if f != "unit_price"})
            == _key({f: x for f, x in rounds[-1][1].items() if f != "unit_price"})
        ]
        if len(same) < 2:
            return self.k["pace"]
        ours = same[-1][0]["unit_price"] - same[0][0]["unit_price"]
        theirs = same[0][1]["unit_price"] - same[-1][1]["unit_price"]
        if ours <= EPS:
            return self.k["pace"]
        return min(2.0, max(0.25, theirs / ours))

    def quoted(self, case, v):
        """The price it has put on each structure: its latest sheets, and its opening."""
        out = {}
        sheets = [sheet["terms"] for sheet in v.sheets]
        if v.opening and len(v.theirs) > 1:
            sheets.append(v.opening["term_sheets"][0]["terms"])
        for raw in sheets:
            terms = v.filled(raw)
            if terms.get("unit_price") is not None:
                out.setdefault(_key({f: x for f, x in terms.items() if f != "unit_price"}), terms["unit_price"])
        return out

    def opening_structure(self, case, v):
        """The terms of our first ask. `ours`: its cash terms as quoted, every other field at the
        value that is cheapest for us at its opening price - C prices uncovered need at the fallback,
        so it decides how long and how much to commit; where C does not care, its own terms.
        `theirs`: its own terms, changed only to cover the need and keep the must-haves."""
        key = (case.get("case_id"), v.sid, "s0")
        if key in self._memo:
            return self._memo[key]
        theirs = v.opening["term_sheets"][0]["terms"] if v.opening else {}
        base = {f: x for f, x in v.filled(theirs).items() if f != "unit_price"}
        b = case["buyer"]
        need = b["need_per_year"]
        price = theirs.get("unit_price") or b.get("current_unit_price") or b.get("fallback_unit_price") or 1.0
        candidates = []
        for s in structures(case):
            s = {f: x for f, x in complete_offer(case, {**base, **s, "unit_price": 1.0}).items() if f != "unit_price"}
            if s not in candidates and must_haves_ok(case, {**s, "unit_price": 1.0}, v.std):
                candidates.append(s)
        if not candidates:
            self._memo[key] = base
            return base

        def away(s):
            return round(sum(_distance(s.get(f), base.get(f)) for f in s), 6)

        if self.k["levers"] == "ours":
            share = self.share(case, v, b.get("category_goal") in RELATIONSHIP_GOALS)
            keep = {f: base[f] for f in CASH_FIELDS if f in base and f != "payment_days"}
            if "payment_days" in base and self.cash(case, v) != "low":
                keep["payment_days"] = base["payment_days"]  # not known to be relaxed about cash: its own days
            ranked = calculator.packages(case, v.std, price * share, keep) or calculator.packages(
                case, v.std, price * share
            )
            if not ranked:
                self._memo[key] = base
                return base
            cheapest = ranked[0][0]
            near = [s for c, s in ranked if c <= cheapest * (1 + 1e-4)]  # C does not care: commit longer, stay closer
            best = min(near, key=lambda s: (-(s.get("contract_months") or 0), away(s)))
            covering = [s for s in near if (s.get("contract_months") or 0) >= 12 * b["horizon_years"]]
            if self.k["contract"] == "horizon" and covering:  # no longer than the horizon: a longer fixed price is a risk it prices
                best = min(covering, key=lambda s: (s.get("contract_months") or 0, away(s)))
            if self.cash(case, v) in ("medium", "high"):
                best = self.payment_trade(case, v, best, price * share)
            self._memo[key] = best
            return best

        def rank(s):  # cover the need, commit no more than the need, else stay as close to its terms as possible
            t = closing_terms(case, {**s, "unit_price": 1.0}, v.std)
            return (
                -round(v.coverage({**s, "unit_price": 1.0}), 6),
                max(0, t["volume_per_year"] - need),
                away(s),
                t["contract_months"],
            )

        self._memo[key] = min(candidates, key=rank)
        return self._memo[key]

    def share(self, case, v, relationship):
        """Where we expect a deal to end, as a share of its opening, when no should-cost of its own
        plant exists. The dossier's reading of the supplier moves it (docs/PLAN.md section 10): a
        list price it cannot move or a margin it will not give up puts the end close to its opening,
        a supplier that wants volume deeper. Measured on practice Sat 21:30 (experiments/
        PRACTICE-ARMS.md, F8): better in two cases, equal in one - but formulated with those cases'
        floors known, so the hidden suppliers have to confirm it."""
        base = self.k["floor_share"] or TARGET_SHARE[bool(relationship)]
        if not self.k["signals"]:
            return base
        found = self.intel(case, v)
        if found.get("coverage") != "full":
            return base
        kinds = {sig.get("kind"): sig.get("strength") or 0 for sig in found.get("signals") or []}
        if kinds.get("list_price_fixed", 0) >= 2 or kinds.get("margin_floor", 0) >= 1:
            return max(base, 0.96)
        if kinds.get("wants_volume", 0) >= 2:
            return min(base, 0.84)
        return base

    def payment_trade(self, case, v, s, price):
        """Payment days are cash to both sides, at different rates: where its cost of money (dossier)
        is far from ours, the days that leave it the same worth cost us less - faster payment for a
        supplier short of cash, slower for one that borrows cheaply. Only a clear gain (0.3 % of C):
        a rate guessed from the owner type alone does not reach it."""
        if "payment_days" not in s or self.k["rate_guess"] == self.supplier(case, v)["interest_rate"]:
            return s
        worth = self.value(case, v, {**s, "unit_price": price})
        best = (v.c({**s, "unit_price": price}), s)
        for days in case.get("term_options", {}).get("payment_days") or []:
            t = {**s, "payment_days": days}
            v0, v1 = self.value(case, v, {**t, "unit_price": 0.0}), self.value(case, v, {**t, "unit_price": 1.0})
            if v1 <= v0 or not must_haves_ok(case, {**t, "unit_price": 1.0}, v.std):
                continue
            cost = v.c({**t, "unit_price": (worth - v0) / (v1 - v0)})
            if cost < best[0] * (1 - 0.003):
                best = (cost, t)
        return best[1]

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
        chosen = best if best[0] < stay[0] * (1 - 0.002) else stay
        return self.second_choice(case, v, chosen[1]) if self.k["second_choice"] else chosen[1]

    def refused(self, case, v):
        """{field: [values]} we asked and it changed in its answer. An answer on one of our own
        sheets refuses nothing."""
        out, asked = {}, None
        for m in v.events:
            sheets = m.get("term_sheets") or []
            if m.get("from") == "buyer":
                if sheets:
                    asked = [complete_offer(case, sheet["terms"]) for sheet in sheets]
            elif asked and sheets:
                answer = {f: x for f, x in v.filled(sheets[0]["terms"]).items() if f != "unit_price"}
                if all({f: x for f, x in a.items() if f != "unit_price"} != answer for a in asked):
                    for field, value in answer.items():
                        ours = asked[0].get(field)
                        if ours != value and ours not in out.setdefault(field, []):
                            out[field].append(ours)
                asked = None
        return {f: values for f, values in out.items() if values}

    def second_choice(self, case, v, structure):
        """Where it changed a field of our ask, its replacement is its choice, not the only one it
        takes: we ask once for the option of that field that costs us least (it turned a fixed price
        into an index clause without a deadband; the clause with the widest deadband costs us a
        third of that). If it changes the field again, we take its value."""
        _, standing = v.standing
        price = standing.get("unit_price")
        if price is None:
            return structure
        best, best_c = structure, v.c({**structure, "unit_price": price})
        for field, values in self.refused(case, v).items():
            if len(values) > 1 or field not in structure:
                continue  # asked twice, changed twice: its value stands
            for option in case.get("term_options", {}).get(field) or []:
                candidate = {**best, field: option}
                if option in values or candidate == best or not v.valid({**candidate, "unit_price": price}):
                    continue
                cost = v.c({**candidate, "unit_price": price})
                if cost < best_c * (1 - 0.002):
                    best, best_c = candidate, cost
        return best

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

    def intel(self, case, v):
        """Its dossier (group B), or {} - a missing dossier is no reason to lose a move."""
        key = (case.get("case_id"), v.sid, "intel")
        if key not in self._memo:
            found = {}
            if self.k["dossier"]:
                try:
                    from .intel import dossier

                    # the openings of all threads, as {supplier: [messages]}: one e-mail alone is not a thread
                    # to the overlay, which then saw neither this opening nor the rivals' (until Sat 22:40)
                    openings = self._memo.get((case.get("case_id"), "openings")) or {v.sid: [v.opening] if v.opening else []}
                    with calculator.LOCK:  # one cache for all cases played at once
                        found = dossier(v.sid, case.get("parts") or [], case, openings) or {}
                except Exception as e:
                    log.warning("%s %s: no dossier (%s: %s)", case.get("case_id"), v.sid, type(e).__name__, e)
            self._memo[key] = found
        return self._memo[key]

    def cash(self, case, v):
        """low | medium | high as the dossier reads it from the supplier's data; None for a supplier
        we hold no data on (the dossier then knows the case only)."""
        found = self.intel(case, v)
        if not found or found.get("coverage") != "full":
            return None
        pressure = (found.get("economics") or {}).get("cash_pressure")
        return pressure if pressure in ("low", "medium", "high") else None

    def menu(self, case, v, sheet):
        """A second offer for a supplier whose cash position we do not know: the same package with
        the latest payment days, at the price that costs us the same. It answers the one worth more
        to it (65 of 79 replies), so its choice costs us nothing and shows what it values."""
        options = case.get("term_options", {}).get("payment_days") or []
        if "payment_days" not in sheet or self.cash(case, v) is not None or not options:
            return []
        late = max(options)
        if late <= sheet["payment_days"]:
            return []
        structure = {f: x for f, x in sheet.items() if f != "unit_price"}
        price = calculator.price_for(case, v.std, {**structure, "payment_days": late}, v.c(sheet))
        if price is None or price <= 0:
            return []
        other = complete_offer(case, {**structure, "payment_days": late, "unit_price": round(price, 2)})
        return [other] if v.valid(other) and other != sheet else []

    def rate(self, case, v):
        """Its cost of money: from the dossier where one exists (measured from its cash discount, or
        by owner type), else our guess."""
        rate = (self.intel(case, v).get("economics") or {}).get("cost_of_money")
        if isinstance(rate, int | float) and 0 < rate < 1:
            return float(rate)
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
        if estimate and relationship and v.opening and own:
            # In every real case its opening carried no relationship cost (D01, P01, P02, P03, P10):
            # an estimate that puts the opening below the sustainable margin is too high (P02: by 1.6 %).
            worth = self.value(case, v, v.filled(v.opening["term_sheets"][0]["terms"]))
            estimate = (estimate[0], min(estimate[1], worth * (1 - b["sustainable_margin_pct"] / 100)))
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
            share = self.share(case, v, bool(relationship))
            target = share * min(reference, market)
            charged = calculator.recent_low(calculator.supplier_cost(case, v.sid, None, self.package))
            # a price it charged within twelve months is one it can go back to - unless its list price is fixed
            if charged and self.k["recent_cap"] and share < 0.96:
                target = min(target, charged)
            if v.opening and v1 > v0:  # the same worth to it on the structure we ask
                its = v.filled(v.opening["term_sheets"][0]["terms"])
                target = (self.value(case, v, {**its, "unit_price": target}) - v0) / (v1 - v0)
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
        key = (case.get("case_id"), sid, "should_cost")
        if key not in self._memo:
            cost = calculator.supplier_cost(case, sid, None, self.package)["cost"]
            self._memo[key] = (cost["ref"], float(cost["value"])) if cost else None
        return self._memo[key]

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
            if ref not in cited and not self.hedged(case, v, ref):
                return [sentence]
        return self.banked(case, v, cited, ours_here, price) if self.k["bank"] else []

    def banked(self, case, v, cited, ours_here, price):
        """The next fact of the argument bank (group C, sellm/claims.py): checked against the data,
        its figure next to its ID. Never one cited before, never a rival's quote (it reveals what we
        hold), and one fact per topic - the arena calls a second forecast or complaint `duplicate`."""
        try:
            from . import claims

            def topic(ref):  # a complaint qn: after a scorecard sc: comes back `duplicate`, but the supplier still
                # reads it and keeps conceding: P11 0.778 with it, 0.710 without; P02 0.531 / 0.522 (Sat 22:16)
                head = ref.split(":", 1)[0]
                return {"ctr": "doc"}.get(head, head)

            used = {topic(i) for i in cited}
            with calculator.LOCK:
                found = claims.arguments(
                    case, v.sid, self.intel(case, v), package=self.package, used=cited, price=price
                )
            for a in found:
                if a["kind"] == "quote" or a["sentence"] in ours_here or not a.get("ids"):
                    continue
                if self.k["one_per_topic"] and topic(a["ids"][0]) in used:
                    continue
                if self.k["gate"] and self.dismissed(case, v, a["kind"]):
                    continue
                sentence = a["sentence"]
                if a["kind"] in ("sc_ppm", "qn") or "ppm" in sentence:
                    if self.k["ppm"] == "skip":
                        continue
                    if self.k["ppm"] == "plain":
                        sentence = re.sub(r"(\d),(\d{3})(?=\s*ppm)", r"\1\2", sentence)
                return [sentence]
        except Exception as e:  # an argument less, never a lost move
            log.warning("%s %s: argument bank failed (%s: %s)", case.get("case_id"), v.sid, type(e).__name__, e)
        return []

    def dismissed(self, case, v, kind):
        """A fact this supplier will answer with 'it holds, but it does not change our calculation',
        by its dossier. Over every recorded single-fact e-mail, an on-time-delivery record was taken
        into account by the suppliers with a delivery or quality problem signal (70110, 70140, 70210:
        13 of 13) and dismissed by the others in about 60 of 70 answers (70250, 70610, 70620, 70710,
        70740; 70510 split). Only for a supplier with a full dossier: a stranger's silence is no
        evidence."""
        found = self.intel(case, v)
        if kind != "sc_otd" or found.get("coverage") != "full":
            return False
        kinds = {sig.get("kind") for sig in found.get("signals") or []}
        return not kinds & {"delivery_problem", "quality_problem"}

    def hedged(self, case, v, ref):
        """A material index whose fall does not reach this supplier: its dossier says its material is
        covered at fixed prices ('Material covered until March 2027'). P08's supplier answered the fall of
        AS-14404 with 'that is not our reality' and ended 0.10 higher (0.438 against 0.549). Labour and
        energy series are not material. Only with `idx_recent`, so the agent without it is unchanged."""
        if not self.k["idx_recent"] or ref.split(":", 1)[-1].startswith(("LCI-", "PPI-D35")):
            return False
        return any(sig.get("kind") == "material_hedged" for sig in self.intel(case, v).get("signals") or [])

    def index_claims(self, case):
        """Cost-driver indices of the case's parts that fell over the last twelve months of their series."""
        key = (case.get("case_id"), "idx")
        if key in self._memo:
            return self._memo[key]
        out, recent = [], []
        parts = case.get("parts") or []
        if self.package and parts:
            try:
                with calculator.LOCK:
                    marks = ",".join("?" * len(parts))
                    rows = self.package.query(
                        f"select distinct series_id from cost_drivers where part_id in ({marks})", tuple(parts)
                    )
                    weights = self.package.query(
                        f"select series_id, max(weight) as weight from cost_drivers where part_id in ({marks}) group by series_id",
                        tuple(parts),
                    )
                    weight = {w["series_id"]: w["weight"] or 0.0 for w in weights}
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
                        elif self.k["idx_recent"]:
                            # rose over the year but fell since its peak: a window of at most 12 months that ends
                            # with the data is checked like the yearly one (docs/CONTEXT.md section 7)
                            peak = max(ids[-13:-1], key=lambda i: self.package.lookup(i)["value"])
                            change = (self.package.lookup(b)["value"] / self.package.lookup(peak)["value"] - 1) * 100
                            if change <= -self.k["idx_recent"]:
                                months = (peak.split("@", 1)[1], b.split("@", 1)[1])
                                recent.append(
                                    (
                                        change * weight.get(r["series_id"], 0.0),
                                        b,
                                        f"The index {r['series_id']} changed {change:+.1f} % from {months[0]} to {months[1]} ({peak}, {b}).",
                                    )
                                )
                    out += [(b, sentence) for _, b, sentence in sorted(recent)[:1]]  # the largest fall in our cost; one, a second may count as duplicate
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
