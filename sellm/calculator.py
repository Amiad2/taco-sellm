# ruff: noqa: E501  (long sentences and messages)
"""The cost calculator: the numbers behind every move, from code and data, never from an LLM.

Our side, exact (the arena's own cost function `arena_kit.cost.total_cost`):
- `packages`    every valid term sheet structure of a case, priced at one unit price, cheapest first
- `levers`      what each option of each negotiable field is worth to us in EUR against a base sheet
- `price_for`   the unit price on another structure that costs us the same (for equivalent offers)

The supplier's side, an estimate with its evidence (`supplier_cost`):
- its full cost where the data package or the case file holds a should-cost of its own plant
  (checked against the floors implied by `C_best` of the played cases: within 1-5 %);
- the direct cost from its own cost breakdown, if it sent one in this negotiation;
- else bounds only: the lowest price it has itself charged for this part in the last twelve months,
  what other approved suppliers charge, what its cost drivers justify since the current price was
  set, and a generic should-cost. For such parts the data package cannot pin the floor (measured:
  the bounds are off by 3-13 %, see docs/LOG.md Sat 21:40), so they are evidence to read and to
  cite, not a target to trust.

`uv run python -m sellm.calculator P08` prints the sheet for a played case.
"""

import itertools
import logging
import re
import threading
from datetime import date

from arena_kit.cost import complete_offer, cost_breakdown, must_haves_ok, supplier_value, total_cost

log = logging.getLogger("sellm")
# The data package is one SQLite connection and the dossiers one cache, shared by every case that is
# played at the same time. Without this lock a lookup failed now and then under ten parallel cases
# and the agent silently fell back to its guess (measured Sat 21:40: 7 of 10 cases, 1-4 times in 30).
LOCK = threading.RLock()

# a deal's worth to the supplier in cash (arena_kit.cost.supplier_value): these terms move it
CASH_FIELDS = ("payment_days", "incoterm", "tooling_eur", "chargeback_eur_per_complaint")
# full cost relative to a German plant (data/package/company.md)
COUNTRY = {"DE": 1.0, "AT": 1.05, "CH": 1.05, "CZ": 0.825, "PL": 0.825, "HU": 0.825, "TR": 0.75, "CN": 0.7}
PROFIT_ROW = re.compile(r"profit|margin|gewinn|marge", re.I)
TOTAL_ROW = re.compile(r"^(unit )?price|^total|^sum", re.I)


# -- our side ------------------------------------------------------------------------------------
def structures(case):
    """Every combination of the negotiable non-price fields over the case's options."""
    fields = [f for f in case["negotiable"] if f != "unit_price"]
    options = [case.get("term_options", {}).get(f) or [None] for f in fields]
    for combo in itertools.product(*options):
        yield {f: v for f, v in zip(fields, combo, strict=True) if v is not None or f == "index_clause"}


def packages(case, standard, price, keep=None):
    """[(C, structure)] of every structure that keeps the must-haves, priced at `price`, cheapest
    first. `keep`: fields fixed to a value, e.g. the supplier's own payment days."""
    out = []
    for s in structures(case):
        s = {**s, **(keep or {})}
        terms = complete_offer(case, {**s, "unit_price": price})
        structure = {f: x for f, x in terms.items() if f != "unit_price"}
        if any(structure == seen for _, seen in out) or not must_haves_ok(case, terms, standard):
            continue
        out.append((total_cost(case, terms, standard), structure))
    return sorted(out, key=lambda row: row[0])


def levers(case, standard, base):
    """What each option of each negotiable field is worth to us, the other terms as in `base` (a
    full term sheet with a price): [{field, option, c, delta}] with delta < 0 a saving in EUR."""
    c_base = total_cost(case, base, standard)
    rows = []
    for field in case["negotiable"]:
        if field == "unit_price":
            continue
        for option in case.get("term_options", {}).get(field) or []:
            terms = complete_offer(case, {**base, field: option})
            ok = must_haves_ok(case, terms, standard)
            c = total_cost(case, terms, standard)
            rows.append({"field": field, "option": option, "c": c, "delta": round(c - c_base, 2), "valid": ok})
    return rows


