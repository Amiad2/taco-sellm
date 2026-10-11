"""The rewritten data layer: it must know what the team's measured agent knew (the old dossiers serve
as the oracle here, read-only), and every fact it may cite must check out against facts.json."""

import re
import time

import pytest

from sellm2.knowledge import build, case_facts, source
from sellm2.knowledge.facts import candidates

from .conftest import records


def _parts(pkg, sid):
    return sorted({r["part_id"] for r in pkg.query("select part_id from sourcing where supplier_id = ?", (sid,))})


def _suppliers(pkg):
    return sorted({r["supplier_id"] for r in pkg.query("select supplier_id from supplier_intel")})


def _old(pkg, sid, parts, case, threads):
    intel = pytest.importorskip("sellm.intel")
    d = intel.dossier(sid, parts, case=case, opening=threads, package=pkg)
    sc = {p: ((d["parts"][p]["should_cost"] or {}).get("id"), (d["parts"][p]["should_cost"] or {}).get("plant_specific")) for p in parts}
    return {
        "coverage": d["coverage"],
        "cash": d["economics"]["cash_pressure"] if d["coverage"] == "full" else None,
        "arche": d["economics"]["archetype"] if d["coverage"] == "full" else None,
        "rate": d["economics"]["cost_of_money"] if d["coverage"] == "full" else None,
        "signals": {s["kind"]: s["strength"] for s in d["signals"]},
        "contact": (d.get("contact") or {}).get("name") if threads else None,
        "sc": {p: v if v[0] else (None, None) for p, v in sc.items()},
    }


def _new(pkg, sid, parts, case, threads):
    b = build(pkg, sid, parts, case, threads)
    return {
        "coverage": b.coverage,
        "cash": b.cash_pressure if b.coverage == "full" else None,
        "arche": b.archetype if b.coverage == "full" else None,
        "rate": b.cost_of_money if b.coverage == "full" else None,
        "signals": b.signals,
        "contact": b.contact if threads else None,
        "sc": {p: ((b.parts[p].should_cost or {}).get("ref"), (b.parts[p].should_cost or {}).get("plant_specific")) for p in parts},
    }


def test_briefs_match_the_measured_dossiers_for_every_detailed_supplier_and_part(pkg):
    bad = []
    for sid in _suppliers(pkg):
        for part in _parts(pkg, sid):
            case = {"case_id": "X", "parts": [part], "suppliers": [sid], "buyer": {}}
            old, new = _old(pkg, sid, [part], case, None), _new(pkg, sid, [part], case, None)
            if old != new:
                bad.append((sid, part, {k: (old[k], new[k]) for k in old if old[k] != new[k]}))
    assert not bad, bad[:3]


def test_briefs_match_on_every_played_case_with_its_openings(pkg):
    seen, bad = set(), []
    for r in records():
        if r["case_id"] in seen:
            continue
        seen.add(r["case_id"])
        case = r["case"]
        threads = {s: t["messages"][:1] for s, t in r["threads"].items()}
        for sid in threads:
            old, new = _old(pkg, sid, case.get("parts") or [], case, threads), _new(pkg, sid, case.get("parts") or [], case, threads)
            if old != new:
                bad.append((r["case_id"], sid, {k: (old[k], new[k]) for k in old if old[k] != new[k]}))
    assert len(seen) >= 10 and not bad, bad[:3]


def test_every_fact_of_every_detailed_supplier_is_verified_by_the_claim_checker(pkg):
    ClaimChecker = pytest.importorskip("sellm.lab.claims").ClaimChecker
    src = source(pkg)
    n, bad, kinds = 0, [], set()
    for sid in _suppliers(pkg):
        parts = _parts(pkg, sid)
        drivers = [s for p in parts for s, _ in src.drivers.get(p, [])]
        case = {"parts": parts, "suppliers": [sid], "term_options": {}, "buyer": {"index_paths": {}}}
        checker = ClaimChecker(pkg.facts, case, drivers)
        for f in candidates(pkg, case, sid, build(pkg, sid, parts, case)):
            n += 1
            kinds.add(f.kind)
            result = [x["result"] for x in checker.check(sid, f.sentence, ())]
            if result != ["verified"]:
                bad.append((sid, f.sentence, result))
    assert n > 800 and not bad, bad[:5]
    assert kinds >= {"idx", "idx6", "idx_recent", "cost", "sc_otd", "sc_ppm", "qn", "po", "fc", "news", "doc", "quote"}


