"""The arena in-process: a `LocalTable` has the methods of the kit's `RemoteTable`, so the kit's
`play()` and every agent run against the lab's suppliers unchanged - no HTTP, no quota.

Rules kept from the arena (docs/CONTEXT.md, brief/api.md, experiments/RESULTS.md): a term sheet
carries exactly the negotiable fields, each (except the price) a value from `term_options` or the
supplier's standard value (else 422, nothing happens); the round limit per thread (409); only the
first term sheet of a supplier's e-mail can be accepted (422 otherwise); unstated terms close on the
supplier's standard terms; the score is the share of the possible saving, 0 for a broken must-have
or a deal worse than the opening, the alternative's score without a deal.

With `clock=True` time is simulated: a supplier answers after `reply_s` seconds (20-60 s in the
arena); a thread left more than 60 s after the supplier's last e-mail gets a timeout when the
session is next touched (our message is refused with a 409, the offer is re-issued under a new ID,
patience drops, a final offer may be withdrawn, three in a row end the thread); at `wave_cap_s`
every open session ends without a deal, as in the Live Final. `play_lab` plays a case either the way
the kit's `play()` does (one thread at a time, waiting for each reply) or with one loop per thread.
"""

import copy
import inspect
import random
import time
from dataclasses import dataclass, field

from arena_kit.client import ArenaError
from arena_kit.cost import closing_terms, cost_breakdown, must_haves_ok, score, total_cost
from arena_kit.play import closing_move, live_threads

from .bot import SupplierThread
from .claims import ClaimChecker

MOVE_S = 60  # the arena's 60 seconds per message, per thread
LATE = "late: more than 60 s after the supplier's last move, so it counted as a timeout"


@dataclass
class Scenario:
    """One case and the suppliers in it, with the yardsticks the score needs."""

    case: dict
    personas: dict  # supplier_id -> Persona
    c_open: float
    c_best: float
    kind: str = "twin"  # twin (a supplier we played), data (a case file, suppliers from the data), invented
    name: str = ""
    notes: str = ""
    drivers: list = field(default_factory=list)  # index series that bear on the case's parts
    tags: list = field(default_factory=list)  # what is special about it (edge cases, archetypes)

    @property
    def c_alt(self):
        alt = self.case["buyer"].get("alternative") or {}
        return total_cost(self.case, alt["terms"]) if alt.get("terms", {}).get("unit_price") else None


class Session:
    def __init__(self, scenario, facts, reader=None):
        self.checker = ClaimChecker(facts, scenario.case, scenario.drivers)
        self.offers, self.used, self.reader = {}, set(), reader