def price_for(case, standard, structure, cost):
    """The unit price at which `structure` costs us `cost` (C is linear in the price)."""
    c0 = total_cost(case, {**structure, "unit_price": 0.0}, standard)
    c1 = total_cost(case, {**structure, "unit_price": 1.0}, standard)
    return (cost - c0) / (c1 - c0) if c1 > c0 else None


# -- the supplier's side -------------------------------------------------------------------------
def read_breakdown(text):
    """A supplier's cost breakdown (the XLSX it attaches when asked and open enough), as text:
    {"elements": {name: EUR per unit}, "direct": sum without the profit row, "profit": that row}."""
    if not text or "breakdown" not in text.lower():
        return None
    elements, profit = {}, None
    for line in text.splitlines():
        cells = [c.strip() for c in line.split("|")]
        if len(cells) < 2 or TOTAL_ROW.search(cells[0]):
            continue
        try:
            value = float(cells[1].replace(",", "."))
        except ValueError:
            continue
        if PROFIT_ROW.search(cells[0]):
            profit = value
        else:
            elements[cells[0]] = value
    if not elements:
        return None
    return {"elements": elements, "direct": round(sum(elements.values()), 4), "profit": profit}


def _query(package, sql, args):
    try:
        with LOCK:
            return package.query(sql, args)
    except Exception as e:  # a table or a column less in a later data release: an evidence less, and said so
        log.warning("calculator: a lookup failed (%s: %s) - %s", type(e).__name__, e, sql[:60])
        return []


def _number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def supplier_cost(case, sid, events=None, package=None):
    """What we know about this supplier's cost of the case's part.

    Returns {"cost": {...} or None, "evidence": [...]}. `cost` is set only where we hold an estimate
    of its own cost: {"value", "low", "high", "ref", "basis"}. Every evidence row is
    {"kind", "value", "ref", "note"} with `value` in EUR per price unit, comparable to its price.
    """
    with LOCK:
        return _supplier_cost(case, sid, events, package)


