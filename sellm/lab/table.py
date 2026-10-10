"""The arena in-process: a `LocalTable` has the methods of the kit's `RemoteTable`, so the kit's
`play()` and every agent run against the lab's suppliers unchanged - no HTTP, no clock, no quota.

Rules kept from the arena (docs/CONTEXT.md, experiments/RESULTS.md): a term sheet carries exactly
the negotiable fields with values from `term_options` (else 422, nothing happens); the round limit
per thread (409); only the first term sheet of a supplier's e-mail can be accepted (422 otherwise);
unstated terms close on the supplier's standard terms; the score is the share of the possible
saving, 0 for a broken must-have or a deal worse than the opening, the alternative without a deal.
"""

import copy
import random
from dataclasses import dataclass, field

from arena_kit.client import ArenaError
from arena_kit.cost import closing_terms, cost_breakdown, must_haves_ok, score, total_cost

from .bot import SupplierThread
from .claims import ClaimChecker


@dataclass
class Scenario:
    """One case and the suppliers in it, with the yardsticks the score needs."""

    case: dict
    personas: dict  # supplier_id -> Persona
    c_open: float
    c_best: float
    kind: str = "twin"  # twin (of a supplier we played) or invented
    name: str = ""
    notes: str = ""
    drivers: list = field(default_factory=list)  # index series that bear on the case's parts

    @property
    def c_alt(self):
        alt = self.case["buyer"].get("alternative") or {}
        return total_cost(self.case, alt["terms"]) if alt.get("terms", {}).get("unit_price") else None


class Session:
    def __init__(self, scenario, facts):
        self.checker = ClaimChecker(facts, scenario.case, scenario.drivers)
        self.offers, self.used = {}, set()


class LocalTable:
    def __init__(self, scenario, facts=None, seed=0):
        self.scenario, self.case = scenario, copy.deepcopy(scenario.case)
        self.facts, self.rng = facts or {}, random.Random(seed)
        self.session_id, self.done, self.threads, self.outcome = f"lab-{seed}", None, {}, None
        self.files = {}

    # -- the RemoteTable interface -------------------------------------------------------------
    def open(self, case_id=None):
        self.session = Session(self.scenario, self.facts)
        for sid, persona in self.scenario.personas.items():
            rng = random.Random(self.rng.random())
            self.threads[sid] = SupplierThread(persona, self.case, rng, self.session)
            self.threads[sid].opening()
        return copy.deepcopy(self.case), {sid: [self._public(m) for m in t.messages] for sid, t in self.threads.items()}

    def send(self, supplier_id, message):
        t = self._thread(supplier_id)
        if message.get("action"):
            return self.close(supplier_id, message)
        sheets = message.get("term_sheets") or []
        if len(sheets) > 3 or len(message.get("body") or "") > 8000 or len(message.get("refs") or []) > 20:
            raise ArenaError(422, "at most 3 term sheets, 8,000 characters and 20 refs")
        for ts in sheets:
            self._check(ts.get("terms", {}))
        if t.round >= self.case.get("round_limit", 10):
            raise ArenaError(409, "round limit reached: accept the standing offer or walk away")
        reply = self._public(t.respond(message))
        if t.closed and all(x.closed for x in self.threads.values()):
            self._end(None, "no_deal")
            return {**reply, "result": self.outcome}
        return reply

    def close(self, supplier_id, message):
        action = message.get("action") or {}
        if action.get("type") == "walk_away":
            self._end(None, "walked_away")
            return self.outcome
        if action.get("type") != "accept":
            raise ArenaError(422, "action is {'type': 'accept', 'term_sheet_id': ...} or 'walk_away'")
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
            raise ArenaError(422, "not a standing offer in this session")
        self._end(owner, "accepted")
        return self.outcome

    def attachment(self, attachment_id):
        for t in self.threads.values():
            for m in t.messages:
                for a in m["attachments"]:
                    if a["attachment_id"] == attachment_id:
                        return a["text"].encode()
        raise ArenaError(404, "no such attachment in this session")

    def missed(self, supplier_id, error):
        if self.outcome is not None:
            return {"result": self.outcome}
        t = self.threads[supplier_id]
        last = self._public(t.messages[-1])
        return {**last, "body": f"({error.detail})", "status": "walked_away" if t.closed else t.status}

    def result(self):
        if self.outcome is None:
            self._end(None, "no_deal")
        return self.outcome

    # -- helpers -------------------------------------------------------------------------------
    def _thread(self, supplier_id):
        if self.outcome is not None:
            raise ArenaError(409, f"the session has ended: {self.outcome['end_reason']}")
        t = self.threads.get(supplier_id)
        if t is None:
            raise ArenaError(422, f"{supplier_id} is not a supplier in this case")
        if t.closed:
            raise ArenaError(409, f"the thread with {supplier_id} has ended: {t.closed}")
        return t

    def _check(self, terms):
        case = self.case
        if set(terms) != set(case["negotiable"]) or not (terms.get("unit_price") or 0) > 0:
            raise ArenaError(422, f"a term sheet carries exactly the negotiable fields {case['negotiable']}")
        for f, v in terms.items():
            options = case["term_options"].get(f)
            if f != "unit_price" and options and v not in options:
                raise ArenaError(422, f"{f}={v!r} is not one of {options}")

    @staticmethod
    def _public(msg):
        return copy.deepcopy(msg)

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
        }
        if owner:
            t, p = self.threads[owner], sc.personas[owner]
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
