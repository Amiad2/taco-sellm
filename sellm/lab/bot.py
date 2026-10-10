"""The lab's supplier in one thread: reads our e-mail, decides in value space, writes back.

Decision per message (see `persona.py` for the evidence):
1. Our best term sheet is the one worth most to the supplier. Our *step* is how much more it is
   worth than our best sheet so far - so a trade the supplier values counts as a step.
2. First counter: a fixed share of (opening value - floor), whatever we offered. Later counters:
   `mirror` times our step, plus a one-off for each verified, relevant claim, at most `cap` per
   round, never below the floor. No step from us, no move from it.
3. `agreed` when our sheet is worth at least its new ask; `final_offer` when its patience is used
   up (a tiny step counts twice) or it is at its floor.
4. After `final_offer`: meet it and it agrees; push price and it may walk; anything else holds.
The e-mail is assembled from sentences like the real suppliers' reasons.
"""

import random

from arena_kit.docs import LABELS

from .reader import read

NAMES = {f: label for label, f in LABELS.items()}
EUR_FIELDS = ("unit_price", "tooling_eur", "chargeback_eur_per_complaint")
CLAIM_TOPIC = {
    "idx": "index",
    "quote": "quote",
    "offer": "offer",
    "sc": "delivery record",
    "qn": "quality record",
    "po": "order history",
    "cost": "cost estimate",
    "fc": "volume change",
    "news": "news",
    "doc": "notice period",
    "ctr": "notice period",
}
GREET = {"family": "Guten Tag,", "corporate": "Dear Sir or Madam,", "casual": "Hallo,"}
CLOSE = {
    "family": "Viele Grüße",
    "corporate": "Mit freundlichen Grüßen",
    "casual": "Beste Grüße",
}


def fmt(field, v):
    if v is None:
        return "none"
    if field == "index_clause":
        share = round(v["material_share"] * 100)
        return f"{v['series']}, {share}% material, deadband {v['deadband_pct']} %, base {v['base_month']}"
    if field in EUR_FIELDS:
        return f"{float(v):.2f}"
    if field in ("effective_date", "incoterm"):
        return str(v)
    return str(int(v))


def quote_text(persona, case, offer_id, stated, title="Angebot / Quote"):
    """A quote PDF's text in the arena's layout (the kit's `docs.quote_terms` parses it)."""
    fixed = case.get("fixed_terms", {})
    rest = {k: v for k, v in persona.pdf_standard.items() if k not in stated and k not in fixed and k in NAMES}
    lines = [persona.name, "To: Hollerau Pumpenwerke GmbH", f"{title} {offer_id}", "Offered terms"]
    lines += [f"{NAMES[k]} {fmt(k, v)}" for k, v in stated.items() if k in NAMES]
    lines.append("Our standard terms (apply to everything not stated above)")
    lines += [f"{NAMES[k]} {fmt(k, v)}" for k, v in rest.items()]
    lines.append("Terms fixed by your enquiry")
    lines += [f"{NAMES[k]} {fmt(k, v)}" for k, v in fixed.items() if k in NAMES]
    lines.append(f"Part(s): {', '.join(case['parts'])}. Enquiry: {case['title']}.")
    return "\n".join(lines)


def schedule_text(persona, case, standing):
    terms = (standing or {}).get("terms", {})
    volume = terms.get("volume_per_year") or persona.standard.get("volume_per_year") or case["buyer"]["need_per_year"]
    lead = terms.get("lead_time_days") or persona.standard.get("lead_time_days")
    rows = [f"{m} | {round(volume / 12)} | {round(volume / 12) * m}" for m in range(1, 13)]
    return "[Delivery schedule]\nMonth | Quantity | Cumulative\n" + "\n".join(rows) + f"\nLead time (days) | {lead} |"


def eight_d_text(persona, case):
    ppm = persona.ppm_real if persona.ppm_real is not None else persona.standard.get("ppm_commitment")
    commit = persona.standard.get("ppm_commitment") or ppm
    return (
        f"8D report - {persona.name}\nPart(s): {', '.join(case['parts'])}\nD1 Team: quality manager, production\n"
        f"D2 Problem: defect rate {ppm} ppm (rolling 12 months)\nD4 Root cause: process variation\n"
        f"D5-D7 Actions: added inspection, process capability study\nppm commitment: {commit}"
    )


def breakdown_text(persona, price):
    shares = [("Material", 0.45), ("Conversion", 0.33), ("Overhead", 0.14)]
    cost = persona.full_cost
    rows = [f"{n} | {cost * s / 0.92:.2f} | {s / 0.92 * cost / price:.0%}" for n, s in shares]
    rows.append(f"Margin | {price - cost:.2f} | {(price - cost) / price:.0%}")
    return "[Cost breakdown]\nElement | EUR per unit | Share of price\n" + "\n".join(rows)