class LocalTable:
    def __init__(
        self,
        scenario,
        facts=None,
        seed=0,
        clock=False,
        reply_s=(20.0, 60.0),
        think_s=None,
        wave_cap_s=None,
        vary=False,
        reader=None,
    ):
        """`clock`: simulate time (see the module doc). `think_s`: our decision time per move in
        simulated seconds (None: the real time the agent took, plus 0.5 s for the network).
        `vary`: play a random member of each twin's family instead of the fitted twin."""
        self.scenario, self.case = scenario, copy.deepcopy(scenario.case)
        self.facts, self.rng, self.reader = facts or {}, random.Random(seed), reader
        self.clock, self.reply_s, self.think_s, self.wave_cap_s = clock, reply_s, think_s, wave_cap_s
        self.vary = vary
        self.session_id, self.done, self.threads, self.outcome = f"lab-{seed}", None, {}, None
        self.now, self.parallel, self._back, self._late = 0.0, False, None, []
        self.personas = {}
        self.stats = {"timeouts": 0, "late": 0, "rejected": 0}

    # -- the RemoteTable interface -------------------------------------------------------------
    def open(self, case_id=None):
        self.session = Session(self.scenario, self.facts, self.reader)
        for sid, persona in self.scenario.personas.items():
            rng = random.Random(self.rng.random())
            p = persona.vary(rng) if self.vary else persona
            self.personas[sid] = p
            t = self.threads[sid] = SupplierThread(p, self.case, rng, self.session)
            t.last_at = 0.0
            t.opening()
            t.messages[-1]["_at"] = 0.0
        self._returned()
        threads = {sid: [self._public(m) for m in t.messages] for sid, t in self.threads.items()}
        return copy.deepcopy(self.case), threads

    def send(self, supplier_id, message):
        if message.get("action"):
            return self.close(supplier_id, message)
        self._arrive()
        t = self._thread(supplier_id)
        sheets = message.get("term_sheets") or []
        if len(sheets) > 3 or len(message.get("body") or "") > 8000 or len(message.get("refs") or []) > 20:
            self._reject("at most 3 term sheets, 8,000 characters and 20 refs")
        for ts in sheets:
            self._check(supplier_id, ts.get("terms", {}))
        if t.round >= self.case.get("round_limit", 10):
            raise ArenaError(409, "round limit reached: accept the standing offer or walk away")
        t.history.append({**copy.deepcopy(message), "from": "buyer", "_at": self.now})
        reply = t.respond(message)
        self._delivered(t, reply)
        self._returned()
        if t.closed and all(x.closed for x in self.threads.values()):
            self._end(None, "no_deal")
            return {**self._public(reply), "result": self._result()}
        return self._public(reply)

    def close(self, supplier_id, message):
        self._arrive()
        action = message.get("action") or {}
        if self.outcome is not None:
            raise ArenaError(409, f"the session has ended: {self.outcome['end_reason']}")
        if action.get("type") == "walk_away":
            self._end(None, "walked_away")
            return self._result()
        if action.get("type") != "accept":
            self._reject("action is {'type': 'accept', 'term_sheet_id': ...} or 'walk_away'")
        sheet = action.get("term_sheet_id")
        owner = next(
            (
                s
                for s, t in self.threads.items()
                if not t.closed and t.standing and t.standing["term_sheet_id"] == sheet
            ),
            None,
        )
        if owner is None:
            self._reject("not a standing offer in this session")
        self.threads[owner].history.append({**copy.deepcopy(message), "from": "buyer", "_at": self.now})
        self._end(owner, "accepted")
        return self._result()

    def attachment(self, attachment_id):
        for t in self.threads.values():
            for m in t.messages:
                for a in m["attachments"]:
                    if a["attachment_id"] == attachment_id:
                        return a["text"].encode()
        raise ArenaError(404, "no such attachment in this session")

    def missed(self, supplier_id, error):
        if self.outcome is not None:
            return {"result": self._result()}
        t = self.threads[supplier_id]
        last = self._public(t.messages[-1])
        return {**last, "body": f"({error.detail})", "status": "walked_away" if t.closed else t.status}

    def result(self):
        if self.outcome is None:
            self._end(None, "no_deal")
        return self._result()

    # -- time ----------------------------------------------------------------------------------
    def _arrive(self):
        """A call from the agent: its thinking time passes, then timeouts and the cap apply."""
        if self.clock and not self.parallel:
            if self.think_s is not None:
                took = self.think_s
            else:
                took = time.monotonic() - (self._back or time.monotonic()) + 0.5
            self.now += took
        self._touch()

    def _returned(self):
        self._back = time.monotonic()

    def _touch(self):
        self._late = []
        if not self.clock or self.outcome is not None:
            return
        if self.wave_cap_s is not None and self.now >= self.wave_cap_s:
            self._end(None, "wave_cap")
            raise ArenaError(409, "the session has ended: wave_cap")
        for sid, t in self.threads.items():
            if not t.closed and self.now - t.last_at > MOVE_S:
                follow = t.timeout(last_round=t.round >= self.case.get("round_limit", 10))
                self.stats["timeouts"] += 1
                self._delivered(t, follow, delay=0.0)
                self._late.append(sid)
        if self._late and all(x.closed for x in self.threads.values()):
            self._end(None, "timeout")

    def _delivered(self, t, reply, delay=None):
        """When the supplier's e-mail arrives; in the sequential mode we wait for it."""
        if not self.clock:
            reply["_at"] = self.now
            return
        d = self.rng.uniform(*self.reply_s) if delay is None else delay
        at = self.now + d
        if not self.parallel:
            self.now = at
        reply["_at"] = t.last_at = at

    # -- helpers -------------------------------------------------------------------------------
    def _thread(self, supplier_id):
        if self.outcome is not None:
            raise ArenaError(409, f"the session has ended: {self.outcome['end_reason']}")
        t = self.threads.get(supplier_id)
        if t is None:
            self._reject(f"{supplier_id} is not a supplier in this case")
        if supplier_id in self._late and not t.closed:
            self.stats["late"] += 1
            raise ArenaError(409, f"{LATE}; GET the thread for the supplier's answer")
        if t.closed:
            raise ArenaError(409, f"the thread with {supplier_id} has ended: {t.closed}")
        return t

    def _reject(self, detail):
        self.stats["rejected"] += 1
        raise ArenaError(422, detail)

    def _check(self, supplier_id, terms):
        case = self.case
        if set(terms) != set(case["negotiable"]) or not (terms.get("unit_price") or 0) > 0:
            self._reject(f"a term sheet carries exactly the negotiable fields {case['negotiable']}")
        standard = self.personas[supplier_id].standard
        for f, v in terms.items():
            options = case["term_options"].get(f)
            if f != "unit_price" and options and v not in options and v != standard.get(f):
                self._reject(f"{f}={v!r} is not one of {options}")

    @staticmethod
    def _public(msg):
        return copy.deepcopy(msg)

    def _result(self):
        return {k: v for k, v in self.outcome.items() if k != "trace"}

    def _end(self, owner, reason):
        sc, case = self.scenario, self.case
        c_alt = sc.c_alt
        r = {
            "ended": True,
            "end_reason": reason,
            "deal": False,
            "supplier_id": None,
            "offer_id": None,
            "terms": None,
            "c_open": sc.c_open,
            "c_deal": None,
            "c_alt": c_alt,
            "c_best": sc.c_best,
            "score": score(sc.c_open, c_alt, sc.c_best) if c_alt else 0.0,
            "must_haves_ok": None,
            "cost_breakdown": None,
            "rounds": sum(t.round for t in self.threads.values()),
            "seconds": round(self.now, 1),
            **self.stats,
        }
        if owner:
            t, p = self.threads[owner], self.personas[owner]
            terms = closing_terms(case, t.standing["terms"], p.pdf_standard)
            breakdown = cost_breakdown(case, terms, p.pdf_standard, p.relationship_view())
            c_deal = round(sum(breakdown.values()), 2)
            ok = must_haves_ok(case, terms)
            r.update(
                deal=True,
                supplier_id=owner,
                offer_id=t.standing["term_sheet_id"],
                terms=terms,
                c_deal=c_deal,
                must_haves_ok=ok,
                cost_breakdown=breakdown,
                score=score(sc.c_open, c_deal, sc.c_best) if ok else 0.0,
            )
        r["trace"] = {sid: t.reasons for sid, t in self.threads.items()}
        for t in self.threads.values():
            t.closed = t.closed or reason
        self.outcome = r


