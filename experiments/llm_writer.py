# ruff: noqa: E501  (prompt text)
"""Experiment (Sat 23:10, Omar): the negotiator's numbers, the LLM's words.

`make_agent` here plays exactly the moves of `sellm.agent.make_agent` - the same term sheets, the
same checked argument, the same accept and walk-away - and only lets the model (`sellm/llm.py`,
`LLM_MODEL`) rewrite the e-mail around them. Code guards what binds and what the arena checks:

- every argument sentence and the offer phrase come back word for word (figure and ID together),
- no figure appears that is not in our draft or in the supplier's last e-mail,
- no leak (urgency, budget, missing alternative) and no ultimatum or hostile word (`sellm.lab.reader`),
- the e-mail stays under 8,000 characters.

If a guard fails, the call fails or takes longer than `LLM_WRITER_TIMEOUT_S` (default 20 s), the
template's e-mail goes out and the reason is logged. Holding e-mails stay the template's. One JSON
line per e-mail goes to `LLM_WRITER_LOG` (if set): outcome, reason, seconds.

Lab: uv run python -m sellm.lab compare sellm.agent:make_agent experiments.llm_writer:make_agent \
         --supplier llm --fixed-twins --invented 0 --test 0 --seeds 1 --think -1
Results: experiments/LLM-WRITER.md. Not used by `--agent sellm`.
"""

import json
import os
import re
import time

from sellm import llm
from sellm.agent import KNOBS
from sellm.negotiator import Negotiator
from sellm.writer import SIGN, contact, render_sheets

NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")
SYSTEM = f"""You write one e-mail for the buyer, Hollerau Pumpenwerke GmbH (a family-owned pump maker), in a negotiation with a supplier by e-mail.
You get the supplier's last e-mail, our draft with the correct facts, and sentences that must appear word for word.
Rules:
- Plain text in English, 80 to 170 words, from the greeting to the signature.
- Answer the supplier's last e-mail: acknowledge what it offered or said, and if it asked for figures, point to the figure we give. Warm and respectful, firm on substance.
- Every required sentence appears exactly as given, character for character, once. You may write sentences before and after it.
- No figures, prices, percentages, dates or IDs other than those in our draft or in the supplier's e-mail. Do not promise anything that is not in our offer.
- Never mention urgency, deadlines, our budget, a lack of alternatives, and never threaten to leave or call anything unacceptable.
- End with exactly this signature:
{SIGN}
Answer with JSON only: {{"body": "<the whole e-mail>"}}"""


def _norm(text):
    return re.sub(r"\s+", " ", text or "").strip()


def _log(record):
    path = os.environ.get("LLM_WRITER_LOG")
    if not path:
        return
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps({**record, "pid": os.getpid(), "t": round(time.time(), 1)}) + "\n")
    except OSError:
        pass


def guard(body, required, allowed_text):
    """None if the LLM's e-mail may go out, else the reason it may not."""
    if not isinstance(body, str) or not body.strip():
        return "empty"
    if len(body) > 8000:
        return "too long"
    flat = _norm(body)
    for sentence in required:
        if _norm(sentence) not in flat:
            return "changed a required sentence"
    allowed = {n.rstrip(",") for n in NUMBER.findall(allowed_text)}
    extra = [n.rstrip(",") for n in NUMBER.findall(body) if n.rstrip(",") not in allowed]
    if extra:
        return f"new figures {extra[:3]}"
    from sellm.lab.reader import read

    seen = read(body)
    for flag in ("ultimatum", "hostile", "urgency", "budget", "no_alternative"):
        if seen.get(flag):
            return flag
    return None


class LLMWriterNegotiator(Negotiator):
    def message(self, case, threads, draft):
        decision = super().message(case, threads, draft)
        msg = decision.get("message") or {}
        sheets = [s["terms"] for s in msg.get("term_sheets") or []]
        if draft.get("kind") not in ("ask", "take_alternative") or not sheets or not msg.get("body"):
            return decision  # accept, walk away, hold: as the negotiator sends them
        sid = decision["supplier_id"]
        events = threads.get(sid) or []
        last = next((m for m in reversed(events) if m.get("from") != "buyer" and m.get("body")), {})
        name = contact(events)
        required = [a for a in draft.get("arguments") or [] if a] + [render_sheets(case, sheets)]
        user = (
            f"Case: {case.get('title', '')}\n\n"
            f"The supplier's last e-mail (from {last.get('from_name') or last.get('from') or 'the supplier'}):\n---\n{(last.get('body') or '')[:2500]}\n---\n\n"
            f"Our draft (correct facts, plain wording):\n---\n{msg['body']}\n---\n\n"
            "Required sentences, each word for word:\n" + "\n".join(f"{i + 1}. {s}" for i, s in enumerate(required)) + "\n"
            f"(The last one is our offer: write it inside a sentence of your own, the terms exactly as given.)\n"
            f"Greeting: {'Dear ' + name + ',' if name else 'Dear Sir or Madam,'}"
        )
        timeout = float(os.environ.get("LLM_WRITER_TIMEOUT_S", "20"))
        t0 = time.monotonic()
        try:
            out, took = llm.chat_json(SYSTEM, user, timeout_s=timeout)
            body = out.get("body")
            reason = guard(body, required, msg["body"] + " " + (last.get("body") or ""))
        except llm.LLMError as e:
            body, took, reason = None, time.monotonic() - t0, f"llm: {e}"
        _log({"case": case.get("case_id"), "sid": sid, "n": draft.get("n"), "ok": reason is None, "reason": reason,
              "s": round(took, 2), "words": len((body or "").split())})
        if reason is None:
            msg = {**msg, "body": body.strip()[:8000]}
            return {**decision, "message": msg}
        self.stats["fallbacks"] += 1
        return decision


def make_agent(package=None, **knobs):
    """The negotiator of `sellm.agent.make_agent` (same KNOBS), with the LLM writing the e-mails."""
    return LLMWriterNegotiator(package, **{**KNOBS, **knobs})
