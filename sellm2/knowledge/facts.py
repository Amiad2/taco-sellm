# ruff: noqa: E501  (long sentences and messages)
"""Facts we may cite, each as one sentence with our figure next to its IDs (docs/CONTEXT.md section 7).

What the arena taught us about wording (docs/LEARNINGS.md):
- one argument per sentence, the figure in the same sentence;
- integers (ppm, units, days) WITHOUT a thousands separator: "2,376 ppm" came back `contradicted`
  4 of 4 and cost trust; money keeps its comma and two decimals ("EUR 1,608.32");
- only facts about this part and its cost drivers: an index that is not a cost driver of the part, or
  another part's orders, came back `irrelevant` and cost the verified fact next to it its effect;
- each topic counts once per case (a second forecast is `duplicate`).

`candidates(...)` lists every fact for this supplier and case with `helps` (it argues for us) and a
`kind`; the policy (sellm2/policy/arguments.py) decides which one goes into which e-mail.
"""

from dataclasses import dataclass, field

from .brief import case_facts
from .source import source

PPM_HIGH = 1000
OTD_TARGET = 95.0
BUYER_NEWS = {"free_capacity", "short_time_work", "credit_watch", "credit_downgrade", "new_plant"}
SKIP_NEWS = {"noise", "market"}
RECENT_FALL_PCT = 2.0  # a cost driver that fell at least this much from its 12-month peak


@dataclass
class Fact:
    kind: str  # idx | idx6 | idx_recent | cost | sc_otd | sc_ppm | qn | po | fc | news | doc | quote
    ids: list
    sentence: str
    helps: bool
    figure: float | None = None
    strength: float = 0.0
    private: bool = False
    case_only: bool = False  # cited only when the case names it (refs, alternative, facts)
    extra: dict = field(default_factory=dict)

    @property
    def topic(self):
        """What the arena counts once per case: the ID family (a letter and its contract are one)."""
        head = self.ids[0].split(":", 1)[0] if self.ids else self.kind
        return {"ctr": "doc"}.get(head, head)


def _month(m, back):
    y, mo = map(int, m.split("-")[:2])
    n = y * 12 + mo - 1 - back
    return f"{n // 12:04d}-{n % 12 + 1:02d}"


def _months_between(a, b):
    ya, ma = map(int, a.split("-")[:2])
    yb, mb = map(int, b.split("-")[:2])
    return (yb - ya) * 12 + (mb - ma)


def _per(price_unit):
    return "per unit" if not price_unit or int(price_unit) == 1 else f"per {int(price_unit)} units"


def candidates(package, case, sid, brief=None, stated=()):
    """Every fact about `sid` and the case's parts, in no particular order. `stated`: index series the
    supplier itself names as its cost drivers (they are relevant to it). Never raises."""
    try:
        return _candidates(source(package), case or {}, sid, brief, set(stated))
    except Exception:  # an argument less, never a lost move
        return []


def _candidates(src, case, sid, brief, stated):
    parts = list(case.get("parts") or [])
    extra = case_facts(case)
    facts = {**src.facts, **extra}
    by_kind = src.by_kind if not extra else _by_kind(facts)
    series = src.series if not extra else _series(facts)
    data_last = max((rows[-1][0] for rows in series.values() if rows), default="")
    out = []
    out += _idx(src, series, data_last, parts, stated)
    out += _cost(brief, parts, src)
    out += _scorecard(by_kind, sid)
    out += _complaints(by_kind, sid, parts, data_last)
    out += _orders(by_kind, sid, parts, data_last, src)
    out += _forecast(by_kind, facts, parts, src)
    out += _news(by_kind, sid)
    out += _notice(by_kind, sid, src)
    out += _quotes(by_kind, sid, parts, src)
    if extra:  # a hidden case's own facts are citable there
        for f in out:
            if any(i in extra for i in f.ids):
                f.extra["case_fact"] = True
    return out


def _by_kind(facts):
    out = {}
    for ref, f in facts.items():
        if isinstance(f, dict):
            out.setdefault(ref.split(":", 1)[0], []).append((ref, f))
    return out


def _series(facts):
    out = {}
    for ref, f in facts.items():
        if ref.startswith("idx:") and isinstance(f, dict) and f.get("month") and f.get("value") is not None:
            out.setdefault(f["series"], []).append((f["month"], float(f["value"]), ref))
    return {s: sorted(rows) for s, rows in out.items()}


