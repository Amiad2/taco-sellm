"""A supplier as the lab models it: what a package is worth to it, its floor, how it concedes.

Evidence behind the model (docs/LOG.md, experiments/RESULTS.md, runs/):

- **Acceptance.** A package is acceptable when its cash value to the supplier reaches its full
  cost. The value is the kit's `supplier_value` (price, payment at the supplier's cost of money,
  freight, chargebacks at its real defect rate) plus lever premiums read from the alternative
  sheets suppliers sent (a shorter lead time costs a capacity-tight plant, a fixed price costs a
  raw-material trader). Calibrated so that the cheapest acceptable package costs the case's known
  C_best, P01 gives a full cost of 129.91; the relationship charge the arena billed on our P01 deal
  independently implies 129.95.
- **Dynamics** (sandbox D01, 20 scripted sessions): the first counter is the same whatever we
  open with; after that the supplier gives back a share (0.6-0.85) of each step we make; it says
  `final_offer` at our 6th message, earlier when our steps are tiny; a price push after
  `final_offer` ended the thread once in two.

Everything is in value space (EUR per unit at the supplier's own standard terms), so a change of
structure - a later start, faster payment, a longer lead time - moves the price the way it moves
the supplier's cash, as the real suppliers' alternative sheets do.
"""

import copy
import math
from dataclasses import asdict, dataclass, field, fields

from arena_kit.cost import OPS, RELATIONSHIP_GOALS, closing_terms, must_haves_ok, supplier_value, total_cost

# dynamics a twin family varies (see Persona.ranges and Persona.vary)
VARIED = ("first_step", "mirror", "cap", "cap_decay", "patience", "claim_w", "walk_on_push", "noise")


@dataclass
class Persona:
    supplier_id: str
    name: str
    opening: dict  # the stated terms of its opening sheet (a subset of the negotiable fields)
    standard: dict  # its own terms for every field: what its value is measured against
    pdf_standard: dict  # what its quote PDF lists as standard terms: unstated terms close on these
    full_cost: float = 0.0  # its floor, EUR per unit in value space; set by calibration
    rate: float = 0.08  # its cost of money per year (more for a supplier short of cash)
    ppm_real: float | None = None  # the defect rate it really achieves (chargebacks cost it this)
    # EUR per unit: lead_time_days per day shorter than its standard, ppm_commitment per 1000 ppm
    # below ppm_real, contract_months per year longer, volume_per_year per +100 % volume,
    # fixed_price for a package without an index clause
    premiums: dict = field(default_factory=dict)
    hard_limits: dict = field(default_factory=dict)  # field -> [op, value] it never goes beyond
    first_step: float = 0.35  # share of (opening value - floor) given in its first counter
    mirror: float = 0.7  # share of each of our steps (in its value) it gives back
    patience: int = 6  # our messages until it says final_offer (a tiny step counts twice)
    tiny_step: float = 0.002  # a step below this share of its opening value counts as tiny
    cap: float = 0.009  # most it gives back for our step in its 2nd counter, share of its opening value
    cap_decay: float = 0.75  # that limit shrinks by this factor with every further counter
    walk_on_push: float = 0.5  # chance it walks when we push price after its final offer
    claim_weight: dict = field(default_factory=dict)  # kind -> share of (ask - floor) a verified claim takes off
    claim_kinds: list = field(default_factory=list)  # kinds of data that moved it ('took it into account')
    claim_w: float = 0.0  # share of (ask - floor) a verified claim of those kinds takes off
    ultimatum: float = 0.5  # multiplies `mirror` for the rest of the case after an ultimatum
    leak: float = 0.6  # multiplies `mirror` once we leak urgency, a budget or no alternative
    discloses: bool = False  # sends a cost breakdown when asked
    alternatives: bool = True  # adds a second package to its counters
    noise: float = 0.1  # relative spread of each concession: identical e-mails need not get identical replies
    approval_at: float | None = (
        None  # after giving this share of (opening - floor) its boss must approve: one round on hold
    )
    no_bid: bool = False  # it declines to quote (an RFQ bidder that does not bid)
    tone_walk: float = 0.0  # chance it ends the talks after an ultimatum or an insult
    withdraw_on_wait: float = 0.5  # chance it withdraws when left waiting at final_offer (sandbox D02)
    asks_data: bool = True  # asks 'Which figures is that based on?' when we ask a lot without data
    archetype: str = "twin"  # twin, family, group, job_shop, monopolist, trader, quality, capacity, generous
    ranges: dict = field(default_factory=dict)  # param -> plausible values (the twin's family)
    style: str = "corporate"  # family, corporate, casual
    sender: str = ""
    sender_name: str = ""
    opening_body: str | None = None
    drivers: list = field(default_factory=list)  # [series, share of cost, change %] for its letter
    traits: list = field(default_factory=list)
    notes: str = ""

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, d):
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in d.items() if k in known})

    def vary(self, rng):
        """A member of its family: each varied parameter drawn from its plausible values."""
        out = copy.copy(self)
        for k, values in self.ranges.items():
            if k in VARIED and values:
                setattr(out, k, rng.choice(values))
        return out

    # -- what a package is worth to it --------------------------------------------------------
    def closing(self, case, terms):
        return closing_terms(case, terms, self.standard)

    def value(self, case, terms):
        t = self.closing(case, terms)
        sup = {"standard": self.standard, "interest_rate": self.rate}
        if self.ppm_real is not None:
            sup["ppm"] = self.ppm_real
        return supplier_value(case, t, sup) + self.extra(t)

    def extra(self, t):
        p, s, out = self.premiums, self.standard, 0.0
        if p.get("lead_time_days") and t.get("lead_time_days") is not None and s.get("lead_time_days"):
            out -= p["lead_time_days"] * max(0, s["lead_time_days"] - t["lead_time_days"])
        if p.get("ppm_commitment") and t.get("ppm_commitment") is not None:
            ref = self.ppm_real if self.ppm_real is not None else s.get("ppm_commitment") or 0
            out -= p["ppm_commitment"] * max(0, ref - t["ppm_commitment"]) / 1000
        if p.get("contract_months") and s.get("contract_months") is not None:
            out += p["contract_months"] * (t["contract_months"] - s["contract_months"]) / 12
        if p.get("volume_per_year") and s.get("volume_per_year"):
            out += p["volume_per_year"] * (t["volume_per_year"] - s["volume_per_year"]) / s["volume_per_year"]
        if p.get("fixed_price") and not t.get("index_clause"):
            out -= p["fixed_price"]
        return out

    def relationship_view(self):
        """The supplier as the arena's relationship term sees it (its true full cost)."""
        sup = {"standard": self.standard, "interest_rate": self.rate, "full_cost": self.full_cost}
        if self.ppm_real is not None:
            sup["ppm"] = self.ppm_real
        return sup

    def price_for(self, case, structure, target, tick=True):
        """The unit price at which `structure` is worth `target` to the supplier (rounded up)."""
        v0 = self.value(case, {**structure, "unit_price": 0.0})
        v1 = self.value(case, {**structure, "unit_price": 1.0})
        if v1 - v0 <= 1e-9:
            return math.inf
        p = (target - v0) / (v1 - v0)
        if not tick:
            return p
        step = 0.01 if p < 20 else 0.05
        return round(math.ceil(round(p / step, 6)) * step, 2)

    def allows(self, terms):
        return all(
            terms.get(f) is None or OPS[op](terms[f], v) for f, (op, v) in self.hard_limits.items() if f in terms
        )

    def nearest_allowed(self, case, structure):
        """`structure` with every field beyond a hard limit moved to the closest allowed option."""
        out = dict(structure)
        for f, (op, v) in self.hard_limits.items():
            if f in out and out[f] is not None and not OPS[op](out[f], v):
                options = [o for o in case["term_options"].get(f, []) if o is not None and OPS[op](o, v)]
                out[f] = min(options, key=lambda o: abs(o - structure[f])) if options else v
        return out