def test_no_integer_is_written_with_a_thousands_separator(pkg):
    """'2,376 ppm' came back contradicted 4 of 4 in the arena; '2376 ppm' verified."""
    for sid in _suppliers(pkg):
        parts = _parts(pkg, sid)
        case = {"parts": parts, "suppliers": [sid]}
        for f in candidates(pkg, case, sid, build(pkg, sid, parts, case)):
            assert not re.search(r"\d,\d{3}\s*(ppm|days)", f.sentence), f.sentence


def test_another_plants_estimate_is_never_this_suppliers_cost(pkg):
    """cost:310012 is Wimbacher's plant (sup:70130); Brandlhuber's is cost:310012-70110."""
    assert build(pkg, "sup:70110", ["part:310012"]).parts["part:310012"].should_cost["ref"] == "cost:310012-70110"
    assert build(pkg, "sup:70130", ["part:310012"]).parts["part:310012"].should_cost["ref"] == "cost:310012"


def test_a_hidden_cases_own_facts_are_known_and_citable(pkg):
    case = {
        "case_id": "H1", "parts": ["part:310010"], "suppliers": ["sup:79999"], "buyer": {},
        "facts": [{"id": "cost:H1-1", "part": "part:310010", "unit_cost": 99.5, "supplier": "sup:79999"},
                  {"id": "news:H1-2", "supplier": "sup:79999", "topic": "credit_watch", "headline": "Stranger GmbH on credit watch"}],
    }  # fmt: skip
    assert set(case_facts(case)) == {"cost:H1-1", "news:H1-2"}
    b = build(pkg, "sup:79999", ["part:310010"], case)
    assert b.coverage == "case_only" and b.parts["part:310010"].should_cost["ref"] == "cost:H1-1"
    assert b.signal("cash_short") >= 1
    facts = candidates(pkg, case, "sup:79999", b)
    assert any(f.kind == "cost" and f.ids == ["cost:H1-1"] and "99.50" in f.sentence for f in facts)
    assert any(f.kind == "news" and f.ids == ["news:H1-2"] for f in facts)


def test_a_sunday_style_release_letter_lands_in_its_supplier(pkg):
    """The Sunday release adds rows to the package's ID index (not to SQLite): they must be read."""
    src = source(pkg)
    before = build(pkg, "sup:70160", _parts(pkg, "sup:70160"))
    fake = {"doc:20261011-70160-X": {"table": "documents", "root": "release", "supplier_id": "sup:70160", "asked_pct": None}}
    src.__dict__["released"] = {**src.released, **fake}
    src_text = src.text
    src.text = lambda ref: "Could you pay our invoices within 10 days? The bank is watching." if ref in fake else src_text(ref)
    try:
        after = build(pkg, "sup:70160", _parts(pkg, "sup:70160"))
    finally:
        src.__dict__.pop("released", None)
        src.text = src_text
    assert after.signal("cash_short") > before.signal("cash_short")


@pytest.mark.parametrize("junk", [None, {}, {"parts": None}, {"facts": "x"}, {"facts": [1, 2]}, {"buyer": {"alternative": {"kind": "quote"}}}])
def test_odd_input_never_raises(pkg, junk):
    b = build(pkg, "sup:70110", ["part:310010"], junk, {"sup:70110": "nonsense"})
    assert b.coverage == "full"
    assert isinstance(candidates(pkg, junk, "sup:70110", b), list)
    assert build(None, "sup:1", ["part:1"]).coverage == "case_only"


def test_fast_enough_for_a_wave(pkg):
    build(pkg, "sup:70110", ["part:310010"])
    t0 = time.perf_counter()
    for sid in _suppliers(pkg):
        build(pkg, sid, _parts(pkg, sid)[:1])
    assert (time.perf_counter() - t0) / 46 < 0.1
