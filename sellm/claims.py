"""The argument bank (group C, docs/PLAN.md sections 3 and 10): every fact the arena checks
(docs/CONTEXT.md section 7), written as one sentence with our figure next to its IDs.

- `citable_for(package, supplier_id, part_ids, case=None)`: what we may cite to this supplier about
  these parts, as entries `{ids, kind, figure, unit, about, statement, helps_buyer, private}` plus a
  few extra fields (`strength`, `case_only`, `sensitive`). The dossier builder and the case overlay
  call it; with `case` the case's own `facts` are included too.
- `arguments(case, supplier_id, dossier=None, package=None, used=())`: the entries that help us in
  this case, best first, as `{sentence, ids, kind, ...}`; IDs already used are left out (each counts
  once per case).

Every statement passes `sellm.lab.claims.ClaimChecker` (tests/test_claims.py: 0 contradicted over all
detailed suppliers). Wording follows sentences the arena verified in our practice runs: one argument
per sentence, the figure in the same sentence, no other figure near it, thousands with a comma
(EUR 1,608.32: a parser may read "1608.32" as 160). Facts that help the supplier
stay in with `helps_buyer: False`, so the negotiator knows what the supplier may cite.
"""

import logging
import threading

log = logging.getLogger(__name__)

# news topics: what they mean for our position (docs/PLAN.md section 10, signal kinds)
BUYER_NEWS = {"free_capacity", "short_time_work", "credit_watch", "credit_downgrade", "new_plant"}
SUPPLIER_NEWS = {"allocation", "full_order_book", "big_order", "chip_shortage", "energy_contract"}
SENSITIVE_NEWS = {"credit_watch", "credit_downgrade", "short_time_work", "restructuring"}
SKIP_NEWS = {"noise", "market"}
PPM_HIGH = 1000  # a scorecard above this is a quality lever
OTD_TARGET = 95.0  # Hollerau's quality agreement
# order of kinds when nothing else decides, per case type (a lower index is used first)
ORDER = {
    "quality": ["sc_ppm", "qn", "sc_otd", "cost", "idx", "doc", "po", "fc", "news", "quote"],
    "capacity": ["fc", "sc_otd", "cost", "idx", "doc", "po", "news", "sc_ppm", "qn", "quote"],
    "rfq": ["quote", "cost", "idx", "fc", "sc_otd", "sc_ppm", "po", "doc", "news", "qn"],
}
DEFAULT_ORDER = ["doc", "idx", "cost", "po", "fc", "sc_otd", "sc_ppm", "qn", "news", "quote"]

_CACHE, _LOCK = {}, threading.Lock()


def _month(m, back):
    y, mo = map(int, m.split("-")[:2])
    n = y * 12 + mo - 1 - back
    return f"{n // 12:04d}-{n % 12 + 1:02d}"


def _per(price_unit):
    return "per unit" if not price_unit or int(price_unit) == 1 else f"per {int(price_unit)} units"


def _q(pkg, sql, params=()):
    try:
        return pkg.query(sql, params)
    except Exception:  # a package without SQLite (or an old one): fewer entries, never an error
        return []


