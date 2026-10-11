# ruff: noqa: E501  (long sentences and messages)
"""The case, a thread and the supplier as numbers. Everything here is a pure function of the case
file and the e-mails: no state is kept between moves, so a fresh agent resumes any session.

- `CaseModel`: our total cost C (the arena's own function `arena_kit.cost.total_cost`), the sheets a
  case allows, the price that makes a structure cost a given C, and C of the alternative/opening.
- `Thread`: one supplier's e-mails read once (its standing offer, its alternatives, our asks, the
  prices it has quoted per structure, how much of our steps it gives back).
- `Supplier`: what a deal is worth to it (`supplier_value` at its cost of money), our estimate of its
  full cost and the prices it puts on the levers that are not cash.
"""

import itertools
import math
import re

from arena_kit.cost import (
    RELATIONSHIP_GOALS,
    closing_terms,
    complete_offer,
    must_haves_ok,
    supplier_value,
    total_cost,
)
from arena_kit.docs import quote_terms, standard_terms
from arena_kit.play import ENDED, moves_left

EPS = 1e-6
MAX_STRUCTURES = 20000  # above this many combinations the structure search goes field by field
READY = ("final_offer", "agreed")
PRICE_FREE = {"unit_price"}


def strip(terms):
    """A sheet without its price: the structure."""
    return {f: v for f, v in terms.items() if f not in PRICE_FREE}


def key(structure):
    return tuple(sorted((f, repr(v)) for f, v in structure.items()))


class CaseModel:
    def __init__(self, case):
        self.case = case
        self.b = case["buyer"]
        self.negotiable = list(case["negotiable"])
        self.options = case.get("term_options") or {}
        self.relationship = bool(
            self.b.get("category_goal") in RELATIONSHIP_GOALS
            and self.b.get("relationship_eur_per_point")
            and self.b.get("sustainable_margin_pct")
        )
        alt = self.b.get("alternative") or {}
        self.c_alt = total_cost(case, alt["terms"]) if (alt.get("terms") or {}).get("unit_price") else math.inf

    # -- cost ------------------------------------------------------------------------------------
    def c(self, terms, std=None, supplier=None):
        if not terms or terms.get("unit_price") is None:
            return math.inf
        return total_cost(self.case, terms, std, supplier)

    def price_for(self, structure, cost, std=None, supplier=None):
        """The unit price at which `structure` costs `cost` (C is linear in the price without the
        relationship term)."""
        c0 = self.c({**structure, "unit_price": 0.0}, std, supplier)
        c1 = self.c({**structure, "unit_price": 1.0}, std, supplier)
        return (cost - c0) / (c1 - c0) if c1 > c0 else None

    def ok(self, terms, std=None):
        return bool(terms) and terms.get("unit_price") is not None and must_haves_ok(self.case, terms, std)

    def sheet(self, terms):
        return complete_offer(self.case, terms)

    # -- the space of sheets -----------------------------------------------------------------------
    def fields(self):
        return [f for f in self.negotiable if f != "unit_price"]

    def structures(self, base=None):
        """Every combination of the negotiable fields' options. Above MAX_STRUCTURES (a hidden case
        with many fields): `base` and every sheet one field away from it, so the search stays fast."""
        fields = self.fields()
        opts = [self.options.get(f) or [None] for f in fields]
        if math.prod(len(o) for o in opts) <= MAX_STRUCTURES:
            for combo in itertools.product(*opts):
                yield {f: v for f, v in zip(fields, combo, strict=True) if v is not None or f == "index_clause"}
            return
        base = base or {f: o[0] for f, o in zip(fields, opts, strict=True)}
        start = {f: base.get(f) for f in fields}
        yield start
        for f, o in zip(fields, opts, strict=True):
            for v in o:
                if v != start.get(f):
                    yield {**start, f: v}

    def coverage(self, terms, std=None):
        t = closing_terms(self.case, terms, std)
        years = min(t["contract_months"] / 12 if t["contract_months"] else 1.0, self.b["horizon_years"])
        need = self.b["need_per_year"]
        return min(t["volume_per_year"], need) * years / (need * self.b["horizon_years"])