def _decide(agent, case, threads, focus):
    """Ask the agent; agents that take `focus` decide for that thread (one loop per thread)."""
    if focus is not None and "focus" in inspect.signature(agent.decide).parameters:
        return agent.decide(case, threads, focus=focus)
    return agent.decide(case, threads)


def play_lab(table, agent, mode="sequential", close_before_s=90, round_margin_s=15, strict=False):
    """Play one case to its end on a LocalTable. `sequential`: as the kit's `play()` (one thread at
    a time, each reply awaited, so the other threads' clocks run). `parallel`: one loop per thread,
    each answered as soon as its own reply is in. With a wave cap the case is closed by the kit's
    `closing_move` shortly before it, as the kit's runner does.

    A 422 (an invalid sheet, or accepting an offer ID a timeout has replaced) crashes the kit's
    `play()`. Here it is counted in the result's `rejected` and the agent decides again on the
    re-read threads; `strict=True` raises instead, as the kit would."""
    case, threads = table.open()
    table.parallel = mode == "parallel" and table.clock
    slowest, refused = 0.0, 0
    while table.outcome is None and live_threads(threads):
        live = live_threads(threads)
        if table.parallel:
            ready = {
                s: max((m.get("_at", 0.0) for m in threads[s] if m.get("from") != "buyer"), default=0.0) for s in live
            }
            focus = min(ready, key=ready.get)
            table.now = max(table.now, ready[focus])
            view = {
                s: [m for m in ev if m.get("from") == "buyer" or m.get("_at", 0.0) <= table.now]
                for s, ev in threads.items()
            }
        else:
            focus, view = None, threads
        t0 = time.monotonic()
        cap = table.wave_cap_s
        if cap is not None and table.clock and table.now > cap - max(close_before_s, slowest + round_margin_s):
            decision = closing_move(case, view)
        else:
            decision = _decide(agent, case, view, focus)
        if table.parallel:
            table.now += table.think_s if table.think_s is not None else time.monotonic() - t0 + 0.5
        start = table.now
        sid, msg = decision["supplier_id"], decision["message"]
        if table.parallel and sid in table.threads:
            pending = max((m.get("_at", 0.0) for m in table.threads[sid].messages), default=0.0)
            if pending > table.now:  # its answer to our last e-mail is still on the way: wait for it
                table.now = pending
                _sync(table, threads)
                continue
        try:
            if msg.get("action"):
                return table.close(sid, msg)
            reply = table.send(sid, msg)
        except ArenaError as e:
            if e.status not in (409, 422) or (e.status == 422 and (strict or refused >= 3)):
                raise
            refused = refused + 1 if e.status == 422 else 0
            if table.outcome is not None:
                return table._result()
            _sync(table, threads)
            continue
        refused = 0
        if "result" in reply:
            return reply["result"]
        threads[sid] += [{**msg, "from": "buyer", "_at": start}, reply]
        _sync(table, threads)
        slowest = max(slowest, reply.get("_at", table.now) - start)
    return table.result() if table.outcome is None else table._result()


def _sync(table, threads):
    """Add the supplier e-mails the table produced meanwhile (timeout follow-ups) to our view."""
    for s, t in table.threads.items():
        known = {m.get("message_id") for m in threads[s] if m.get("message_id")}
        threads[s] += [table._public(m) for m in t.messages if m["message_id"] not in known]