class SupplierThread:
    def __init__(self, persona, case, rng=None, session=None):
        self.p, self.case = persona, case
        self.rng = rng or random.Random(0)
        self.session = session  # shared: claim checker, cited keys, offers of every thread
        self.key = persona.supplier_id.split(":", 1)[1]
        self.round, self.pressure, self.status, self.closed = 0, 0, "open", None
        self.ask = persona.value(case, persona.opening)
        self.a0 = self.ask
        self.mirror = persona.mirror
        self.best_ours, self.leaked, self.warm, self.counters = None, False, False, 0
        self.timeouts, self.approved, self.pending = 0, False, 0.0
        self.standing, self.messages, self.reasons = None, [], []
        self.history = []  # both sides in order: our e-mails (added by the table) and its replies

    # -- messages ------------------------------------------------------------------------------
    def _mail(self, status, sheets, lines, attach=(), subject=None):
        n = len(self.messages)
        out_sheets = []
        for i, terms in enumerate(sheets):
            sid = f"offer:{self.key}-{self.round}" + ("" if i == 0 else "-a")
            out_sheets.append({"term_sheet_id": sid, "terms": terms})
            if self.session is not None:
                self.session.offers[sid] = (self.p.supplier_id, terms)
        self.standing = out_sheets[0] if out_sheets else None
        self.status = status
        attachments = []
        for kind, text in attach:
            attachments.append(
                {"attachment_id": f"att:{self.key}-{self.round}-{kind}", "name": f"{kind}.txt", "text": text}
            )
        if out_sheets and (status in ("final_offer", "agreed") or self.round == 0):
            oid = out_sheets[0]["term_sheet_id"]
            attachments.append(
                {
                    "attachment_id": f"att:{self.key}-{self.round}-quote",
                    "name": f"quote-{oid.replace(':', '-')}.pdf",
                    "text": quote_text(self.p, self.case, oid, out_sheets[0]["terms"]),
                }
            )
        body = "\n\n".join([GREET.get(self.p.style, "Dear Sir or Madam,"), " ".join(lines)])
        body += f"\n\n{CLOSE.get(self.p.style, 'Kind regards')}\n{self.p.sender_name or self.p.name}"
        stated = set(out_sheets[0]["terms"]) if out_sheets else set()
        msg = {
            "message_id": f"msg:{self.key}-{self.round}-{n}",
            "from": self.p.sender or f"sales@{self.key}",
            "from_name": self.p.sender_name,
            "subject": subject or f"Re: {self.case['title']}",
            "body": body,
            "term_sheets": out_sheets,
            "status": status,
            "signals": {"reply_delay_days": 2, "validity_days": 7 if status == "final_offer" else 30},
            "missing_fields": sorted(set(self.case["negotiable"]) - stated) if out_sheets else [],
            "claim_results": [],
            "attachments": attachments,
            "refs": [],
            "action": None,
        }
        self.messages.append(msg)
        self.history.append(msg)
        self.reasons.append({"round": self.round, "status": status, "ask": round(self.ask, 4), "lines": lines})
        return msg

    def opening(self):
        terms = dict(self.p.opening)
        if self.p.no_bid:
            self.closed = "no_bid"
            lines = ["Thank you for your enquiry. Unfortunately we are not in a position to quote for this part."]
            return self._mail("no_bid", [], lines, subject=f"Re: {self.case['title']}")
        if self.p.opening_body:
            msg = self._mail("open", [terms], [])
            msg["body"] = self.p.opening_body
            msg["subject"] = f"Quote from {self.p.name}: {self.case['title']}"
            return msg
        lines = ["Thank you for your enquiry. Please find our quote attached."]
        for series, share, change in self.p.drivers:
            lines.append(f"{series} rose {change:.1f} % in twelve months and is {share:.0%} of our cost.")
        lines.append(f"We offer €{terms['unit_price']:.2f} per unit. This offer remains valid for 30 days.")
        return self._mail("open", [terms], lines, subject=f"Quote from {self.p.name}: {self.case['title']}")

    def timeout(self, last_round=False):
        """We left it waiting more than 60 s: the offer stands, re-issued with a new ID, and its
        patience drops. Left waiting at its final offer it may withdraw; the third timeout in a row
        (or one after the last round) ends the thread."""
        self.round += 1
        self.timeouts += 1
        self.pressure += 1
        if self.status == "final_offer" and self.rng.random() < self.p.withdraw_on_wait:
            self.closed = "walked_away"
            line = "We need to plan our capacity, so we are closing this enquiry. We wish you all the best."
            return self._mail("walked_away", [], [line])
        if self.timeouts >= 3 or last_round:
            self.closed = "timeout"
            return self._mail("walked_away", [], ["Without an answer from your side we close this enquiry."])
        sheets = [self.standing["terms"]] if self.standing else []
        return self._mail(self.status, sheets, ["Without movement from your side we cannot move either."])

    # -- the decision --------------------------------------------------------------------------
    def respond(self, msg):
        p, case = self.p, self.case
        self.round += 1
        self.timeouts = 0
        body = msg.get("body") or ""
        feats = read(body, self.session.reader if self.session is not None else None)
        lines, attach = [], []
        tol = 0.0005 * self.a0

        # data we cited
        bonus, results = 0.0, []
        if self.session is not None:
            results = self.session.checker.check(
                p.supplier_id, body, msg.get("refs") or [], self.session.offers, self.session.used
            )
        if len(results) >= 3 and len(set(msg.get("refs") or [])) > 6:
            lines.append("We received a lot of material; we looked at what bears on this part.")
        for r in results:
            topic = CLAIM_TOPIC.get(r["kind"], "data")
            if r["result"] == "verified":
                w = p.claim_weight.get(r["kind"], p.claim_w if r["kind"] in p.claim_kinds else 0.0)
                if w > 0:
                    bonus += w * max(0.0, self.ask - p.full_cost)
                    lines.append(f"We checked the {topic} data you cited; it holds and we took it into account.")
                else:
                    lines.append(
                        f"We checked the {topic} data you cited; it holds, but it does not change our calculation."
                    )
            elif r["result"] == "duplicate":
                lines.append(f"We have already taken that {topic} data into account.")
            elif r["result"] == "irrelevant":
                lines.append(f"The {topic} data you cited does not bear on this part.")
            else:
                self.mirror *= 0.8
                self.pressure += 1
                lines.append(f"The {topic} figures you cite do not match our records.")
        r_out = [{"index": r["index"], "result": r["result"]} for r in results]

        # tone
        if feats["ultimatum"] or feats["hostile"]:
            if self.rng.random() < p.tone_walk:
                self.closed = "walked_away"
                lines.append("We are not prepared to continue on this basis. We end our offer here.")
                reply = self._mail("walked_away", [], lines)
                reply["claim_results"] = r_out
                return reply
            self.mirror *= p.ultimatum
            self.pressure += 1
            lines.append("We do not negotiate under pressure; our offer reflects our costs.")
        if feats["leak"] and not self.leaked:
            self.leaked = True
            self.mirror *= p.leak
        if feats["appreciation"] and not self.warm and "family" in p.traits:
            self.warm = True
            bonus += 0.03 * max(0.0, self.ask - p.full_cost)
            lines.append("We value our long-standing cooperation.")
        if feats["asks_breakdown"]:
            if p.discloses:
                price = self.standing["terms"]["unit_price"] if self.standing else p.opening["unit_price"]
                attach.append(("cost-breakdown", breakdown_text(p, price)))
                lines.append("Please find our cost breakdown attached.")
            else:
                lines.append("Our calculation is our property; we do not share a breakdown.")
        if feats["asks_margin"] and not p.discloses:
            lines.append("Our margin and our limits stay internal.")
        neg = case["negotiable"]
        if feats["asks_capacity"] and (
            {"lead_time_days", "volume_per_year"} & set(neg) or "capacity_tight" in p.traits
        ):
            attach.append(("delivery-schedule", schedule_text(p, case, self.standing)))
            lines.append("Please find our delivery schedule attached.")
        if feats["quality"] and ("ppm_commitment" in neg or p.archetype == "quality"):
            attach.append(("8d-report", eight_d_text(p, case)))
            lines.append("Our 8D report with the corrective actions is attached.")

        sheets = [ts.get("terms", ts) for ts in msg.get("term_sheets") or []]
        if not sheets:  # a question or a holding message: the offer stands, re-issued
            terms = [self.standing["terms"]] if self.standing else []
            lines.append("Our offer stands.")
            reply = self._mail(self.status, terms, lines, attach)
            reply["claim_results"] = r_out
            return reply

        values = [p.value(case, s) for s in sheets]
        i = max(range(len(sheets)), key=values.__getitem__)
        ours, best_sheet = values[i], sheets[i]
        verified = any(r["result"] == "verified" for r in results)
        if p.asks_data and not verified and ours < self.ask - 0.06 * self.a0:
            lines.append("Which figures is that based on? Please send us the data.")
        structure = {k: v for k, v in best_sheet.items() if k != "unit_price"}
        step = ours - self.best_ours if self.best_ours is not None else None
        self.best_ours = ours if self.best_ours is None else max(self.best_ours, ours)

        if self.status == "final_offer":
            if ours >= self.ask - tol and p.allows(best_sheet):
                reply = self._agree(best_sheet, lines, attach)
            elif step is not None and step <= tol and self.rng.random() < p.walk_on_push:
                self.closed = "walked_away"
                lines.append("We have made our final offer. We regret that we could not reach an agreement.")
                reply = self._mail("walked_away", [], lines)
            else:
                lines.append("Please note that this is our final offer. Please decide.")
                reply = self._mail("final_offer", [self.standing["terms"]], lines, attach)
            reply["claim_results"] = r_out
            return reply

        # concession
        gap = max(0.0, self.ask - p.full_cost)
        self.counters += 1
        # an offer far below its floor offends: a smaller first counter, and patience runs out faster
        # (sandbox D01: opening 16 % below the floor got 0.70 instead of 1.40 and a final offer after our
        # 3rd message instead of the 6th; 2-4 % below showed neither)
        lowball = p.full_cost > 0 and (p.full_cost - ours) / p.full_cost > p.lowball
        if step is None:
            concession = p.first_step * gap * (p.lowball_first if lowball else 1.0)
            self.pressure += 1 + (p.lowball_pressure if lowball else 0)
        elif step > tol:
            # it gives back a share of our step that shrinks as the step grows, and less every round:
            # on D01 steps of 0.15 / 0.6 / 2.6 got about 0.13 / 0.4 / 0.9 back
            saturation = max(1e-9, p.cap * self.a0)
            concession = self.mirror * step / (1 + step / saturation) * p.cap_decay ** max(0, self.counters - 2)
            self.pressure += (2 if step < p.tiny_step * self.a0 else 1) + (p.lowball_pressure if lowball else 0)
        else:
            concession = 0.0
            self.pressure += 1
            lines.append("Without movement from your side we cannot move either.")
        if p.noise and concession > 0:
            concession *= max(0.0, self.rng.gauss(1.0, p.noise))
        concession += bonus + self.pending
        self.pending = 0.0
        if (
            p.approval_at
            and not self.approved
            and self.a0 - self.ask + concession > p.approval_at * (self.a0 - p.full_cost)
        ):
            # a bigger move needs the boss: this round it holds, the next brings the step
            self.approved, self.pending = True, concession
            lines.append("A further step needs the approval of our managing director; we will come back to you.")
            reply = self._mail("open", [self.standing["terms"]] if self.standing else [], lines, attach)
            reply["claim_results"] = r_out
            return reply
        self.ask = max(p.full_cost, self.ask - concession)

        if ours >= self.ask - tol and p.allows(best_sheet):
            reply = self._agree(best_sheet, lines, attach)
            reply["claim_results"] = r_out
            return reply

        final = self.pressure >= p.patience or self.ask <= p.full_cost + tol
        counter = p.nearest_allowed(case, structure)
        if counter != structure:
            changed = [NAMES.get(k, k) for k in structure if counter.get(k) != structure.get(k)]
            lines.append(f"We cannot offer {', '.join(changed).lower()} as requested; we keep our standard there.")
        price = p.price_for(case, counter, self.ask)
        offer = {**counter, "unit_price": price}
        out = [offer]
        if p.alternatives and not final and (alt := self._alternative(counter)) is not None:
            out.append(alt)
        if step is not None and step > tol or step is None:
            lines.append(f"In response to your proposal we can adjust our price to €{price:.2f} per unit.")
        if len(out) > 1:
            alt_txt = ", ".join(
                f"{NAMES.get(k, k).lower()} {fmt(k, v)}"
                for k, v in out[1].items()
                if out[0].get(k) != v and k != "unit_price"
            )
            lines.append(f"Alternatively, with {alt_txt}: €{out[1]['unit_price']:.2f} per unit.")
        if final:
            lines.append("Please note that this is our final offer. Please decide.")
        reply = self._mail("final_offer" if final else "open", out, lines, attach)
        reply["claim_results"] = r_out
        return reply

    def _agree(self, terms, lines, attach):
        lines.append("We accept your proposal and look forward to your order.")
        return self._mail("agreed", [dict(terms)], lines, attach)

    def _alternative(self, structure):
        """Its own preferred variant of our structure: one lever moved its way, same value to it."""
        p, case, best = self.p, self.case, None
        for f in structure:
            options = case["term_options"].get(f) or []
            for o in options:
                if o == structure[f]:
                    continue
                s = {**structure, f: o}
                if not p.allows(s):
                    continue
                price = p.price_for(case, s, self.ask)
                if price >= p.price_for(case, structure, self.ask):
                    continue  # only variants that let it offer a lower price
                gain = p.price_for(case, structure, self.ask) - price
                if best is None or gain > best[0]:
                    best = (gain, {**s, "unit_price": price})
        return best[1] if best else None