def _idx(src, series, data_last, parts, stated):
    """Per cost driver of the parts (and series the supplier names itself): the change over the last
    12 and 6 months of the series, and the fall from its 12-month peak; each window ends with the
    series and lies within the last 12 months of the data (else the arena calls it irrelevant)."""
    drivers = []
    for part in parts:
        for s, w in src.drivers.get(part, []):
            if s not in [d[0] for d in drivers]:
                drivers.append((s, w))
    for s in sorted(stated):
        if s not in [d[0] for d in drivers]:
            drivers.append((s, 0.1))
    out = []
    for s, weight in drivers:
        rows = series.get(s) or []
        if not rows or _months_between(rows[-1][0], data_last) > 12:
            continue
        by_month = {m: (v, ref) for m, v, ref in rows}
        last, (v_last, ref_last) = rows[-1][0], (rows[-1][1], rows[-1][2])
        change12 = None
        for back, kind in ((12, "idx"), (6, "idx6")):
            start = by_month.get(_month(last, back))
            if not start or not start[0]:
                continue
            change = (v_last / start[0] - 1) * 100
            if back == 12:
                change12 = change
            sentence = f"The index {s} changed {change:+.1f} % from {_month(last, back)} to {last} ({start[1]}, {ref_last})."
            out.append(Fact(kind, [start[1], ref_last], sentence, change < -0.5, round(change, 1),
                            abs(change) * max(weight, 0.05), extra={"series": s, "weight": weight}))  # fmt: skip
        window = [r for r in rows if _months_between(r[0], last) <= 12 and r[0] != last]
        if window and change12 is not None and change12 >= -0.5:
            peak = max(window, key=lambda r: r[1])
            change = (v_last / peak[1] - 1) * 100
            if change <= -RECENT_FALL_PCT:
                sentence = f"The index {s} changed {change:+.1f} % from {peak[0]} to {last} ({peak[2]}, {ref_last})."
                out.append(Fact("idx_recent", [peak[2], ref_last], sentence, True, round(change, 1),
                                abs(change) * max(weight, 0.05), extra={"series": s, "weight": weight}))  # fmt: skip
    return out


def _cost(brief, parts, src):
    """The should-cost the brief matched to this supplier (never another plant's)."""
    out = []
    for part in parts:
        pb = (brief.parts.get(part) if brief else None) if brief else None
        sc = pb.should_cost if pb else None
        if not sc:
            continue
        per = _per(pb.price_unit)
        sentence = f"Our bottom-up estimate of the full cost is EUR {sc['cited']:,.2f} {per} before margin ({sc['ref']})."
        out.append(Fact("cost", [sc["ref"]], sentence, True, sc["cited"], 3.0,
                        extra={"plant_specific": sc["plant_specific"], "part": part}))  # fmt: skip
    return out


def _scorecard(by_kind, sid):
    rows = sorted((r for r in by_kind.get("sc", []) if r[1].get("supplier") == sid), key=lambda r: r[1].get("quarter", ""))
    if not rows:
        return []
    ref, f = rows[-1]
    q, otd, ppm = f.get("quarter"), float(f.get("otd_pct") or 0), float(f.get("ppm") or 0)
    return [
        Fact("sc_otd", [ref], f"Your rolling twelve-month on-time delivery in {q} was {otd:.1f} % ({ref}).",
             otd < OTD_TARGET, otd, max(0.0, OTD_TARGET - otd) / 10),
        Fact("sc_ppm", [ref], f"Your rolling twelve-month quality level in {q} was {ppm:.0f} ppm ({ref}).",
             ppm > PPM_HIGH, ppm, ppm / PPM_HIGH),
    ]  # fmt: skip


def _complaints(by_kind, sid, parts, data_last):
    start = _month(data_last, 12) if data_last else ""
    rows = [(i, f) for i, f in by_kind.get("qn", []) if f.get("supplier") == sid and f.get("part") in parts]
    rows = sorted((r for r in rows if (r[1].get("date") or "")[:7] >= start), key=lambda r: r[1].get("date", ""))[-3:]
    return [
        Fact("qn", [i], f"Complaint {i} of {f['date']} recorded {float(f['ppm']):.0f} ppm.", float(f["ppm"]) >= PPM_HIGH,
             float(f["ppm"]), float(f["ppm"]) / PPM_HIGH / 4)
        for i, f in reversed(rows) if f.get("ppm") is not None
    ]  # fmt: skip


