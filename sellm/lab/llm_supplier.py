# ruff: noqa: E501  (prompt texts)
"""LLM suppliers: the calibrated engine sets the hard limits, an LLM plays the person inside them.

That is how the brief describes the arena's suppliers: "Its hard limits come from its own situation:
it never sells below its cost floor, bigger moves need the boss's approval, data you cite is checked
by ID, and it gives nothing without a move from you. Inside those limits it decides as that person
would - reading your whole e-mail."

Per reply:
1. The engine (`bot.SupplierThread`, calibrated on our real sessions) works out its own move on a
   shadow copy: claim results, tone, the step we made, its concession, approval, patience.
2. Code turns that into bounds for this round: the lowest price the person may go to (never below
   the floor; at most a bit beyond the engine's move, more when we brought verified data), whether
   it must stay at a final offer, whether walking away is plausible.
3. The LLM, given the company (register facts, archetype, cost of money, capacity, quality), its
   history with Hollerau (letters, call and meeting notes, news, past renewals), this case and the
   thread so far, reads our e-mail and decides: counter, agree, final offer, hold or walk away, the
   price, a variant it prefers, which documents to attach, and writes the e-mail.
4. Code enforces the bounds, computes every number, renders the term sheets and documents (as the
   arena does: "never written by a language model"). If the LLM fails the engine's reply is used and
   counted (`llm_fail` in the result) - never silently.
"""

import copy
import hashlib
import json
import logging
import os
import re
import threading
import time
from pathlib import Path

from .bot import NAMES, SupplierThread, fmt
from .reader import read

log = logging.getLogger("arena")
DATA_LOCK = threading.Lock()  # one SQLite connection is shared by the threads of a process
CACHE = Path(__file__).resolve().parents[2] / "runs" / "lab" / "llm-cache"
ARCHETYPE_TEXT = {
    "family": "a family-owned company; the owner or a long-serving sales person writes. You remember how the "
    "buyer treated you, value loyalty and respect, dislike pressure, and are proud of your craft.",
    "group": "part of a larger group with an approval ladder; you are a sales manager who needs your managing "
    "director's sign-off for bigger moves. Formal, process-driven, careful with precedents.",
    "job_shop": "a small owner-run job shop that needs cash and work; informal, quick, flexible on terms, "
    "very interested in fast payment and steady orders.",
    "monopolist": "one of very few qualified sources; you barely move on price, say so politely, and do not "
    "fear losing the business.",
    "trader": "a stockist or trader whose margin depends on material prices; you insist on index clauses for "
    "longer terms and talk about material costs.",
    "quality": "a supplier with a quality problem the buyer knows about; you are defensive about defects but "
    "want to keep the business, and quality commitments cost you real money.",
    "capacity": "a supplier whose capacity is tight; short lead times and extra volume cost you overtime, and "
    "you prioritise customers who commit.",
    "generous": "a supplier hungry for this business; you move readily when the buyer moves.",
    "twin": "",
}
SYSTEM = """You play the person at a supplier who answers a buyer's e-mails in a B2B negotiation. The buyer is
Hollerau Pumpenwerke GmbH, a German pump maker. Stay in character: your company, your situation, your
history with Hollerau, as given below. Decide as that person would, reading the buyer's whole e-mail:
its term sheets, its arguments and data, its questions, its tone.

Hard limits you never break (they come from your company's economics and authority):
- Never quote a price below LOWEST_ALLOWED for this round (your floor or your boss's limit for one step).
- Give nothing without a move from the buyer, a convincing argument, or verified data.
- A final offer is final: once you said it, you do not go lower; you accept if the buyer meets it.
- Never reveal your costs, floor or margin unless your company is open about costs (see below).

Reply with ONE JSON object, nothing else:
{"decision": "counter" | "agree" | "final_offer" | "hold" | "walk_away",
 "price": <unit price in EUR on the buyer's best sheet's terms, or on "terms" if you change them>,
 "terms": {<optional: terms of the buyer's best sheet you will not accept, with the value you offer instead>},
 "alternative": {<optional: ONE term changed your way for a second package at the same value to you>},
 "attach": [<optional: "cost_breakdown" | "delivery_schedule" | "8d_report">],
 "email": "<your reply, 50-150 words, in your voice; write {PRICE} where your price goes and {ALT_PRICE}
          for the alternative's price; no other prices or percentages than those given to you>",
 "reasons": ["<2-4 short internal reasons for your decision>"]}

decision: counter = a new offer (price at or above LOWEST_ALLOWED); agree = you accept the buyer's best sheet
as it stands (only if it is at or above LOWEST_ALLOWED); final_offer = a counter you mark as your last word;
hold = you keep your current offer; walk_away = you end the talks (only when the buyer has been hostile,
threatened you, or pushes after your final offer).

How you usually behave is given as "the move your company usually makes" and "the decision your company
usually takes" (measured on real negotiations with you). Follow it unless the buyer's e-mail gives you
a reason to differ: a convincing argument or verified data that bears on your situation, a trade you
value, sincere appreciation (then you may move further, down to LOWEST_ALLOWED); pressure, threats,
rudeness, irrelevant or wrong data, no move from the buyer (then you move less or hold). Say final offer
when your patience is running out or you are close to your limit - not earlier without a reason."""


