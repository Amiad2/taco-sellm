# ruff: noqa: E501
"""The negotiator with personality dials, for the lab (group C playbooks). It subclasses
sellm.negotiator.Negotiator and changes nothing in it: every dial at its default plays exactly the
negotiator. Dials, by what they stand for:

structure   pay_days (None | 14 | 30 | 45 | 60 | 90)   payment days we ask for, whatever the dossier says
            idx ("auto" | "none" | "db0" | "db3" | "db5")   the index clause we ask for
aggression  open_below, pace, keep_below, horizon, floor_share   (the negotiator's own knobs)
persuasion  n_args (0-3)        data arguments per e-mail
            arg_first (0, 1)    from which of our messages on we argue (0 = the first)
            arg_order           which kind of fact comes first: default | history | delivery | notice | forecast | quality
tone        plain | warm | firm   one sentence around the proposal
"""

import re

from sellm.negotiator import ID_RE, Negotiator, Thread

DIALS = dict(
    pay_days=None,
    idx="auto",
    n_args=1,
    arg_first=0,
    arg_order="default",
    tone="plain",
    menu=1,
    precedent=0,
    committee=0,
)
ORDERS = {
    "default": None,
    "history": ("po", "fc", "sc_otd", "doc", "idx", "cost"),
    "delivery": ("sc_otd", "sc_ppm", "qn", "po", "fc", "doc"),
    "notice": ("doc", "idx", "cost", "po", "fc", "sc_otd"),
    "forecast": ("fc", "po", "sc_otd", "doc", "idx", "cost"),
    "quality": ("sc_ppm", "qn", "sc_otd", "po", "fc", "doc"),
}
TONES = {
    "plain": None,
    "warm": "We value the years of reliable cooperation and want to keep it that way.",
    "firm": "We need a clear step on the price to move forward on our side.",
    "empathy": "We understand that your material costs weigh on you, and we want a fair split of that burden.",
    "split": "We suggest that we meet in the middle of the remaining gap.",
    "volume": "We can plan reliably with you and keep our orders steady.",
}