def _orders(by_kind, sid, parts, data_last, src):
    out = []
    start = _month(data_last, 24) if data_last else ""
    for part in parts:
        rows = sorted(
            (r for r in by_kind.get("po", []) if r[1].get("supplier") == sid and r[1].get("part") == part
             and (r[1].get("date") or "")[:7] >= start and r[1].get("unit_price")),
            key=lambda r: (r[1]["date"], r[0]),
        )  # fmt: skip
        if len(rows) < 2:
            continue
        (a, fa), (b, fb) = rows[0], rows[-1]
        pa, pb = float(fa["unit_price"]), float(fb["unit_price"])
        change = (pb / pa - 1) * 100
        per = _per(fa.get("price_unit") or src.price_units.get(part))
        sentence = (f"We ordered from you at EUR {pa:,.2f} {per} in {fa['date'][:7]} and at EUR {pb:,.2f} {per} "
                    f"in {fb['date'][:7]} ({a}, {b}).")  # fmt: skip
        out.append(Fact("po", [a, b], sentence, change > 0.5, round(change, 1), abs(change) / 2))
    return out


def _forecast(by_kind, facts, parts, src):
    out = []
    for part in parts:
        number = part.split(":", 1)[-1]
        rows = sorted(i for i, f in by_kind.get("fc", []) if f.get("part") == part or i.startswith(f"fc:{number}@"))
        if not rows:
            continue
        ref, f = rows[-1], facts[rows[-1]]
        if f.get("change_pct") is None:
            continue
        change, volume = float(f["change_pct"]), f.get("volume_per_year")
        sentence = (f"Our forecast {ref} expects {int(volume):,} units a year, a change of {change:+.1f} %."
                    if volume else f"Our forecast {ref} records a change of {change:+.1f} %.")  # fmt: skip
        out.append(Fact("fc", [ref], sentence, change > 0, change, abs(change) / 5,
                        private=not src.forecast_shared.get(ref, True)))  # fmt: skip
    return out


def _news(by_kind, sid):
    out = []
    for i, f in sorted(by_kind.get("news", []), reverse=True):
        topic = f.get("topic") or ""
        if f.get("supplier") != sid or topic in SKIP_NEWS:
            continue
        sentence = f"We have read that {(f.get('headline') or '').rstrip('.')} ({i})."
        out.append(Fact("news", [i], sentence, topic in BUYER_NEWS, None, 0.5, extra={"topic": topic}))
    return out


def _notice(by_kind, sid, src):
    contracts = [(i, f) for i, f in by_kind.get("ctr", []) if "#" not in i and f.get("supplier") == sid and f.get("days")]
    if not contracts:
        return []
    ctr, cf = max(contracts, key=lambda r: r[1].get("valid_to") or "")
    out = []
    for i, f in sorted(by_kind.get("doc", []), reverse=True):
        if f.get("supplier") != sid or not f.get("days") or (f.get("type") or src.letter_kind.get(i)) != "letter":
            continue
        given, required = int(f["days"]), int(cf["days"])
        sentence = f"Your letter {i} gives us {given} days of notice, while our agreement {ctr} requires {required} days."
        out.append(Fact("doc", [i, ctr], sentence, given < required, given, 4.0 if given < required else 0.0))
    return out


def _quotes(by_kind, sid, parts, src):
    out = []
    for i, f in sorted(by_kind.get("quote", []), key=lambda r: r[1].get("date") or "", reverse=True):
        part = f.get("part")
        if part not in parts or not f.get("unit_price"):
            continue
        price, per, rival = float(f["unit_price"]), _per(f.get("price_unit") or src.price_units.get(part)), f.get("supplier") != sid
        sentence = (f"We hold a quote at EUR {price:,.2f} {per} for this part ({i})." if rival
                    else f"Your own quote of {f.get('date')} was EUR {price:,.2f} {per} ({i}).")  # fmt: skip
        out.append(Fact("quote", [i], sentence, True, price, 2.0, private=rival, case_only=True, extra={"rival": rival}))
    return out