def _complete_json():
    """An LLM call returning parsed JSON: OpenAI-compatible endpoints with JSON mode, else the kit's."""
    import httpx

    from arena_kit.cli import load_env

    load_env(Path(__file__).resolve().parents[2] / ".env")
    provider = os.environ.get("LLM_PROVIDER", "openai")
    model = os.environ.get("LAB_SUPPLIER_MODEL") or os.environ.get("LLM_MODEL")
    if provider != "openai":
        from arena_kit.agents.llm import llm_from_env, parse

        complete = llm_from_env()
        return lambda system, user: parse(complete(system, user))
    base = os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    headers = {"Authorization": f"Bearer {os.environ.get('LLM_API_KEY', '')}"}
    client = httpx.Client(timeout=90.0)

    def call(system, user):
        body = {
            "model": model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "response_format": {"type": "json_object"},
        }
        for attempt in range(4):
            r = client.post(f"{base}/chat/completions", json=body, headers=headers)
            if r.status_code == 400 and "response_format" in r.text and "response_format" in body:
                body.pop("response_format")
                continue
            if r.status_code in (429, 500, 502, 503, 504) and attempt < 3:
                time.sleep(float(r.headers.get("retry-after", 2**attempt)))
                continue
            r.raise_for_status()
            text = r.json()["choices"][0]["message"]["content"]
            return json.loads(re.search(r"\{.*\}", text, re.S).group(0))
        raise RuntimeError("LLM call failed after retries")

    return call


class Brain:
    """The LLM behind the suppliers of a process, with a disk cache (same prompt, same answer)."""

    def __init__(self, cache=True):
        self.call, self.cache = _complete_json(), cache
        self.calls = self.cached = self.failed = 0

    def ask(self, system, user):
        key = hashlib.sha256((system + "\n" + user).encode()).hexdigest()
        path = CACHE / f"{key}.json"
        if self.cache and path.exists():
            self.cached += 1
            return json.loads(path.read_text(encoding="utf-8"))
        self.calls += 1
        out = self.call(system, user)
        if self.cache:
            CACHE.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(out), encoding="utf-8")
        return out


def dossier(package, persona, case):
    """What the person knows about its own company and its history with Hollerau, from the data."""
    with DATA_LOCK:
        return _dossier(package, persona, case)