class _Bank:
    """One package's facts, indexed by kind, supplier and part (built once, about 20 ms)."""

    def __init__(self, pkg):
        self.facts = getattr(pkg, "facts", None) or {}
        self.by_kind = {}
        for i, f in self.facts.items():
            self.by_kind.setdefault(i.split(":", 1)[0], []).append((i, f))
        last = {}
        for _, f in self.by_kind.get("idx", []):
            last[f["series"]] = max(last.get(f["series"], ""), f["month"])
        self.series_last = last
        self.data_last = max(last.values(), default="")
        self.drivers = {}  # part -> [(series, weight)]
        for r in _q(pkg, "select part_id, series_id, weight from cost_drivers"):
            self.drivers.setdefault(r["part_id"], []).append((r["series_id"], r.get("weight") or 0.0))
        self.cost_owner = {r["id"]: r.get("supplier_id") for r in _q(pkg, "select id, supplier_id from should_cost")}
        self.parts = {r["id"]: r for r in _q(pkg, "select id, description, price_unit from parts")}
        fc = _q(pkg, "select id, shared_with_suppliers from forecasts")
        self.shared = {r["id"]: bool(r.get("shared_with_suppliers")) for r in fc}
        self.letters = {r["id"]: r.get("kind") for r in _q(pkg, "select id, kind from documents")}

    def entries(self, sid, parts, facts=None, prefer=()):
        """Entries over `facts` (default: the package's), for supplier `sid` and these parts; IDs in
        `prefer` (a case's own facts) win where only one entry per part is made."""
        own = facts is None
        facts = self.facts if own else facts
        kinds = self.by_kind if own else _by_kind(facts)
        out = []
        for build in (self._idx, self._cost, self._sc, self._qn, self._po, self._fc, self._news, self._notice,
                      self._quote):  # fmt: skip
            try:
                out += build(kinds, facts, sid, parts, prefer)
            except Exception as e:  # one kind less, never a lost dossier
                log.warning("claims: %s for %s failed: %s: %s", build.__name__, sid, type(e).__name__, e)
        return out

    # -- one builder per kind ------------------------------------------------------------------
    def _idx(self, kinds, facts, sid, parts, prefer=()):
        """Each cost-driver series of the parts over 12 and 6 months, ending at its last month."""
        out, seen = [], set()
        for part in parts:
            for series, weight in self.drivers.get(part, []):
                last = self.series_last.get(series)
                if not last or series in seen or _months(last, self.data_last) > 12:
                    continue
                seen.add(series)
                for back in (12, 6):
                    a, b = f"idx:{series}@{_month(last, back)}", f"idx:{series}@{last}"
                    if a not in self.facts or b not in self.facts:
                        continue
                    change = (self.facts[b]["value"] / self.facts[a]["value"] - 1) * 100
                    ma, mb = a.split("@")[1], b.split("@")[1]
                    out.append(_entry([a, b], "idx", round(change, 1), "%", part,
                                      f"The index {series} changed {change:+.1f} % from {ma} to {mb} ({a}, {b}).",
                                      change < -0.5, strength=abs(change) * max(weight, 0.05), window=back,
                                      weight=weight, series=series))  # fmt: skip
        return out

    def _cost(self, kinds, facts, sid, parts, prefer=()):
        """This supplier's own plant estimate; else a generic one. Another plant's is never cited to it."""
        out, done = [], set()
        # the case's own estimate first, then its own plant, then a generic one
        rows = sorted(kinds.get("cost", []), key=lambda r: (r[0] not in prefer, self._cost_supplier(*r) != sid))
        for i, f in rows:
            part, owner = f.get("part"), self._cost_supplier(i, f)
            if part not in parts or part in done or owner not in (sid, None) or not f.get("unit_cost"):
                continue
            done.add(part)
            cost, per = float(f["unit_cost"]), _per(f.get("price_unit") or self._price_unit(part))
            text = f"Our bottom-up estimate of the full cost is EUR {cost:,.2f} {per} before margin ({i})."
            out.append(_entry([i], "cost", cost, "EUR", part, text, True, strength=3.0, plant_specific=owner == sid))
        return out

    def _sc(self, kinds, facts, sid, parts, prefer=()):
        rows = sorted((r for r in kinds.get("sc", []) if r[1].get("supplier") == sid), key=lambda r: r[1]["quarter"])
        if not rows:
            return []
        i, f = rows[-1]  # the latest quarter: a rolling twelve months already
        q = f["quarter"]
        otd, ppm = float(f["otd_pct"]), float(f.get("ppm") or 0)
        return [
            _entry([i], "sc_otd", otd, "%", sid,
                   f"Your rolling twelve-month on-time delivery in {q} was {otd:.1f} % ({i}).",
                   otd < OTD_TARGET, strength=max(0.0, OTD_TARGET - otd) / 10),
            _entry([i], "sc_ppm", ppm, "ppm", sid,
                   f"Your rolling twelve-month quality level in {q} was {ppm:,.0f} ppm ({i}).",
                   ppm > PPM_HIGH, strength=ppm / PPM_HIGH),
        ]  # fmt: skip

    def _qn(self, kinds, facts, sid, parts, prefer=()):
        """The three latest complaints on these parts within twelve months of the data."""
        start = _month(self.data_last, 12) if self.data_last else ""
        rows = [(i, f) for i, f in kinds.get("qn", []) if f.get("supplier") == sid and f.get("part") in parts]
        rows = sorted((r for r in rows if r[1].get("date", "")[:7] >= start), key=lambda r: r[1]["date"])[-3:]
        return [
            _entry([i], "qn", float(f["ppm"]), "ppm", f["part"],
                   f"Complaint {i} of {f['date']} recorded {float(f['ppm']):,.0f} ppm.", float(f["ppm"]) >= PPM_HIGH,
                   strength=float(f["ppm"]) / PPM_HIGH / 4)
            for i, f in reversed(rows) if f.get("ppm") is not None
        ]  # fmt: skip

    def _po(self, kinds, facts, sid, parts, prefer=()):
        """Per part: the first and the last order of the last 24 months, with their prices."""
        out = []
        start = _month(self.data_last, 24) if self.data_last else ""
        for part in parts:
            rows = sorted(
                (r for r in kinds.get("po", []) if r[1].get("supplier") == sid and r[1].get("part") == part
                 and r[1].get("date", "")[:7] >= start and r[1].get("unit_price")),
                key=lambda r: (r[1]["date"], r[0]),
            )  # fmt: skip
            if len(rows) < 2:
                continue
            (a, fa), (b, fb) = rows[0], rows[-1]
            pa, pb = float(fa["unit_price"]), float(fb["unit_price"])
            change = (pb / pa - 1) * 100
            per = _per(fa.get("price_unit") or self._price_unit(part))
            text = (f"We ordered from you at EUR {pa:,.2f} {per} in {fa['date'][:7]} and at EUR {pb:,.2f} {per} "
                    f"in {fb['date'][:7]} ({a}, {b}).")  # fmt: skip
            out.append(_entry([a, b], "po", round(change, 1), "%", part, text, change > 0.5,
                              strength=abs(change) / 2))  # fmt: skip
            # The same history as an argument: the last order at its lowest price of the last twelve months
            # against the latest one, where the price has jumped since. "5.75 two years ago, 5.84 today" was
            # dismissed 42 times; "5.26 in June, 5.84 in September" was taken into account (P18 0.598 -> 0.657,
            # P08 0.637 -> 0.659, Sun 04:30).
            year = _month(self.data_last, 12) if self.data_last else ""
            recent = [r for r in rows[:-1] if r[1]["date"][:7] >= year]
            if recent:
                lowest = min(float(r[1]["unit_price"]) for r in recent)
                c, fc = [r for r in recent if float(r[1]["unit_price"]) == lowest][-1]
                jump = (pb / lowest - 1) * 100
                if jump >= 2.0 and jump > change + 0.5 and c != a:
                    months = (fc["date"][:7], fb["date"][:7])
                    text = (f"We ordered from you at EUR {lowest:,.2f} {per} in {months[0]} and at EUR {pb:,.2f} {per} "
                            f"in {months[1]} ({c}, {b}).")  # fmt: skip
                    out.append(_entry([c, b], "po", round(jump, 1), "%", part, text, True, strength=abs(jump) / 2))
        return out

    def _fc(self, kinds, facts, sid, parts, prefer=()):
        out = []
        for part in parts:
            number = part.split(":", 1)[1]
            rows = sorted(i for i, f in kinds.get("fc", []) if f.get("part") == part or i.startswith(f"fc:{number}@"))
            if not rows:
                continue
            i, f = rows[-1], facts[rows[-1]]
            change, volume = float(f["change_pct"]), f.get("volume_per_year")
            text = (f"Our forecast {i} expects {int(volume):,} units a year, a change of {change:+.1f} %."
                    if volume else f"Our forecast {i} records a change of {change:+.1f} %.")  # fmt: skip
            out.append(_entry([i], "fc", change, "%", part, text, change > 0, strength=abs(change) / 5,
                              private=not self.shared.get(i, True)))  # fmt: skip
        return out

    def _news(self, kinds, facts, sid, parts, prefer=()):
        out = []
        for i, f in sorted(kinds.get("news", []), reverse=True):
            topic = f.get("topic") or ""
            if f.get("supplier") != sid or topic in SKIP_NEWS:
                continue
            text = f"We have read that {f.get('headline', '').rstrip('.')} ({i})."
            out.append(_entry([i], "news", None, "", sid, text, topic in BUYER_NEWS, strength=0.5, topic=topic,
                              sensitive=topic in SENSITIVE_NEWS, helps_supplier=topic in SUPPLIER_NEWS))  # fmt: skip
        return out

    def _notice(self, kinds, facts, sid, parts, prefer=()):
        """A letter that gives notice, against the notice our contract with it requires."""
        contracts = [
            (i, f) for i, f in kinds.get("ctr", []) if "#" not in i and f.get("supplier") == sid and f.get("days")
        ]
        if not contracts:
            return []
        ctr, cf = max(contracts, key=lambda r: r[1].get("valid_to") or "")
        out = []
        for i, f in sorted(kinds.get("doc", []), reverse=True):
            if f.get("supplier") != sid or not f.get("days") or (f.get("type") or self.letters.get(i)) != "letter":
                continue
            given, required = int(f["days"]), int(cf["days"])
            text = (f"Your letter {i} gives us {given} days of notice, while our agreement {ctr} requires "
                    f"{required} days.")  # fmt: skip
            out.append(_entry([i, ctr], "doc", given, "days", sid, text, given < required,
                              strength=4.0 if given < required else 0.0, required_days=required))  # fmt: skip
        return out

    def _quote(self, kinds, facts, sid, parts, prefer=()):
        """Rival quotes (buyer-private) and its own past quotes; the arena checks a quote of the case,
        so these are cited only when the case's refs or its alternative name them (`case_only`)."""
        out = []
        for i, f in sorted(kinds.get("quote", []), key=lambda r: r[1].get("date") or "", reverse=True):
            part = f.get("part")
            if part not in parts or not f.get("unit_price"):
                continue
            price, per, rival = (
                float(f["unit_price"]),
                _per(f.get("price_unit") or self._price_unit(part)),
                f.get("supplier") != sid,
            )
            text = (f"We hold a quote at EUR {price:,.2f} {per} for this part ({i})." if rival
                    else f"Your own quote of {f.get('date')} was EUR {price:,.2f} {per} ({i}).")  # fmt: skip
            out.append(_entry([i], "quote", price, "EUR", part, text, True, private=rival, case_only=True,
                              strength=2.0, rival=rival))  # fmt: skip
        return out

    # -- helpers -------------------------------------------------------------------------------
    def _cost_supplier(self, i, f):
        return f.get("supplier") or f.get("supplier_id") or self.cost_owner.get(i)

    def _price_unit(self, part):
        return (self.parts.get(part) or {}).get("price_unit") or 1