def structures(case):
    """Every combination of the negotiable non-price fields over the case's options."""
    import itertools

    fields = [f for f in case["negotiable"] if f != "unit_price"]
    options = [case["term_options"].get(f) or [None] for f in fields]
    for combo in itertools.product(*options):
        yield {f: v for f, v in zip(fields, combo, strict=True) if v is not None or f == "index_clause"}


def buyer_cost(case, persona, terms):
    """C of a deal with this supplier, the relationship term priced with its true full cost."""
    return total_cost(case, terms, persona.pdf_standard, persona.relationship_view())


def best_package(case, persona):
    """(C, terms): the cheapest package for the buyer that this supplier would accept."""
    best = (math.inf, None)
    relationship = case["buyer"].get("category_goal") in RELATIONSHIP_GOALS
    for s in structures(case):
        if not persona.allows(s) or not must_haves_ok(case, {**s, "unit_price": 1.0}, persona.pdf_standard):
            continue
        p_min = persona.price_for(case, s, persona.full_cost, tick=False)
        if not math.isfinite(p_min) or p_min <= 0:
            continue

        def c(p, s=s):
            return buyer_cost(case, persona, {**s, "unit_price": round(p, 4)})

        if relationship:  # buyer cost rises with price, the relationship term falls: convex
            lo, hi = p_min, p_min * 1.3
            for _ in range(60):
                m1, m2 = lo + (hi - lo) / 3, hi - (hi - lo) / 3
                lo, hi = (lo, m2) if c(m1) <= c(m2) else (m1, hi)
            p = max(p_min, (lo + hi) / 2)
        else:
            p = p_min
        if (cost := c(p)) < best[0]:
            best = (cost, {**s, "unit_price": round(p, 2)})
    return best


def calibrate(case, personas, c_best, iterations=50):
    """Set each supplier's floor so that the cheapest package any of them accepts costs `c_best`.
    With several suppliers (an RFQ) every floor is the same share of that supplier's opening value."""
    openings = {sid: p.value(case, p.opening) for sid, p in personas.items()}
    lo, hi = 0.2, 1.5
    for _ in range(iterations):
        k = (lo + hi) / 2
        for sid, p in personas.items():
            p.full_cost = k * openings[sid]
        c = min(best_package(case, p)[0] for p in personas.values())
        lo, hi = (k, hi) if c < c_best else (lo, k)
    for sid, p in personas.items():
        p.full_cost = round(hi * openings[sid], 4)
    return min(best_package(case, p)[0] for p in personas.values())
