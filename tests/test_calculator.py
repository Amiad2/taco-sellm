"""The cost calculator (`sellm/calculator.py`): our side is exact, the supplier's side is honest
about what it knows. Checked on the real sessions saved in runs/ (no network, no LLM)."""

import glob
import json
from pathlib import Path

import pytest

from arena_kit.cost import must_haves_ok, total_cost
from sellm import calculator
from sellm.negotiator import Thread

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "package"

BREAKDOWN = (
    "[Cost breakdown]\nElement | EUR per unit | Share of price\n"
    "BAR-14021 (material / cost driver) | 5.56 | =B2/B6\nWAGES-METAL (material / cost driver) | 4.39 | =B3/B6\n"
    "conversion (machine-hour rate x time) | 2.81 | =B4/B6\noverhead and profit | 2.84 | =B5/B6\n"
    "Unit price | =SUM(B2:B5) | =SUM(C2:C5)"
)


def record(case_id):
    files = sorted(glob.glob(str(ROOT / "runs" / "*" / case_id / "*.json")))
    if not files:
        pytest.skip(f"no saved session of {case_id}")
    return json.loads(Path(files[-1]).read_text(encoding="utf-8"))


def opening(case_id):
    rec = record(case_id)
    case = rec["case"]
    sid = case["suppliers"][0]
    view = Thread(case, sid, rec["threads"][sid]["messages"][:1])
    return case, sid, view, view.filled(view.opening["term_sheets"][0]["terms"])


@pytest.fixture(scope="module")
def package():
    if not DATA.is_dir():
        return None
    from arena_kit.data import DataPackage

    return DataPackage(DATA)


def test_packages_are_valid_and_sorted():
    for case_id in ("P04", "P08", "P10", "D02"):
        case, _, view, its = opening(case_id)
        ranked = calculator.packages(case, view.std, its["unit_price"])
        assert ranked and [c for c, _ in ranked] == sorted(c for c, _ in ranked)
        for cost, structure in ranked:
            terms = {**structure, "unit_price": its["unit_price"]}
            assert set(terms) == set(case["negotiable"])
            assert must_haves_ok(case, terms, view.std)
            assert cost == total_cost(case, terms, view.std)


def test_a_lever_is_the_difference_in_our_cost():
    case, _, view, its = opening("P04")
    rows = {(r["field"], r["option"]): r for r in calculator.levers(case, view.std, its)}
    later = rows[("payment_days", 90)]
    assert later["delta"] < 0, "paying later saves us interest"
    assert later["delta"] == pytest.approx(
        total_cost(case, {**its, "payment_days": 90}, view.std) - total_cost(case, its, view.std)
    )
    assert rows[("payment_days", 14)]["delta"] > 0


def test_the_cheapest_package_depends_on_the_price_we_expect():
    """At the opening price a second year can cost more than the fallback; at the price a deal can
    end at it does not. The first ask is built for the second."""
    case, _, view, its = opening("P08")
    at_opening = calculator.packages(case, view.std, its["unit_price"])[0][1]
    at_target = calculator.packages(case, view.std, its["unit_price"] * 0.88)[0][1]
    assert at_opening["contract_months"] == 12
    assert at_target["contract_months"] >= 24


def test_price_for_gives_the_same_cost_on_another_structure():
    case, _, view, its = opening("D02")
    other = {f: x for f, x in {**its, "payment_days": 60}.items() if f != "unit_price"}
    cost = total_cost(case, its, view.std)
    price = calculator.price_for(case, view.std, other, cost)
    assert price > its["unit_price"], "later payment is worth a higher price to us"
    assert total_cost(case, {**other, "unit_price": price}, view.std) == pytest.approx(cost, abs=0.5)


def test_a_cost_breakdown_is_read():
    found = calculator.read_breakdown(BREAKDOWN)
    assert found["direct"] == pytest.approx(12.76) and found["profit"] == pytest.approx(2.84)
    assert len(found["elements"]) == 3
    assert calculator.read_breakdown("Quotation\nUnit price | 15.60") is None
    case, sid, view, _ = opening("D02")
    events = [
        *view.events,
        {
            "from": "sales",
            "attachments": [{"attachment_id": "att:x", "name": "cost-breakdown.xlsx", "text": BREAKDOWN}],
        },
    ]
    found = calculator.supplier_cost(case, sid, events)
    assert found["cost"]["basis"] == "its own cost breakdown" and found["cost"]["value"] == pytest.approx(12.76)


def test_supplier_cost_says_what_it_knows(package):
    if package is None:
        pytest.skip("no data package")
    case, sid, _, its = opening("P01")
    found = calculator.supplier_cost(case, sid, None, package)
    assert (
        found["cost"]["ref"] == "cost:310010" and found["cost"]["low"] < found["cost"]["value"] < found["cost"]["high"]
    )
    assert calculator.recent_low(found) is None, "its history says it sold below full cost: no price to go back to"
    case, sid, _, its = opening("P08")
    found = calculator.supplier_cost(case, sid, None, package)
    assert found["cost"] is None, "no should-cost of its own plant: bounds only"
    kinds = {e["kind"] for e in found["evidence"]}
    assert {"own_low_12m", "rival_low_12m", "index_justified"} <= kinds
    assert calculator.recent_low(found) < its["unit_price"]


def test_a_kit_of_several_parts_gets_no_part_evidence(package):
    case, sid, _, _ = opening("P07")
    assert calculator.supplier_cost(case, sid, None, package) == {"cost": None, "evidence": []}


def test_the_sheet_prints(package):
    rec = record("P04")
    text = calculator.sheet(rec["case"], {s: t["messages"][:1] for s, t in rec["threads"].items()}, package)
    assert "levers at its price" in text and "payment_days" in text
