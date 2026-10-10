# ruff: noqa: E501  (prompt text and messages)
"""The LLM around the code's moves (`SELLM_LLM=shadow|apply`, off by default).

Code still fixes every number: the term sheets, the target, the checked facts, accept and walk
away. The model does two things.

1. It writes the e-mail around the move (the guarded writer of experiments/llm_writer.py: required
   sentences word for word, no new figure, no leak; else the template's e-mail goes out).
2. It gives a verdict on the supplier's standing offer: A = take it now, B = keep negotiating. It
   may first call our functions (the calculator's cost of any price, the dossier's reading of the
   supplier, the facts we have left). The confidence is not asked for: it is the probability the
   model puts on the letter it answers with, read from the token probabilities.

`shadow`: the verdict is logged next to what code decided, nothing else changes.
`apply`:  in a single-supplier case, before the supplier's final offer, an A with a probability of
          `take_at` (0.85) or more makes us accept at once - if the offer keeps the must-haves, is
          not dearer than the alternative and is better than its opening. Nothing else is acted
          on: after a final offer code accepts whatever the model says (asking once more lost two
          of three deals, experiments/PERSISTENCE.md T1).

One JSON line per verdict goes to `SELLM_TRACE` (default runs/logs/advisor-trace.jsonl).
"""

import importlib.util
import json
import math
import os
import time
from pathlib import Path

from arena_kit.cost import total_cost

from . import calculator, llm
from .endgame import Persistent
from .negotiator import Thread, log

ROOT = Path(__file__).resolve().parents[1]
TRACE = ROOT / "runs" / "logs" / "advisor-trace.jsonl"