def _dossier(package, persona, case):
    out, sid = [], persona.supplier_id
    if package is not None:
        intel = package.query("select * from supplier_intel where supplier_id = ?", (sid,))
        if intel:
            i = intel[0]
            out.append(
                f"Company: {persona.name}, {i.get('legal_form') or ''}, founded {i.get('founded')}, owner type "
                f"{i.get('owner_type')}{', group ' + i['group_parent'] if i.get('group_parent') else ''}, "
                f"{i.get('staff')} staff, turnover {i.get('turnover_band')}, equity ratio {i.get('equity_ratio_pct')} %, "
                f"credit index {i.get('credit_index')} (12 months ago {i.get('credit_index_12m_ago')}; higher is worse)."
            )
        hist = package.query(
            "select date, part_id, type, asked_pct, settled_pct, note from negotiation_history where supplier_id = ? "
            "order by date",
            (sid,),
        )
        if hist:
            out.append(
                "Past price rounds with Hollerau: "
                + "; ".join(
                    f"{h['date'][:7]} {h['type']}: asked {h['asked_pct']} %, settled {h['settled_pct']} %"
                    + (f" ({h['note']})" if h.get("note") else "")
                    for h in hist[-6:]
                    if h.get("asked_pct") is not None
                )
            )
        docs = package.query(
            "select id, date, kind, subject from documents where supplier_id = ? order by date", (sid,)
        )
        texts = []
        for d in docs[-8:]:
            try:
                body = package.document(d["id"])
            except (FileNotFoundError, ValueError):
                continue
            body = re.sub(r"\s+", " ", body.split("\n", 3)[-1])[:500]
            texts.append(f"[{d['date']} {d['kind']}: {d['subject']}] {body}")
        if texts:
            out.append("Letters, e-mails and notes about you (some written by the buyer's staff):\n" + "\n".join(texts))
        news = package.query("select date, headline, body from news where supplier_id = ? order by date", (sid,))
        if news:
            out.append("News about you: " + " | ".join(f"{n['date']} {n['headline']}" for n in news[-4:]))
    if persona.notes:
        out.append(f"What we know of your behaviour: {persona.notes}")
    return "\n".join(out)


def profile(persona, case, package):
    """The standing brief for the LLM: who it is and what its business needs."""
    b = case["buyer"]
    lines = [
        f"You are {persona.sender_name or 'the sales manager'} at {persona.name}.",
        ARCHETYPE_TEXT.get(persona.archetype, ""),
        f"Your style of writing: {persona.style} (family: warm, personal; corporate: formal; casual: short, direct).",
        f"The enquiry: {case['title']}. Parts: {', '.join(case['parts'])}. Need about {b['need_per_year']} pieces "
        f"a year. Negotiable: {', '.join(case['negotiable'])}. Fixed: {json.dumps(case.get('fixed_terms', {}))}.",
        f"Your own standard terms: {json.dumps({k: v for k, v in persona.standard.items() if k in NAMES})}.",
    ]
    rate = persona.rate
    if rate >= 0.15:
        lines.append(
            f"Cash is tight for you (your cost of money is about {rate:.0%} a year): faster payment is worth a lot to you."
        )
    elif rate <= 0.07:
        lines.append("Money is cheap for you: payment terms matter little to you, price matters.")
    if persona.premiums.get("lead_time_days"):
        lines.append("Your capacity is busy: a shorter lead time than your standard costs you overtime.")
    if persona.premiums.get("fixed_price"):
        lines.append("You carry material price risk: a fixed price without an index clause costs you a premium.")
    if persona.premiums.get("ppm_commitment"):
        lines.append(
            f"Your real defect rate is about {persona.ppm_real} ppm: a tighter quality commitment costs you money."
        )
    if persona.hard_limits:
        lines.append(f"Lines you do not cross: {json.dumps(persona.hard_limits)}.")
    lines.append("You are open about costs and may send a cost breakdown if asked." if persona.discloses else
                 "Your costs, margin and calculation stay internal; you do not send cost breakdowns.")  # fmt: skip
    if persona.claim_kinds:
        lines.append(f"Data that tends to convince you when verified: {', '.join(persona.claim_kinds)}.")
    history = dossier(package, persona, case)
    if history:
        lines.append(history)
    return "\n".join(x for x in lines if x)


def _sheet_text(terms):
    return ", ".join(f"{NAMES.get(k, k)} {fmt(k, v)}" for k, v in terms.items())