def _months(a, b):
    ya, ma = map(int, a.split("-")[:2])
    yb, mb = map(int, b.split("-")[:2])
    return (yb - ya) * 12 + (mb - ma)


def _by_kind(facts):
    out = {}
    for i, f in facts.items():
        out.setdefault(i.split(":", 1)[0], []).append((i, f))
    return out


def _entry(ids, kind, figure, unit, about, statement, helps, private=False, **extra):
    return {"ids": list(ids), "kind": kind, "figure": figure, "unit": unit, "about": about, "statement": statement,
            "helps_buyer": bool(helps), "private": bool(private), **extra}  # fmt: skip


def _bank(package):
    key = id(package)
    with _LOCK:  # dossiers are built from several threads at once in the final
        hit = _CACHE.get(key)
        if hit is None or hit[0] is not package:
            hit = _CACHE[key] = (package, _Bank(package))
        return hit[1]


def _case_facts(case):
    facts = (case or {}).get("facts") or {}
    if isinstance(facts, list):
        facts = {f["id"]: f for f in facts if isinstance(f, dict) and f.get("id")}
    return facts


def citable_for(package, supplier_id, part_ids, case=None):
    """Every fact we may cite to `supplier_id` about `part_ids` (see the module doc). Never raises."""
    try:
        bank = _bank(package)
        parts = list(part_ids or [])
        out = bank.entries(supplier_id, parts)
        extra = _case_facts(case)
        if extra:  # hidden cases bring facts of their own, citable there only
            seen = {tuple(e["ids"]) for e in out}
            out += [e for e in bank.entries(supplier_id, parts, {**bank.facts, **extra}, set(extra))
                    if tuple(e["ids"]) not in seen
                    and any(i in extra for i in e["ids"])]  # fmt: skip
        return out
    except Exception as e:
        log.warning("citable_for %s: %s: %s", supplier_id, type(e).__name__, e)
        return []