class DialNegotiator(Negotiator):
    def __init__(self, package=None, **knobs):
        self.d = {k: knobs.pop(k, v) for k, v in DIALS.items()}
        super().__init__(package, **knobs)
        self.name = "dials " + " ".join(f"{k}={v}" for k, v in {**self.d, **knobs}.items())

    # -- structure ---------------------------------------------------------------------------------
    def _force(self, case, s):
        s = dict(s)
        neg, opts = case["negotiable"], case.get("term_options", {})
        if self.d["pay_days"] is not None and "payment_days" in neg:
            if self.d["pay_days"] in (opts.get("payment_days") or [self.d["pay_days"]]):
                s["payment_days"] = self.d["pay_days"]
        if self.d["idx"] != "auto" and "index_clause" in neg:
            options = opts.get("index_clause") or []
            want = self.d["idx"]
            for o in options:
                if (o is None and want == "none") or (o and want == f"db{int(o.get('deadband_pct', 0))}"):
                    s["index_clause"] = o
        return s

    def opening_structure(self, case, v):
        return self._force(case, super().opening_structure(case, v))

    def structure(self, case, v, s0):
        return self._force(case, super().structure(case, v, s0))

    def menu(self, case, v, sheet):
        return super().menu(case, v, sheet) if self.d["menu"] else []

    # -- persuasion --------------------------------------------------------------------------------
    def arguments(self, case, v, views, live, sheet):
        if self.d["n_args"] <= 0 or len(v.asks) < self.d["arg_first"]:
            return []
        out = list(super().arguments(case, v, views, live, sheet))
        if len(out) < self.d["n_args"]:
            ours_here = " ".join(m.get("body") or "" for m in v.ours)
            cited = {i for w in views.values() for m in w.ours for i in ID_RE.findall(m.get("body") or "")}
            cited |= {i for s in out for i in ID_RE.findall(s)}
            _, standing = v.standing
            more = self.banked(case, v, cited, ours_here, standing.get("unit_price"), self.d["n_args"] - len(out))
            out += [s for s in more if s not in out]
        return out[: self.d["n_args"]]

    def banked(self, case, v, cited, ours_here, price, limit=None):
        """The negotiator's bank, ordered by the dial and up to `limit` sentences (one per topic)."""
        order = ORDERS.get(self.d["arg_order"])
        limit = limit or max(1, self.d["n_args"])
        try:
            from sellm import calculator, claims

            def topic(ref):
                head = ref.split(":", 1)[0]
                return {"ctr": "doc"}.get(head, head)

            used = {topic(i) for i in cited}
            with calculator.LOCK:
                found = claims.arguments(
                    case, v.sid, self.intel(case, v), package=self.package, used=cited, price=price
                )
            if order:
                found = sorted(found, key=lambda a: order.index(a["kind"]) if a["kind"] in order else len(order))
            out = []
            for a in found:
                if a["kind"] == "quote" or a["sentence"] in ours_here or not a.get("ids"):
                    continue
                t = topic(a["ids"][0])
                if self.k["one_per_topic"] and t in used:
                    continue
                sentence = a["sentence"]
                if a["kind"] in ("sc_ppm", "qn") or "ppm" in sentence:
                    if self.k["ppm"] == "skip":
                        continue
                    if self.k["ppm"] == "plain":
                        sentence = re.sub(r"(\d),(\d{3})(?=\s*ppm)", r"\1\2", sentence)
                used.add(t)
                out.append(sentence)
                if len(out) >= limit:
                    break
            return out
        except Exception:
            return []

    # -- tone --------------------------------------------------------------------------------------
    def message(self, case, threads, draft):
        decision = super().message(case, threads, draft)
        body = (decision.get("message") or {}).get("body")
        if not body or draft.get("kind") != "ask":
            return decision
        lines = [TONES.get(self.d["tone"])]
        if draft.get("n", 0) == 0:  # the first ask only: an anchor, not a repeated demand
            try:
                v = Thread(case, draft["sid"], threads[draft["sid"]])
                if self.d["precedent"]:
                    lines.append(self.precedent_line(case, v))
                if self.d["committee"]:
                    lines.append(self.committee_line(case, v))
            except Exception:
                pass
        lines = [x for x in lines if x]
        if lines:
            head, sep, rest = body.partition("\n\n")
            para, tail = rest.split("\n\n", 1) if "\n\n" in rest else (rest, "")
            cut = max(para.rfind(" On that basis"), para.rfind(" We can improve"))
            extra = " ".join(lines)
            para = f"{para[:cut]} {extra}{para[cut:]}" if cut > 0 else f"{extra} {para}"
            decision["message"]["body"] = head + sep + para + ("\n\n" + tail if tail else "")
        return decision

    def precedent_line(self, case, v):
        """Our own past renewals with this supplier: what it asked and what was agreed (negotiation_history,
        no data ID: nothing for the arena to check, a fact for the supplier to read)."""
        found = self.intel(case, v)
        events = []
        for part in case.get("parts") or []:
            events += (((found.get("parts") or {}).get(part) or {}).get("history") or {}).get("events") or []
        rows = [
            e
            for e in sorted(events, key=lambda e: e["date"])
            if e.get("asked_pct") is not None and e.get("settled_pct") is not None
        ]
        rows = [e for e in rows if e["asked_pct"] > 0][-2:]
        if not rows:
            return ""
        past = " and ".join(
            f"+{e['settled_pct']:g} % in {e['date'][:4]} (you had asked +{e['asked_pct']:g} %)" for e in rows
        )
        return f"In our last annual renewals we agreed {past}."

    def committee_line(self, case, v):
        """Its approval ladder, from our own meeting notes: a rise above 2 % goes to its pricing committee."""
        found = self.intel(case, v)
        if not any(x.get("kind") == "approval_ladder" for x in found.get("signals") or []):
            return ""
        return "We understand that changes above 2 % need your pricing committee, so please take our proposal there."