class Thread:
    """One supplier's thread, read once."""

    def __init__(self, cm, sid, events):
        self.cm, self.case, self.sid, self.events = cm, cm.case, sid, list(events or [])
        self.theirs = [m for m in self.events if m.get("from") != "buyer"]
        self.ours = [m for m in self.events if m.get("from") == "buyer"]
        self.opening = next((m for m in self.theirs if m.get("term_sheets")), None)
        self.last = self.theirs[-1] if self.theirs else {}
        self.status = self.last.get("status")
        self.sheets = [s for s in self.last.get("term_sheets") or [] if s.get("terms")]
        self.asks = [m["term_sheets"][0]["terms"] for m in self.ours if m.get("term_sheets")]
        self.holds = sum(1 for m in self.ours if not m.get("term_sheets") and not m.get("action"))
        self.left = moves_left(self.case, self.events)
        std0 = {}
        for att in (self.opening or {}).get("attachments") or []:
            if (att.get("name") or "").startswith("quote") and att.get("text"):
                std0 = quote_terms(att["text"]).get("standard", {})
                break
        self.std0 = std0
        self.std = {**std0, **standard_terms(self.events)}

    @property
    def live(self):
        return bool(self.theirs) and self.status not in ENDED

    @property
    def fresh(self):
        """Its last e-mail answers a holding e-mail of ours: the offer ID we see is current."""
        if len(self.events) < 2:
            return False
        ours = self.events[-2]
        return ours.get("from") == "buyer" and not ours.get("term_sheets") and not ours.get("action")

    @property
    def standing(self):
        """(term_sheet_id, terms): only the first sheet of its last e-mail can be accepted."""
        return (self.sheets[0].get("term_sheet_id"), self.sheets[0]["terms"]) if self.sheets else (None, {})

    def filled(self, terms):
        """Its sheet with every negotiable field: what it leaves out closes on its standard terms."""
        return complete_offer(self.case, {**self.std, **{k: v for k, v in (terms or {}).items() if v is not None}})

    def c(self, terms, supplier=None):
        return self.cm.c(terms, self.std, supplier)

    def ok(self, terms):
        return self.cm.ok(terms, self.std)

    @property
    def opening_terms(self):
        return self.filled(self.opening["term_sheets"][0]["terms"]) if self.opening else {}

    def quoted(self):
        """{structure key: price} it has put on each structure: its latest sheets, then its opening."""
        out = {}
        raws = [s["terms"] for s in self.sheets]
        if self.opening and len(self.theirs) > 1:
            raws.append(self.opening["term_sheets"][0]["terms"])
        for raw in raws:
            t = self.filled(raw)
            if t.get("unit_price") is not None:
                out.setdefault(key(strip(t)), t["unit_price"])
        return out

    def quoted_sheets(self):
        """Every distinct full sheet it has put a price on (latest first)."""
        seen, out = set(), []
        for m in reversed(self.theirs):
            for s in m.get("term_sheets") or []:
                t = self.filled(s.get("terms"))
                if t.get("unit_price") is None or key(t) in seen:
                    continue
                seen.add(key(t))
                out.append(t)
        return out

    def rounds(self):
        """[(our ask, its answer)] in order, full sheets."""
        out, asked = [], None
        for m in self.events:
            sheets = m.get("term_sheets") or []
            if m.get("from") == "buyer":
                asked = complete_offer(self.case, sheets[0]["terms"]) if sheets else asked
            elif asked is not None and sheets:
                answer = self.filled(sheets[0]["terms"])
                if answer.get("unit_price") is not None:
                    out.append((asked, answer))
                asked = None
        return out

    def pace(self, default):
        """The share of our steps it has given back on an unchanged structure (0.25-2), else `default`."""
        rounds = self.rounds()
        if len(rounds) < 2:
            return default
        last_ask, last_ans = key(strip(rounds[-1][0])), key(strip(rounds[-1][1]))
        same = [r for r in rounds if key(strip(r[0])) == last_ask and key(strip(r[1])) == last_ans]
        if len(same) < 2:
            return default
        ours = same[-1][0]["unit_price"] - same[0][0]["unit_price"]
        theirs = same[0][1]["unit_price"] - same[-1][1]["unit_price"]
        if ours <= EPS:
            return default
        return min(2.0, max(0.25, theirs / ours))

    def moved(self):
        """Its last priced offer is cheaper for us than the one before (or it has made only one)."""
        offers = [self.c(self.filled(m["term_sheets"][0]["terms"])) for m in self.theirs if m.get("term_sheets")]
        return len(offers) < 2 or offers[-1] < offers[-2] - EPS

    def price_steps(self):
        """Its prices on its standing structure, oldest first."""
        return [self.filled(m["term_sheets"][0]["terms"]).get("unit_price") for m in self.theirs if m.get("term_sheets")]