def arguments(case, supplier_id, dossier=None, package=None, used=(), private=False, price=None):
    """The arguments that help us with this supplier in this case, best first: [{sentence, ids, kind,
    figure, unit, private, strength}]. `used`: IDs cited earlier in the case. Quotes only when the
    case names them (refs, alternative); buyer-private facts only with `private=True`. `price`: the
    supplier's standing unit price (default: the dossier's opening offer); a cost estimate or a quote
    at or above it would argue for the supplier and is left out. Without either nothing is filtered:
    pass the standing price (the current price is no measure in a price increase: P01's should-cost
    132.64 is above the old 126.50 and well below the 138.55 asked)."""
    entries = list((dossier or {}).get("citable") or [])
    if package is not None:
        have = {tuple(e["ids"]) for e in entries}
        entries += [e for e in citable_for(package, supplier_id, case.get("parts") or [], case)
                    if tuple(e["ids"]) not in have]  # fmt: skip
    named = set(case.get("refs") or []) | set(_case_facts(case))
    alt = (case.get("buyer") or {}).get("alternative") or {}
    if alt.get("ref"):
        named.add(alt["ref"])
    used = set(used or ())
    order = ORDER.get(case.get("type"), DEFAULT_ORDER)
    if price is None:
        price = (((dossier or {}).get("opening_offer") or {}).get("terms") or {}).get("unit_price")
    single = len(case.get("parts") or []) == 1  # a bundle's price is not one part's
    out = []
    for e in entries:
        if not e.get("helps_buyer") or any(i in used for i in e["ids"]):
            continue
        if e["kind"] in ("cost", "quote") and single and price and e.get("figure") is not None:
            if float(e["figure"]) >= float(price) * (0.98 if e["kind"] == "cost" else 1.0):
                continue
        if e.get("case_only") and not any(i in named for i in e["ids"]):
            continue
        if e.get("private") and not private:
            continue
        rank = order.index(e["kind"]) if e["kind"] in order else len(order)
        out.append((rank, -float(e.get("strength") or 0.0), e))
    out.sort(key=lambda r: (r[0], r[1]))
    return [{"sentence": e["statement"], "ids": e["ids"], "kind": e["kind"], "figure": e.get("figure"),
             "unit": e.get("unit"), "private": e.get("private", False), "strength": e.get("strength")}
            for _, _, e in out]  # fmt: skip
