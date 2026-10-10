"""sellm.intel: the dossier contract (docs/PLAN.md section 10), the builder and the case overlay."""

import time
from pathlib import Path

import pytest
from intel_fixture import make_package

from arena_kit.data import DataPackage
from sellm.intel import SCHEMA_VERSION, dossier
from sellm.intel.extract import Source, body
from sellm.intel.schema import CORE_FIELDS, SIGNAL_KINDS, TOP_KEYS, validate

REAL = Path(__file__).resolve().parents[1] / "data" / "package"


@pytest.fixture
def fixture_pkg(tmp_path):
    return DataPackage(make_package(tmp_path / "pkg"))


@pytest.fixture
def release_pkg(tmp_path):
    return DataPackage(make_package(tmp_path / "pkg", release=True))


@pytest.fixture(scope="module")
def real_pkg():
    if not (REAL / "world.sqlite").is_file():
        pytest.skip("data package not downloaded (uv run arena data)")
    return DataPackage(REAL)


def test_the_stub_carries_every_field_of_the_contract():
    d = dossier("sup:70130", ["part:310011"])
    assert set(d) == set(TOP_KEYS) and set(CORE_FIELDS) <= set(d)
    assert d["schema_version"] == SCHEMA_VERSION == 1
    assert d["supplier_id"] == "sup:70130" and d["coverage"] == "case_only"
    assert isinstance(d["economics"]["cost_of_money"], float) and 0 < d["economics"]["cost_of_money"] <= 1
    assert d["economics"]["cash_pressure"] in ("low", "medium", "high")
    assert isinstance(d["signals"], list) and isinstance(d["citable"], list)
    assert set(d["parts"]) == {"part:310011"} and d["parts"]["part:310011"]["drivers"] == []
    assert "informal_costing" in SIGNAL_KINDS


@pytest.mark.parametrize(
    "sid, parts", [(None, None), (123, "part:X"), ("", [None, 5]), ("sup:1", 7), ("sup:1", {"a": 1})]
)
def test_dossier_never_raises(sid, parts):
    d = dossier(sid, parts, case={"weird": True}, opening=["not", "messages"])
    assert d["schema_version"] == 1 and isinstance(d["parts"], dict)


def test_the_stub_is_fast():
    t0 = time.perf_counter()
    for _ in range(100):
        dossier("sup:70130", ["part:310011", "part:310012"])
    assert (time.perf_counter() - t0) / 100 < 0.005


def test_the_stub_is_valid():
    assert validate(dossier("sup:70130", ["part:310011"])) == []


def _broken(change):
    d = dossier("sup:70130", ["part:310011"])
    change(d)
    return validate(d)


@pytest.mark.parametrize(
    "change, needle",
    [
        (lambda d: d.pop("signals"), "missing"),
        (lambda d: d.update(extra=1), "unknown"),
        (lambda d: d.update(schema_version=2), "schema_version"),
        (lambda d: d.update(coverage="partial"), "coverage"),
        (lambda d: d["economics"].update(cost_of_money=0.0), "cost_of_money"),
        (lambda d: d["economics"].update(cash_pressure="severe"), "cash_pressure"),
        (lambda d: d["economics"].update(archetype="pirate"), "archetype"),
        (
            lambda d: d["signals"].append({"kind": "gossip", "strength": 1, "evidence": ["doc:1"], "excerpt": ""}),
            "kind",
        ),
        (
            lambda d: d["signals"].append({"kind": "cash_short", "strength": 4, "evidence": ["doc:1"], "excerpt": ""}),
            "strength",
        ),
        (
            lambda d: d["signals"].append({"kind": "cash_short", "strength": 1, "evidence": ["b", "a"], "excerpt": ""}),
            "sorted",
        ),
        (
            lambda d: d["parts"]["part:310011"].update(floor_estimate={"value": 5, "low": 6, "high": 7, "basis": "x"}),
            "band",
        ),
        (
            lambda d: d["parts"]["part:310011"]["alternatives"].append({"supplier_id": "sup:1", "private": False}),
            "private",
        ),
        (lambda d: d["standard_terms"].update(source="gossip"), "source"),
        (lambda d: d["economics"].update(we_pay_late_days=float("nan")), "finite"),
    ],
)
def test_the_validator_reports_every_breach(change, needle):
    errors = _broken(change)
    assert errors and any(needle in e for e in errors), errors


def test_extract_reads_the_package(fixture_pkg):
    src = Source(fixture_pkg)
    assert src.detailed_ids() == ["sup:1", "sup:2", "sup:3"]
    two = src.supplier("sup:2")
    assert two["owner_type"] == "founder" and two["skonto_pct"] == 2 and two["turnover_eur"] is None
    docs = src.documents("sup:1")
    assert [d["id"] for d in docs] == ["doc:1", "doc:2", "doc:3"]
    assert docs[0]["text"].startswith("Call with the managing director") and "# " not in docs[0]["text"]
    assert [n["id"] for n in src.market_news()] == ["news:3"]
    assert src.release_rows == {} and src.version() == "9.9.9"
    assert body("# T\n\nemail - 2026-01-01 - X\n\nHello.") == "Hello."


def test_extract_picks_up_the_sunday_release(release_pkg):
    src = Source(release_pkg)
    docs = src.documents("sup:3")
    assert [d["id"] for d in docs] == ["doc:R1"] and docs[0]["text"] == "We are on allocation for the rest of the year."
    assert [n["id"] for n in src.news("sup:3")] == ["news:R1"]
    assert [n["id"] for n in src.market_news()] == ["news:3"]


def test_extract_reads_every_row_of_the_real_package(real_pkg):
    src = Source(real_pkg)
    assert len(src.detailed_ids()) == 46
    assert len(src.q("SELECT id FROM po_lines")) == 5400
    assert len(src.documents("sup:70130")) == 7 and len(src.market_news()) == 7
