# ruff: noqa: E501  (long sentences and messages)
"""sellm2's buyer agent: `make_agent(package)` -> an object with `decide(case, threads, focus=None)`.

The kit's interface (arena_kit.play), the runner's (sellm2.runner) and the lab's (sellm.lab) all call
`decide`. Every move is a pure function of the case and the threads, so `fallback` is the agent
itself and a fresh agent resumes a session after a crash. Our own bug never reaches the runner: it
becomes a holding e-mail, or the kit's closing move when no message is left, and is logged."""

import logging
import os

from .policy import Policy

log = logging.getLogger("sellm2")


class Buyer:
    def __init__(self, package=None, **knobs):
        self.policy = Policy(package, **knobs)
        self.package = package
        self.fallback = self
        self.stats = {"moves": 0, "errors": 0}
        self.name = "sellm2" + "".join(f" {k}={v}" for k, v in knobs.items())
        self.last_reasons = []

    def decide(self, case, threads, focus=None):
        try:
            draft = self.policy.move(case, threads, focus)
            decision = self.policy.message(case, threads, draft)
            self.stats["moves"] += 1
            self.last_reasons = draft.get("reasons") or []
            sheets = [s["terms"].get("unit_price") for s in decision["message"].get("term_sheets") or []]
            log.info("%s %s: %s %s - %s", case.get("case_id"), draft["sid"], draft["kind"], sheets, "; ".join(self.last_reasons))
            return decision
        except Exception:
            if os.environ.get("SELLM_STRICT") == "1":
                raise
            self.stats["errors"] += 1
            log.exception("%s: sellm2 failed, sending a safe move", case.get("case_id"))
            return self.policy.rescue(case, threads, focus)


def make_agent(package=None, writer=None, **knobs):
    """A fresh agent for one case (`writer` is accepted for the kit's and the lab's call signature)."""
    return Buyer(package, **knobs)
