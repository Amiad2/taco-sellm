"""The argument bank (sellm/claims.py): every sentence it offers passes the arena's published check
(as sellm/lab/claims.py implements it), it is fast enough for the case overlay, and it only offers
what helps us in the case at hand."""

import json
import time
from pathlib import Path

import pytest

from sellm import claims
from sellm.lab.claims import ClaimChecker

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "package"
CASES = ROOT / "sellm" / "lab" / "cases"


@pytest.fixture(scope="module")
def pkg():
    if not (DATA / "facts.json").is_file():
        pytest.skip("data package not downloaded (uv run arena data)")
    from arena_kit.data import DataPackage

    p = DataPackage(DATA)
    p.lookup("")
    return p


def _case(name):
    return json.loads((CASES / f"{name}.json").read_text(encoding="utf-8"))


def _parts(pkg, sid):
    return sorted({r["part_id"] for r in pkg.query("select part_id from sourcing where supplier_id = ?", (sid,))})


def _checker(pkg, sid, parts, case=None):
    drivers = [s for p in parts for s, _ in claims._bank(pkg).drivers.get(p, [])]
    case = case or {"parts": parts, "suppliers": [sid], "term_options": {}, "buyer": {"index_paths": {}}}
    return ClaimChecker(pkg.facts, case, drivers)


def test_every_statement_of_every_detailed_supplier_is_verified(pkg):
    sups = sorted({r["supplier_id"] for r in pkg.query("select supplier_id from supplier_intel")})
    assert len(sups) == 46
    n, bad, kinds = 0, [], set()
    for sid in sups:
        parts = _parts(pkg, sid)
        checker = _checker(pkg, sid, parts)
        for e in claims.citable_for(pkg, sid, parts):
            n += 1
            kinds.add(e["kind"])
            assert set(e) >= {"ids", "kind", "figure", "unit", "about", "statement", "helps_buyer", "private"}
            results = [r["result"] for r in checker.check(sid, e["statement"], ())]
            if results != ["verified"]:
                bad.append((sid, e["statement"], results))
    assert n > 500 and not bad, bad[:5]
    assert kinds >= {"idx", "cost", "sc_otd", "sc_ppm", "qn", "po", "fc", "news", "doc", "quote"}


def test_fast_enough_for_the_case_overlay(pkg):
    claims.citable_for(pkg, "sup:70110", ["part:310010"])
    t0 = time.perf_counter()
    for sid in ("sup:70110", "sup:70510", "sup:70210", "sup:70140"):
        claims.citable_for(pkg, sid, _parts(pkg, sid))
    assert (time.perf_counter() - t0) / 4 < 0.05


def test_another_plants_estimate_is_never_cited_to_a_supplier(pkg):
    """cost:310012 is Wimbacher's plant (sup:70130); Brandlhuber (sup:70110) gets its own row."""
    ids = [e["ids"][0] for e in claims.citable_for(pkg, "sup:70110", ["part:310012"]) if e["kind"] == "cost"]
    assert ids == ["cost:310012-70110"]


def test_p01_leads_with_the_short_notice_and_the_falling_index(pkg):
    case = _case("P01")
    args = claims.arguments(case, "sup:70110", package=pkg, price=138.55)  # its opening offer
    assert args[0]["kind"] == "doc" and "51 days" in args[0]["sentence"] and "90 days" in args[0]["sentence"]
    assert {"idx", "cost"} <= {a["kind"] for a in args[:4]}
    checker, used = _checker(pkg, "sup:70110", case["parts"], case), set()
    for a in args:
        assert [r["result"] for r in checker.check("sup:70110", a["sentence"], (), used=used)] == ["verified"]


def test_used_ids_private_facts_and_estimates_above_the_price_are_left_out(pkg):
    case = _case("P01")
    first = claims.arguments(case, "sup:70110", package=pkg)[0]
    later = claims.arguments(case, "sup:70110", package=pkg, used=first["ids"])
    assert all(not set(a["ids"]) & set(first["ids"]) for a in later)
    assert not any(a["private"] for a in later)
    cheap = claims.arguments(case, "sup:70110", package=pkg, price=120.0)  # below the should-cost of 132.64
    assert "cost" not in {a["kind"] for a in cheap}


def test_a_hidden_cases_own_facts_are_citable(pkg):
    case = {**_case("P01"), "facts": {"cost:999999-70110": {"part": "part:310010", "supplier": "sup:70110",
                                                             "unit_cost": 1234.5, "price_unit": 1}}}  # fmt: skip
    entries = claims.citable_for(pkg, "sup:70110", case["parts"], case)
    own = [e for e in entries if e["ids"] == ["cost:999999-70110"]]
    assert own and "EUR 1,234.50" in own[0]["statement"]
    checker = _checker(pkg, "sup:70110", case["parts"], case)
    assert [r["result"] for r in checker.check("sup:70110", own[0]["statement"], ())] == ["verified"]


def test_never_raises():
    assert claims.citable_for(None, "sup:1", ["part:1"]) == []
    assert claims.arguments({"parts": [], "buyer": {}}, "sup:1") == []