PAY_PAIR = re.compile(r"payment|zahlungsziel", re.I)


class Supplier:
    """Our model of one supplier: its value function, its cost, its lever prices."""

    # What suppliers charged for levers that are not cash in its value (measured from their own
    # alternative sheets, docs/LEARNINGS.md): share of its price per unit of the lever.
    LEAD_PER_DAY = 0.0049  # P10: 1.90 on 32.20 for 12 days shorter
    # ppm: not priced. P11 (Sun 03:05, session a11271a2) walked the same price ladder (46.5, 46.0,
    # 45.5) for 1500 ppm as for 300 ppm, so a looser commitment only cost us (0.620 against 0.778).
    PPM_PER_1000 = 0.0
    DEADBAND_PER_PT = 0.004  # P08 0.12 on 5.5 and P18 0.10 on 5.6 for 5 points

    def __init__(self, cm, thread, brief, rate=None):
        self.cm, self.t, self.brief = cm, thread, brief
        theirs = thread.opening["term_sheets"][0]["terms"] if thread.opening else {}
        std = {**{f: v for f, v in theirs.items() if f != "unit_price" and v is not None}, **thread.std}
        full = closing_terms(cm.case, std, std)
        full.pop("unit_price", None)
        self.standard = full
        self.rate = rate if rate is not None else (brief.cost_of_money if brief and brief.known else 0.08)

    def value(self, terms, rate=None):
        return supplier_value(self.cm.case, terms, {"standard": self.standard, "interest_rate": rate or self.rate})

    def price_at_value(self, structure, worth, rate=None):
        """The price on `structure` that is worth `worth` to it."""
        v0 = self.value({**structure, "unit_price": 0.0}, rate)
        v1 = self.value({**structure, "unit_price": 1.0}, rate)
        return (worth - v0) / (v1 - v0) if v1 > v0 else None

    def estimate(self, full_cost):
        """The supplier as the relationship term needs it."""
        return {"standard": self.standard, "interest_rate": self.rate, "full_cost": full_cost}

    def measured_rate(self):
        """Its yearly cost of money read from its own sheets that differ only in payment days and
        price (price step / mean price / day step x 360), or None."""
        sheets = self.t.quoted_sheets()
        rates = []
        for a, b in itertools.combinations(sheets, 2):
            da, db = strip(a), strip(b)
            if set(da) != set(db) or "payment_days" not in da or da["payment_days"] == db["payment_days"]:
                continue
            if any(da[f] != db[f] for f in da if f != "payment_days"):
                continue
            days = db["payment_days"] - da["payment_days"]
            step = b["unit_price"] - a["unit_price"]
            mean = (a["unit_price"] + b["unit_price"]) / 2
            if mean > 0 and days:
                r = step / mean / days * 360
                if 0 < r < 1:
                    rates.append(r)
        return sum(rates) / len(rates) if rates else None

    def lever_premium(self, structure, ref_structure, price):
        """EUR per unit it asks for moving non-cash levers from `ref_structure` to `structure`."""
        extra = 0.0
        a, b = ref_structure, structure
        # lead time: priced only by a supplier whose capacity is tight (P10 1.90 for 12 days, P05's 70240
        # 1.50 for 10 days); the others walked the same price ladder at 42 as at 28 days (P05, Sun 03:19)
        tight = bool(self.brief and self.brief.signal("capacity_tight"))
        if tight and "lead_time_days" in self.cm.negotiable and a.get("lead_time_days") is not None and b.get("lead_time_days") is not None:
            extra += (a["lead_time_days"] - b["lead_time_days"]) * self.LEAD_PER_DAY * price
        if "ppm_commitment" in self.cm.negotiable and a.get("ppm_commitment") is not None and b.get("ppm_commitment") is not None:
            extra += (a["ppm_commitment"] - b["ppm_commitment"]) / 1000 * self.PPM_PER_1000 * price
        if "index_clause" in self.cm.negotiable:
            ca, cb = a.get("index_clause"), b.get("index_clause")
            if ca and cb:
                extra += ((cb.get("deadband_pct") or 0) - (ca.get("deadband_pct") or 0)) * self.DEADBAND_PER_PT * price
        return extra