SYSTEM = """You are the second opinion in a buyer's price negotiation by e-mail. The buyer is Hollerau Pumpenwerke; the other side is a supplier. Code has computed every number. You judge one thing: should the buyer ACCEPT the supplier's standing offer now (A), or KEEP NEGOTIATING (B)?

What earlier negotiations with such suppliers showed:
- A supplier that has said "final offer" does not improve it. Asked once more, two of three withdrew and the deal was lost. A lost deal costs far more than a slightly better price can gain.
- Before a final offer suppliers did not withdraw. They concede in small steps for three to six of our messages, then say "final offer".
- A supplier gives nothing without a move from us. A checked fact moves some suppliers by one or two percent, others not at all.
- Lower total cost is better for the buyer. In some cases squeezing the supplier below a sustainable margin costs the buyer too; the cost function you can call includes that.

You may call the functions to check a price, the supplier's profile or the facts we have left. Then answer with exactly one letter first, A or B, then " - " and one short sentence with your reason."""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "cost_of_price",
            "description": "Our total cost in EUR if the deal closed at this unit price on the terms of the supplier's standing offer, and how that compares.",
            "parameters": {
                "type": "object",
                "properties": {"unit_price": {"type": "number"}},
                "required": ["unit_price"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "supplier_profile",
            "description": "What our data says about this supplier: signals such as short of cash, wants volume, fixed list price, approval ladder; its cost of money; a short profile.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "facts_left",
            "description": "The checked facts we could still cite to this supplier (kind and sentence), none of them used so far.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]


def _writer_base():
    """The guarded LLM writer (group B's experiment), loaded by path: `experiments` is no package for the arena CLI."""
    try:
        spec = importlib.util.spec_from_file_location("sellm_llm_writer", ROOT / "experiments" / "llm_writer.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.LLMWriterNegotiator
    except Exception as e:  # no writer is no reason to lose a move: the template writes
        log.warning("LLM writer not available (%s: %s), e-mails come from the template", type(e).__name__, e)
        return object


class _Writer(_writer_base()):
    pass


def probability(text, first):
    """(letter, probability) of the verdict: the share of A or B among the model's first-token probabilities."""
    letter = (text or "").strip()[:1].upper()
    if letter not in ("A", "B"):
        return None, None
    mass = {"A": 0.0, "B": 0.0}
    for t in first or []:
        token = (t.get("token") or "").strip()[:1].upper()
        if token in mass:
            mass[token] += math.exp(t.get("logprob", -99.0))
    total = mass["A"] + mass["B"]
    return letter, (mass[letter] / total if total > 0 else None)


class Advised(_Writer, Persistent):
    def __init__(self, package=None, writer=None, verdict="shadow", take_at=0.85, **knobs):
        super().__init__(package, writer=writer, **knobs)
        self.verdict_mode, self.take_at = verdict, take_at
        self.name = f"advised({verdict}) " + self.name

    def decide(self, case, threads, focus=None):
        try:
            draft = self.move(case, threads, focus)
            draft = self.advised(case, threads, draft)
            decision = self.message(case, threads, draft)
            self.stats["moves"] += 1
            return decision
        except Exception:
            if os.environ.get("SELLM_STRICT") == "1":
                raise
            self.stats["errors"] += 1
            log.exception("%s: the advised negotiator failed, sending a safe move", case.get("case_id"))
            return self.rescue(case, threads, focus)

    # -- the verdict -----------------------------------------------------------------------------
    def advised(self, case, threads, draft):
        sid = draft.get("sid")
        if draft.get("kind") == "walk_away" or sid not in threads:
            return draft
        v = Thread(case, sid, threads[sid])
        standing = v.filled(v.standing[1]) if v.standing[0] else {}
        if standing.get("unit_price") is None or not v.valid(standing):
            return draft
        record = {"case": case.get("case_id"), "sid": sid, "n": len(v.ours), "status": v.status, "their_price": standing["unit_price"],
                  "code": draft["kind"], "mode": self.verdict_mode, "applied": False}  # fmt: skip
        try:
            text, calls, first, took = llm.chat_tools(
                SYSTEM, self.briefing(case, v, standing), TOOLS, self.handlers(case, v, standing), timeout_s=12.0
            )
            letter, p = probability(text, first)
            record.update(
                verdict=letter,
                p=None if p is None else round(p, 4),
                reason=text.strip()[:300],
                tools=calls,
                s=round(took, 2),
            )
        except llm.LLMError as e:
            record.update(verdict=None, error=str(e)[:200])
            letter, p = None, None
        take = (
            self.verdict_mode == "apply"
            and letter == "A"
            and p is not None
            and p >= self.take_at
            and draft["kind"] in ("ask", "take_alternative", "hold")
            and v.status == "open"
            and len(threads) == 1
            and self.takable(case, v, standing)
        )
        if take:
            record["applied"] = True
            draft = {"kind": "accept", "sid": sid, "accept_id": v.standing[0]}
        self.trace(record)
        return draft

    def takable(self, case, v, standing):
        """Better than its opening and not dearer than our alternative: an accept the arena scores above zero."""
        cost = v.c(standing)
        opening = v.filled(v.opening["term_sheets"][0]["terms"]) if v.opening else {}
        if opening.get("unit_price") is not None and v.valid(opening) and cost >= v.c(opening):
            return False
        alt = (case["buyer"].get("alternative") or {}).get("terms") or {}
        return not (alt.get("unit_price") and total_cost(case, alt) < cost)

    def briefing(self, case, v, standing):
        b = case["buyer"]
        asks = [m["term_sheets"][0]["terms"].get("unit_price") for m in v.ours if m.get("term_sheets")]
        offers = [m["term_sheets"][0]["terms"].get("unit_price") for m in v.theirs if m.get("term_sheets")]
        opening = v.filled(v.opening["term_sheets"][0]["terms"]) if v.opening else {}
        c_now = v.c(standing)
        c_open = v.c(opening) if opening.get("unit_price") is not None else None
        alt = (b.get("alternative") or {}).get("terms") or {}
        lines = [
            f"Case: {case.get('title', '')} ({case.get('type')}, category goal {b.get('category_goal')}).",
            f"We have sent {len(v.ours)} of at most {case.get('round_limit', 10)} messages in this thread.",
            f"Its unit prices so far: {offers}. Our asks so far: {asks}.",
            f"Its standing offer: {standing} - status '{v.status}'.",
            f"Our total cost at its standing offer: EUR {c_now:,.0f}"
            + (
                f"; at its opening: EUR {c_open:,.0f} (saved so far {100 * (1 - c_now / c_open):.1f} %)."
                if c_open
                else "."
            ),
            (
                f"Our alternative without this supplier costs EUR {total_cost(case, alt):,.0f}."
                if alt.get("unit_price")
                else "We have no alternative: no deal scores nothing."
            ),
            "",
            "The supplier's last e-mail:",
            "---",
            (v.last.get("body") or "")[:1800],
            "---",
        ]
        return "\n".join(lines)

    def handlers(self, case, v, standing):
        structure = {f: x for f, x in standing.items() if f != "unit_price"}
        c_now = v.c(standing)

        def cost_of_price(unit_price):
            c = v.c({**structure, "unit_price": float(unit_price)}, self.estimate(case, v))
            return {"unit_price": unit_price, "total_cost_eur": round(c), "against_standing_offer_eur": round(c - v.c(standing, self.estimate(case, v))),
                    "note": "includes our estimate of the relationship cost where the case has one"}  # fmt: skip

        def supplier_profile():
            found = self.intel(case, v)
            eco = found.get("economics") or {}
            return {"signals": [{"kind": s.get("kind"), "strength": s.get("strength"), "excerpt": (s.get("excerpt") or "")[:160]} for s in (found.get("signals") or [])[:8]],
                    "cash_pressure": eco.get("cash_pressure"), "cost_of_money": eco.get("cost_of_money"), "archetype": eco.get("archetype"),
                    "profile": (found.get("profile_text") or "")[:700], "data_coverage": found.get("coverage")}  # fmt: skip

        def facts_left():
            try:
                from . import claims

                cited = {
                    i
                    for m in v.ours
                    for i in __import__("re").findall(r"[a-z]+:[A-Za-z0-9@#._-]+", m.get("body") or "")
                }
                with calculator.LOCK:
                    found = claims.arguments(
                        case, v.sid, self.intel(case, v), package=self.package, used=cited, price=standing["unit_price"]
                    )
                return {
                    "facts": [
                        {"kind": a["kind"], "sentence": a["sentence"][:200]} for a in found if a["kind"] != "quote"
                    ][:6]
                }
            except Exception as e:
                return {"facts": [], "error": f"{type(e).__name__}: {e}"}

        _ = c_now
        return {"cost_of_price": cost_of_price, "supplier_profile": supplier_profile, "facts_left": facts_left}

    def trace(self, record):
        path = Path(os.environ.get("SELLM_TRACE") or TRACE)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps({**record, "t": round(time.time(), 1), "pid": os.getpid()}, default=str) + "\n")
        except OSError:
            pass
        log.info(
            "%s %s: verdict %s p=%s (code: %s)%s",
            record.get("case"),
            record.get("sid"),
            record.get("verdict"),
            record.get("p"),
            record.get("code"),
            " APPLIED" if record.get("applied") else "",
        )