class LLMSupplierThread(SupplierThread):
    """A supplier thread whose replies an LLM writes and decides, inside the engine's bounds."""

    def __init__(self, persona, case, rng=None, session=None, brain=None, package=None):
        super().__init__(persona, case, rng, session)
        self.brain, self.package = brain, package
        self.brief = None
        self.llm_calls = self.llm_fail = 0

    def _brief(self):
        if self.brief is None:
            self.brief = profile(self.p, self.case, self.package)
        return self.brief

    def _shadow(self):
        """A copy that can run the engine without touching this thread or the session."""
        sh = copy.copy(self)
        sh.messages, sh.reasons, sh.history = list(self.messages), list(self.reasons), list(self.history)
        sh.rng = copy.deepcopy(self.rng)
        if self.session is not None:
            s = copy.copy(self.session)
            s.used, s.offers = set(self.session.used), dict(self.session.offers)
            sh.session = s
        return sh

    def respond(self, msg):
        if self.brain is None:
            return super().respond(msg)
        before = {k: getattr(self, k) for k in ("ask", "status", "round")}
        sh = self._shadow()
        engine = SupplierThread.respond(sh, msg)  # the engine's own reply and the state after it
        try:
            out = self._decide(msg, engine, sh, before)
            self.llm_calls += 1
            return out
        except Exception as e:  # the engine's reply stands, and it is counted
            self.llm_fail += 1
            log.warning("LLM supplier failed (%s): the engine's reply is used", e)
            return self._adopt(sh, engine)

    def _adopt(self, sh, engine):
        """Take over the shadow's state and reply as this thread's own."""
        for k in ("ask", "status", "pressure", "mirror", "best_ours", "leaked", "warm", "counters", "timeouts",
                  "approved", "pending", "round", "closed", "standing"):  # fmt: skip
            setattr(self, k, getattr(sh, k))
        if self.session is not None:
            self.session.used |= sh.session.used
        self.history.append(engine)
        self.messages.append(engine)
        self.reasons.append(sh.reasons[-1])
        for ts in engine.get("term_sheets") or []:
            if self.session is not None:
                self.session.offers[ts["term_sheet_id"]] = (self.p.supplier_id, ts["terms"])
        return engine

    def _decide(self, msg, engine, sh, before):
        p, case = self.p, self.case
        sheets = [ts.get("terms", ts) for ts in msg.get("term_sheets") or []]
        best = max(sheets, key=lambda s: p.value(case, s)) if sheets else (self.standing or {}).get("terms")
        structure = {k: v for k, v in (best or {}).items() if k != "unit_price"}
        structure = p.nearest_allowed(case, structure)
        a, e, f = before["ask"], sh.ask, p.full_cost
        verified = [r for r in engine.get("claim_results") or [] if r["result"] == "verified"]
        feats = read(msg.get("body") or "")
        extra = 0.25 * max(0.0, a - e) + (0.08 * max(0.0, a - f) if verified else 0.0)
        if feats["appreciation"] and "family" in p.traits:
            extra += 0.03 * max(0.0, a - f)
        final_locked = before["status"] == "final_offer"
        lowest = a if final_locked else max(f, e - extra)
        # the person may move less than its company usually does, but not to nothing: at least half the
        # usual step (the dynamics are calibrated on real replies; the LLM varies them, it does not replace them)
        highest = a if final_locked or e >= a - 1e-9 else a - 0.5 * (a - e)
        self._bounds = {"engine_ask": e, "lowest": lowest, "highest": highest}

        def price_at(value, s=structure):
            return p.price_for(case, s, value)

        p_ask, p_engine, p_low, p_high = price_at(a), price_at(e), price_at(lowest), price_at(highest)
        ours = {**structure, "unit_price": best["unit_price"]} if best and "unit_price" in best else None
        ours_value = p.value(case, best) if best else None
        thread = []
        for m in self.history[-8:]:
            who = "BUYER" if m.get("from") == "buyer" else f"YOU ({m.get('status')})"
            ts = "; ".join(_sheet_text(t.get("terms", t)) for t in m.get("term_sheets") or [])
            thread.append(
                f"{who}: {re.sub(chr(10) + '+', ' ', (m.get('body') or '')[:700])}"
                + (f"\n   sheets: {ts}" if ts else "")
            )
        claims = engine.get("claim_results") or []
        user = "\n".join([
            "THE NEGOTIATION SO FAR (oldest first):", *thread,
            "",
            f"THE BUYER'S NEW E-MAIL (their message {self.round} of {case.get('round_limit', 10)}):",
            msg.get("body") or "(no text)",
            "Their term sheets: " + (" | ".join(_sheet_text(s) for s in sheets) or "none (a question or a holding message)"),
            f"Data they cited, as checked against the records: {[c['result'] for c in claims] or 'none'}",
            "",
            "YOUR NUMBERS FOR THIS REPLY (on the terms of the buyer's best sheet: "
            f"{_sheet_text(structure) or 'its terms'}):",
            f"- your current offer is worth EUR {p_ask:.2f} on these terms",
            f"- LOWEST_ALLOWED this round: EUR {p_low:.2f}" + (" (you are at your final offer)" if final_locked else ""),
            f"- HIGHEST you may stay at this round: EUR {p_high:.2f} (the buyer moved; your company always answers a move)"
            if highest < a - 1e-9 else "- the buyer did not move: you may hold your offer",
            f"- the move your company usually makes now: to EUR {p_engine:.2f}",
            f"- the buyer offers EUR {best['unit_price']:.2f}" if ours else "- the buyer sent no price",
            f"- your status so far: {before['status']}; your patience: {'running out' if sh.pressure >= p.patience - 1 else 'fine'}",
            "- a bigger move than usual needs your boss's approval" if p.approval_at and not self.approved else "",
            f"- the decision your company usually takes now: {engine['status']}",
        ])  # fmt: skip
        d = self.brain.ask(SYSTEM + "\n\nWHO YOU ARE\n" + self._brief(), user)
        return self._apply(d, msg, engine, sh, before, structure, best, ours_value, lowest, final_locked)

    def _apply(self, d, msg, engine, sh, before, structure, best, ours_value, lowest, final_locked):
        p, case = self.p, self.case
        decision = str(d.get("decision", "counter")).lower()
        # the state the engine reached (pressure, mirror, claims used, ...), then our own move on it
        for k in ("pressure", "mirror", "best_ours", "leaked", "warm", "counters", "timeouts", "approved", "pending",
                  "round"):  # fmt: skip
            setattr(self, k, getattr(sh, k))
        if self.session is not None:
            self.session.used |= sh.session.used
        claims = engine.get("claim_results") or []
        attach = []
        for kind in d.get("attach") or []:
            if kind == "cost_breakdown" and p.discloses:
                from .bot import breakdown_text

                price = (self.standing or {}).get("terms", {}).get("unit_price") or p.opening["unit_price"]
                attach.append(("cost-breakdown", breakdown_text(p, price)))
            elif kind == "delivery_schedule":
                from .bot import schedule_text

                attach.append(("delivery-schedule", schedule_text(p, case, self.standing)))
            elif kind == "8d_report":
                from .bot import eight_d_text

                attach.append(("8d-report", eight_d_text(p, case)))
        feats = read(msg.get("body") or "")
        provoked = (
            feats["ultimatum"] or feats["hostile"] or final_locked or self.round >= case.get("round_limit", 10) - 1
        )
        if decision == "walk_away" and not provoked:
            decision = "final_offer" if self.round > 2 else "hold"
        if engine["status"] == "walked_away" and decision not in ("walk_away",):
            decision = "final_offer" if final_locked else decision  # the person may stay, as a final offer
        text = str(d.get("email") or "")
        reasons = [str(r) for r in d.get("reasons") or []][:4]
        if decision == "walk_away":
            self.closed, self.ask = "walked_away", before["ask"]
            return self._out("walked_away", [], text, reasons, claims, attach)
        # real suppliers agree when the buyer meets them, rarely earlier: close to its usual ask at least
        e = self._bounds["engine_ask"]
        agree_from = e - 0.25 * max(0.0, e - lowest)
        if (
            decision == "agree"
            and best
            and ours_value is not None
            and ours_value >= agree_from - 1e-6
            and p.allows(best)
        ):
            self.ask = min(before["ask"], max(lowest, ours_value))
            return self._out("agreed", [dict(best)], text, reasons, claims, attach, agreed=True)
        highest = self._bounds["highest"]
        if decision == "hold" and highest < before["ask"] - 1e-9 and not (feats["ultimatum"] or feats["hostile"]):
            decision = "counter"  # it always answers a move from the buyer (calibrated), at least a little
        if decision == "hold" or (not msg.get("term_sheets") and decision != "final_offer"):
            self.ask = before["ask"]
            sheets = [self.standing["terms"]] if self.standing else []
            return self._out(before["status"], sheets, text, reasons, claims, attach)
        # counter or final offer: its price on its terms, kept inside the bounds
        terms = dict(structure)
        for k, v in (d.get("terms") or {}).items():
            options = case["term_options"].get(k) or []
            if k in terms and k != "unit_price" and (v in options or v == p.standard.get(k)):
                terms[k] = v
        terms = p.nearest_allowed(case, terms)
        try:
            price = float(d.get("price"))
        except (TypeError, ValueError):
            price = p.price_for(case, terms, sh.ask)
        value = p.value(case, {**terms, "unit_price": price})
        ceiling = before["ask"] if feats["ultimatum"] or feats["hostile"] else highest
        value = min(ceiling, max(lowest, value))
        self.ask = value
        price = p.price_for(case, terms, value)
        out = [{**terms, "unit_price": price}]
        alt = d.get("alternative") or {}
        if len(alt) == 1 and p.alternatives:
            ((k, v),) = alt.items()
            options = case["term_options"].get(k) or []
            if k in terms and (v in options or v == p.standard.get(k)) and v != terms[k]:
                s2 = p.nearest_allowed(case, {**terms, k: v})
                if s2 != terms:
                    out.append({**s2, "unit_price": p.price_for(case, s2, value)})
        # a final offer at most one round before its patience says so, unless it is at its limit
        early_ok = sh.pressure >= p.patience - 1 or value <= p.full_cost + 1e-6
        final = (decision == "final_offer" and early_ok) or final_locked or sh.status == "final_offer"
        final = final or value <= p.full_cost + 1e-6
        if best and ours_value is not None and ours_value >= value - 1e-6 and p.allows(best):
            return self._out("agreed", [dict(best)], text, reasons, claims, attach, agreed=True)
        return self._out("final_offer" if final else "open", out, text, reasons, claims, attach)

    def _out(self, status, sheets, text, reasons, claims, attach, agreed=False):
        """The e-mail with the code's numbers in place of the LLM's placeholders."""
        price = f"€{sheets[0]['unit_price']:.2f}" if sheets else ""
        alt = f"€{sheets[1]['unit_price']:.2f}" if len(sheets) > 1 else price
        body = re.sub(r"(EUR|€)\s*\{PRICE\}", "{PRICE}", text)
        body = re.sub(r"(EUR|€)\s*\{ALT_PRICE\}", "{ALT_PRICE}", body)
        body = body.replace("{PRICE}", price).replace("{ALT_PRICE}", alt).strip()
        msg = self._mail(status, sheets, [], attach)
        signed = self.p.name.split(" GmbH")[0] in body or (self.p.sender_name or "§") in body
        msg["body"] = body if signed else f"{body}\n\n{self.p.sender_name or self.p.name}"
        msg["claim_results"] = claims
        self.reasons[-1]["lines"] = reasons
        self.reasons[-1]["llm"] = True
        return msg

    def _drivers(self):
        """Its cost drivers with their true twelve-month change, for its quote letter."""
        rows = self.package.query(
            f"select series_id, weight from cost_drivers where part_id in ({','.join('?' * len(self.case['parts']))})",
            tuple(self.case["parts"]),
        )
        parts = []
        for r in rows[:3]:
            ids = self.package.ids(f"idx:{r['series_id']}@")
            if len(ids) >= 13:
                a, b = self.package.lookup(ids[-13])["value"], self.package.lookup(ids[-1])["value"]
                parts.append(f"{r['series_id']} {(b / a - 1) * 100:+.1f} % in twelve months, {r['weight']:.0%} of cost")
        return "; ".join(parts)

    def opening(self):
        """Twins keep their real opening e-mail; other suppliers get one written by the LLM."""
        if self.brain is None or self.p.opening_body or self.p.no_bid:
            return super().opening()
        terms = dict(self.p.opening)
        with DATA_LOCK:
            drivers = self._drivers() if self.package is not None else ""
        user = (
            f"Write your quote e-mail for this enquiry (50-120 words). Your offered terms: {_sheet_text(terms)}. "
            f"Write {{PRICE}} where the price goes. Your cost drivers (true figures you may quote): {drivers or 'none given'}. "
            'Reply as JSON: {"email": "...", "reasons": []}'
        )
        try:
            d = self.brain.ask(SYSTEM + "\n\nWHO YOU ARE\n" + self._brief(), user)
            self.llm_calls += 1
            msg = self._mail("open", [terms], [], subject=f"Quote from {self.p.name}: {self.case['title']}")
            text = re.sub(r"(EUR|€)\s*\{PRICE\}", "{PRICE}", str(d.get("email", "")))
            msg["body"] = text.replace("{PRICE}", f"€{terms['unit_price']:.2f}")
            return msg
        except Exception as e:
            self.llm_fail += 1
            log.warning("LLM supplier opening failed (%s): template used", e)
            return super().opening()