def _supplier_cost(case, sid, events, package):
    evidence, cost = [], None
    parts = case.get("parts") or []
    part = parts[0] if len(parts) == 1 else None  # a kit's unit price is not a part's price
    number = part.split(":", 1)[1] if part else None

    def own(fact):
        return fact.get("supplier") in (None, sid) and fact.get("supplier_id") in (None, sid)

    for ref, fact in (case.get("facts") or {}).items():  # hidden cases carry facts of their own
        if ref.startswith("cost:") and fact.get("unit_cost") and part and fact.get("part") in (part, number, None):
            if own(fact) and cost is None:
                value = float(fact["unit_cost"])
                cost = {
                    "value": value,
                    "low": value * 0.95,
                    "high": value * 1.05,
                    "ref": ref,
                    "basis": "should-cost in the case file",
                }
                evidence.append({"kind": "should_cost_case", "value": value, "ref": ref, "note": "case fact"})
    if package and part:
        for r in _query(
            package,
            "select id, supplier_id, cost_base, unit_cost, confidence_pct from should_cost where part_id = ?",
            (part,),
        ):
            value, conf = _number(r.get("unit_cost")), (_number(r.get("confidence_pct")) or 10) / 100
            if value is None:
                continue
            if r.get("supplier_id") == sid:
                evidence.append(
                    {"kind": "should_cost_own", "value": value, "ref": r["id"], "note": f"its own plant, +-{conf:.0%}"}
                )
                if cost is None:
                    cost = {
                        "value": value,
                        "low": value * (1 - conf),
                        "high": value * (1 + conf),
                        "ref": r["id"],
                        "basis": "should-cost of its own plant",
                    }
            elif not r.get("supplier_id"):
                country = (_query(package, "select country from suppliers where id = ?", (sid,)) or [{}])[0].get(
                    "country"
                )
                factor = COUNTRY.get(country, 1.0)
                evidence.append(
                    {
                        "kind": "should_cost_generic",
                        "value": round(value * factor, 2),
                        "ref": r["id"],
                        "note": f"generic {r.get('cost_base')} estimate x {factor} ({country}), +-15 % and more",
                    }
                )
        prices = _query(
            package,
            "select supplier_id, valid_from, valid_to, price, basis from price_conditions where part_id = ? order by valid_from",
            (part,),
        )
        newest = max((r["valid_from"] for r in prices if r.get("valid_from")), default=None)
        if newest:
            try:
                since = date.fromisoformat(newest).replace(year=date.fromisoformat(newest).year - 1).isoformat()
            except ValueError:
                since = newest
            recent = [
                r for r in prices if _number(r.get("price")) and (not r.get("valid_to") or r["valid_to"] >= since)
            ]
            mine = [r for r in recent if r["supplier_id"] == sid]
            below = any(
                "below full cost" in (r.get("note") or "")
                for r in _query(
                    package, "select note from negotiation_history where part_id = ? and supplier_id = ?", (part, sid)
                )
            )
            if mine:
                low = min(mine, key=lambda r: float(r["price"]))
                note = f"its lowest price for this part since {since} (from {low['valid_from']})" + (
                    "; history notes say it sold below full cost" if below else ""
                )
                evidence.append(
                    {
                        "kind": "own_low_12m",
                        "value": float(low["price"]),
                        "ref": None,
                        "note": note,
                        "below_cost": below,
                    }
                )
            others = [r for r in recent if r["supplier_id"] != sid]
            if others:
                low = min(others, key=lambda r: float(r["price"]))
                evidence.append(
                    {
                        "kind": "rival_low_12m",
                        "value": float(low["price"]),
                        "ref": None,
                        "note": f"{low['supplier_id']} charged this from {low['valid_from']}",
                    }
                )
        current = _number(case["buyer"].get("current_unit_price"))
        drivers = _query(package, "select series_id, weight from cost_drivers where part_id = ?", (part,))
        if current and drivers:
            move, refs = 0.0, []
            for d in drivers:
                try:
                    ids = package.ids(f"idx:{d['series_id']}@")
                    if len(ids) >= 13:
                        move += float(d["weight"]) * (
                            package.lookup(ids[-1])["value"] / package.lookup(ids[-13])["value"] - 1
                        )
                        refs += [ids[-13], ids[-1]]
                except Exception:
                    continue
            if refs:
                evidence.append(
                    {
                        "kind": "index_justified",
                        "value": round(current * (1 + move), 2),
                        "ref": None,
                        "note": f"the current price moved with its cost drivers over twelve months ({move:+.1%})",
                        "refs": refs,
                    }
                )
    for message in events or []:  # its own breakdown beats every estimate of ours
        for att in message.get("attachments") or []:
            found = read_breakdown(att.get("text"))
            if found:
                evidence.append(
                    {
                        "kind": "breakdown",
                        "value": found["direct"],
                        "ref": att.get("attachment_id"),
                        "note": f"its own cost breakdown without overhead and profit ({found['profit']})",
                    }
                )
                if cost is None or cost["basis"] != "its own cost breakdown":
                    high = found["direct"] + (found["profit"] or 0) * 0.5
                    cost = {
                        "value": found["direct"],
                        "low": found["direct"],
                        "high": high,
                        "ref": att.get("attachment_id"),
                        "basis": "its own cost breakdown",
                    }
    return {"cost": cost, "evidence": evidence}


def recent_low(found):
    """The lowest price it has itself charged for this part in the last twelve months, unless the
    history says it sold below full cost then: a price it can go back to."""
    rows = [e for e in found["evidence"] if e["kind"] == "own_low_12m" and not e.get("below_cost")]
    return rows[0]["value"] if rows else None


# -- the sheet -----------------------------------------------------------------------------------
def sheet(case, threads, package=None, estimate_rate=0.08):
    """The calculator's view of a case as text: the opening, the levers, the supplier's cost."""
    from arena_kit.docs import quote_terms, standard_terms

    b = case["buyer"]
    lines = [
        f"{case['case_id']}  {case['type']} / {b.get('category_goal')}  need {b['need_per_year']} a year, horizon {b['horizon_years']} years"
    ]
    for sid, events in threads.items():
        opening = next((m for m in events if m.get("term_sheets")), None)
        if not opening:
            continue
        std = {}
        for att in opening.get("attachments") or []:
            if att.get("name", "").startswith("quote") and att.get("text"):
                std = quote_terms(att["text"]).get("standard", {})
        std = {**std, **standard_terms(events)}
        its = complete_offer(
            case, {**std, **{k: v for k, v in opening["term_sheets"][0]["terms"].items() if v is not None}}
        )
        if its.get("unit_price") is None:
            continue
        parts = cost_breakdown(case, its, std)
        lines.append(
            f"\n{sid}: opening {its['unit_price']} -> C {sum(parts.values()):,.0f}  ({', '.join(f'{k} {v:,.0f}' for k, v in parts.items() if abs(v) >= 1)})"
        )
        lines.append("  levers at its price (EUR against its own terms, - is a saving):")
        for row in levers(case, std, its):
            if abs(row["delta"]) >= 1 or not row["valid"]:
                option = (
                    row["option"]
                    if not isinstance(row["option"], dict)
                    else f"clause {row['option'].get('series')} deadband {row['option'].get('deadband_pct')}"
                )
                lines.append(
                    f"    {row['field']:>30} = {str(option):<28} {row['delta']:>+12,.0f}"
                    + ("" if row["valid"] else "   breaks a must-have")
                )
        best = packages(case, std, its["unit_price"])
        if best:
            lines.append(f"  cheapest package at its price: C {best[0][0]:,.0f}  {best[0][1]}")
        found = supplier_cost(case, sid, events, package)
        sup = {"standard": {**its, **std}, "interest_rate": estimate_rate}
        lines.append(
            f"  worth of its opening to it: {supplier_value(case, its, sup):.2f} per unit (at {estimate_rate:.0%} cost of money)"
        )
        if found["cost"]:
            c = found["cost"]
            lines.append(
                f"  its cost: {c['value']:.2f} ({c['low']:.2f}-{c['high']:.2f}), {c['basis']} [{c['ref']}] = {c['value'] / its['unit_price']:.3f} of its price"
            )
        else:
            lines.append("  its cost: no estimate of its own plant - bounds only:")
        for e in found["evidence"]:
            lines.append(
                f"    {e['kind']:>20} {e['value']:>10.2f}  ({e['value'] / its['unit_price']:.3f} of its price)  {e['note']}"
                + (f" [{e['ref']}]" if e.get("ref") else "")
            )
    return "\n".join(lines)


def main(argv=None):
    import glob
    import json
    import os
    import sys

    from arena_kit.cli import load_env
    from arena_kit.data import DataPackage

    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print(__doc__)
        return 2
    load_env()
    data = os.environ.get("ARENA_DATA", "data/package")
    package = DataPackage(data) if os.path.isdir(data) else None
    for name in args:
        files = sorted(glob.glob(f"runs/*/{name.split(':')[-1]}/*.json"))
        if not files:
            print(f"{name}: no saved session in runs/ (play the case once, then scripts/pull-runs)")
            continue
        record = json.loads(open(files[-1], encoding="utf-8").read())
        threads = {s: t["messages"][:1] for s, t in record["threads"].items()}
        print(sheet(record["case"], threads, package))
        result = (record.get("state") or {}).get("result") or {}
        if result.get("c_best"):
            print(
                f"\n  known from play: C_open {result['c_open']:,.0f}  C_best {result['c_best']:,.0f}"
                + (f"  (C_alt {result['c_alt']:,.0f})" if result.get("c_alt") else "")
            )
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
