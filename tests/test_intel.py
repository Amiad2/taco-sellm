"""sellm.intel: the dossier contract (docs/PLAN.md section 10), the builder and the case overlay."""

import json
import time
from pathlib import Path

import pytest
from intel_fixture import make_package

from arena_kit.data import DataPackage
from sellm.intel import SCHEMA_VERSION, dossier, signals
from sellm.intel.__main__ import main as cli
from sellm.intel.assemble import build_supplier
from sellm.intel.build import DOSSIERS, build_all, build_one, write_all
from sellm.intel.extract import Source, body
from sellm.intel.schema import CORE_FIELDS, SIGNAL_KINDS, TOP_KEYS, validate
from sellm.intel.serialize import dumps

REAL = Path(__file__).resolve().parents[1] / "data" / "package"


@pytest.fixture
def fixture_pkg(tmp_path):
    return DataPackage(make_package(tmp_path / "pkg"))


@pytest.fixture
def release_pkg(tmp_path):
    return DataPackage(make_package(tmp_path / "pkg-release", release=True))


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
    assert src.release_rows == {} and src.version == "9.9.9"
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


def test_parts_follow_the_rules(fixture_pkg):
    src = Source(fixture_pkg)
    a = build_supplier(src, "sup:1")["parts"]["part:A"]
    assert a["current_price"]["price"] == 102.0 and a["sourcing"]["quota_pct"] == 100
    assert a["should_cost"]["id"] == "cost:A" and a["should_cost"]["plant_specific"] is True
    assert a["floor_estimate"] == {
        "value": 101.0,
        "low": 95.95,
        "high": 106.05,
        "basis": "plant-specific should-cost cost:A",
    }
    assert a["price_to_should_cost"] == 1.0099
    h = a["history"]
    assert (h["mean_asked_pct"], h["mean_settled_pct"], h["mean_give_pct"], h["below_full_cost"]) == (
        2.5,
        -0.25,
        2.75,
        True,
    )
    s1, s2 = a["drivers"]
    assert (s1["series"], s1["change_12m_pct"], s1["change_6m_pct"]) == ("S1", 6.0, 1.92)
    assert s1["ids_12m"] == ["idx:S1@2025-08", "idx:S1@2026-08"]
    assert (s2["series"], s2["change_12m_pct"], s2["change_6m_pct"]) == ("S2", -5.0, -3.06)
    assert a["forecast"] == {
        "id": "fc:A@2026-06",
        "snapshot_month": "2026-06",
        "volume_next_12m": 1000,
        "change_pct": 5.0,
        "volume_per_year": 1000,
    }
    assert [(x["supplier_id"], x["quote_id"], x["unit_price"], x["private"]) for x in a["alternatives"]] == [
        ("sup:2", "quote:3", 99.0, True)
    ]


def test_a_plant_estimate_is_never_another_suppliers(fixture_pkg):
    src = Source(fixture_pkg)
    b1 = build_supplier(src, "sup:1")["parts"]["part:B"]
    assert b1["should_cost"]["id"] == "cost:B-1" and b1["price_to_should_cost"] == 1.0204
    assert build_supplier(src, "sup:2")["parts"]["part:B"]["should_cost"]["id"] == "cost:B"
    c = build_supplier(src, "sup:3")["parts"]["part:C"]
    assert c["should_cost"]["plant_specific"] is False
    assert c["floor_estimate"] == {
        "value": 80.0,
        "low": 68.0,
        "high": 92.0,
        "basis": "generic DE should-cost cost:C x 1.0 (DE)",
    }


def test_the_supplier_sections(fixture_pkg):
    src = Source(fixture_pkg)
    one, two = build_supplier(src, "sup:1"), build_supplier(src, "sup:2")
    assert validate(one) == [] and validate(two) == []
    assert one["coverage"] == "full" and one["built_from"]["package"] == "9.9.9"
    assert one["economics"]["our_spend_eur"] == {"FY2025": 1000000.0, "FY2026": 1289395.92}
    assert one["economics"]["our_share_of_turnover_pct"] == 6.68 and one["economics"]["we_pay_late_days"] == 3.0
    assert two["identity"]["turnover_estimated"] is True and two["economics"]["our_share_of_turnover_pct"] == 10.0
    assert two["economics"]["discount_taken_share_pct"] == 50.0
    perf = one["performance"]
    assert perf["latest"]["id"] == "sc:1@2026Q3" and perf["mean_4q"]["otd_pct"] == 87.83 and perf["trend"] == "better"
    assert (perf["qn_12m"], perf["qn_ids_12m"]) == (1, ["qn:1"])
    assert one["contract"]["index_clauses"] == [
        {"id": "ctr:1#3.2", "series": "S1", "material_share": 0.5, "deadband_pct": 0}
    ]
    assert [d["id"] for d in one["documents"]] == ["doc:1", "doc:2", "doc:3"] and one["documents"][2]["part_ids"] == [
        "part:A"
    ]
    assert two["news"][0]["noise"] is True and [n["id"] for n in one["market_news"]] == ["news:3"]
    assert two["market_news"] == [] and one["own_quotes"][0]["remarks"] == "Payment within 10 days requested."


def test_golden_values_on_the_real_package(real_pkg):
    src = Source(real_pkg)
    w, b = build_supplier(src, "sup:70130"), build_supplier(src, "sup:70110")
    assert set(w["parts"]) == {"part:310011", "part:310012"}
    assert w["parts"]["part:310011"]["should_cost"]["id"] == "cost:310011"
    assert (w["parts"]["part:310012"]["should_cost"]["id"], w["parts"]["part:310012"]["should_cost"]["unit_cost"]) == (
        "cost:310012",
        370.21,
    )
    assert b["parts"]["part:310012"]["should_cost"]["id"] == "cost:310012-70110"
    assert b["parts"]["part:310012"]["should_cost"]["unit_cost"] == 347.27
    assert b["parts"]["part:310010"]["should_cost"]["unit_cost"] == 132.64
    assert build_supplier(src, "sup:70520")["parts"]["part:350010"]["should_cost"]["id"] == "cost:350010-70520"
    assert build_supplier(src, "sup:70510")["parts"]["part:350010"]["should_cost"]["id"] == "cost:350010"
    assert [w["parts"][p]["current_price"]["price"] for p in ("part:310011", "part:310012")] == [180.52, 359.17]
    assert [w["parts"][p]["price_to_should_cost"] for p in ("part:310011", "part:310012")] == [1.0018, 0.9702]
    assert b["parts"]["part:310012"]["price_to_should_cost"] == 1.1031
    assert (
        w["economics"]["our_spend_eur"]["FY2026"] == 1289395.92 and w["economics"]["our_share_of_turnover_pct"] == 6.68
    )
    assert b["economics"]["our_share_of_turnover_pct"] == 4.87
    t = build_supplier(src, "sup:70210")
    assert t["economics"]["our_share_of_turnover_pct"] == 9.05 and t["identity"]["turnover_estimated"] is True
    late = [build_supplier(src, s)["economics"]["we_pay_late_days"] for s in ("sup:70130", "sup:70110", "sup:70580")]
    assert late == [2.8, 3.7, 19.4]
    perf = w["performance"]
    assert (perf["latest"]["id"], perf["latest"]["otd_pct"], perf["latest"]["ppm"], perf["latest"]["colour"]) == (
        "sc:70130@2026Q3",
        82.4,
        651,
        "green",
    )
    assert (perf["mean_4q"]["otd_pct"], perf["mean_4q"]["ppm"], perf["trend"]) == (87.83, 1147.5, "better")
    drivers = {x["series"]: x for x in b["parts"]["part:310010"]["drivers"]}
    assert (drivers["LCI-C"]["weight"], drivers["LCI-C"]["change_12m_pct"]) == (0.32, 2.66)
    assert drivers["LCI-C"]["ids_12m"] == ["idx:LCI-C@2025-06", "idx:LCI-C@2026-06"]
    assert drivers["PPI-C241"]["change_12m_pct"] == 6.54
    assert (drivers["PPI-D351"]["change_12m_pct"], drivers["PPI-D351"]["change_6m_pct"]) == (-3.72, 6.63)
    assert len(w["documents"]) == len(b["documents"]) == 7


def test_the_real_package_in_numbers(real_pkg):
    src = Source(real_pkg)
    ds = [build_supplier(src, s) for s in src.detailed_ids()]
    assert len(ds) == 46 and all(validate(d) == [] for d in ds)
    assert sum(len(d["parts"]) for d in ds) == 90 and sum(len(d["documents"]) for d in ds) == 208
    assert sum(len(d["news"]) for d in ds) == 32
    market = {"news:20260910-27", "news:20260912-30", "news:20260914-31", "news:20260916-32"}
    assert not any(n["id"] in market for d in ds for n in d["news"])


def _signals(d):
    return {s["kind"]: s["strength"] for s in d["signals"]}


def test_signals_and_economics_on_the_fixture(fixture_pkg, release_pkg):
    src = Source(fixture_pkg)
    one = signals.apply(build_supplier(src, "sup:1"))
    assert _signals(one) == {
        "cash_short": 2,
        "margin_floor": 1,
        "ownership_change": 1,
        "price_claim": 1,
        "wants_volume": 2,
    }
    assert one["economics"]["cash_pressure"] == "high" and one["economics"]["archetype"] == "job_shop"
    assert one["economics"]["cost_of_money"] == 0.25
    cash = next(s for s in one["signals"] if s["kind"] == "cash_short")
    assert cash["evidence"] == ["doc:1", "quote:1"] and "bank is watching" in cash["excerpt"]
    two = signals.apply(build_supplier(src, "sup:2"))
    assert _signals(two) == {"cash_short": 1, "delivery_problem": 2, "material_hedged": 1, "quality_problem": 3}
    assert two["economics"]["cost_of_money"] == 0.36 and "measured" in two["economics"]["cost_of_money_basis"]
    assert "ownership_change" not in _signals(two)  # its 'new managing director' news is noise
    three = signals.apply(build_supplier(src, "sup:3"))
    assert _signals(three) == {"approval_ladder": 1} and three["economics"]["archetype"] == "group"
    assert three["economics"]["cost_of_money"] == 0.065 and three["economics"]["cash_pressure"] == "low"
    later = signals.apply(build_supplier(Source(release_pkg), "sup:3"))
    assert _signals(later)["capacity_tight"] == 2 and later["economics"]["archetype"] == "monopolist"
    assert all(validate(d) == [] for d in (one, two, three, later))


GOLDEN_SIGNALS = {
    "sup:70130": (
        {"cash_short": 3, "wants_volume": 2, "margin_floor": 2, "ownership_change": 1},
        "high",
        "job_shop",
        0.25,
    ),
    "sup:70110": (
        {"partnership": 2, "cash_short": 1, "informal_costing": 2, "price_claim": 1, "quality_problem": 1},
        "medium",
        "family",
        0.09,
    ),
    "sup:70210": ({}, "high", "job_shop", 0.36),
    "sup:70280": ({}, "high", None, 0.54),
    "sup:70230": ({}, "high", None, 0.45),
    "sup:70350": ({}, "high", None, 0.36),
    "sup:70510": ({"approval_ladder": 1}, "low", "group", 0.065),
    "sup:70240": ({}, None, "job_shop", 0.25),
    "sup:70420": ({"list_price_fixed": 1, "approval_ladder": 1}, None, None, None),
    "sup:70190": ({"material_hedged": 1}, None, None, None),
    "sup:70620": ({"list_price_fixed": 1}, None, None, None),
}


@pytest.mark.parametrize("sid", sorted(GOLDEN_SIGNALS))
def test_golden_signals_on_the_real_package(real_pkg, sid):
    at_least, pressure, arche, rate = GOLDEN_SIGNALS[sid]
    d = signals.apply(build_supplier(Source(real_pkg), sid))
    got = _signals(d)
    assert all(got.get(k, 0) >= v for k, v in at_least.items()), got
    if sid == "sup:70130":
        assert got["cash_short"] == 3 and got["ownership_change"] == 1
    if sid == "sup:70110":
        assert got["cash_short"] == 1
    ec = d["economics"]
    assert pressure is None or ec["cash_pressure"] == pressure
    assert arche is None or ec["archetype"] == arche
    assert rate is None or ec["cost_of_money"] == rate


def test_noise_and_market_news_never_make_a_signal(real_pkg):
    src = Source(real_pkg)
    ds = [signals.apply(build_supplier(src, s)) for s in src.detailed_ids()]
    noise = {n["id"] for d in ds for n in d["news"] if n["noise"]}
    market = {n["id"] for n in src.market_news()}
    assert len(noise) == 10 and len(market) == 7
    assert not any(e in noise | market for d in ds for s in d["signals"] for e in s["evidence"])
    by_id = {d["supplier_id"]: _signals(d) for d in ds}
    assert "ownership_change" not in by_id["sup:70230"] and "ownership_change" not in by_id["sup:70160"]
    assert sum("quality_problem" in s for s in by_id.values()) == 17
    assert sum("delivery_problem" in s for s in by_id.values()) == 9


def test_profile_text_is_short_and_complete(fixture_pkg, real_pkg):
    for pkg in (fixture_pkg, real_pkg):
        for d in build_all(pkg).values():
            text = d["profile_text"]
            assert 0 < len(text.split()) <= 120 and "None" not in text, text
    w = build_one(Source(real_pkg), "sup:70130")["profile_text"]
    assert w.startswith("Gießerei Wimbacher GmbH (DE; family; 120 staff") and "Cost of money about 25 % a year" in w
    assert "Cost of money about 6.5 %" in build_one(Source(real_pkg), "sup:70510")["profile_text"]


def test_serialization_is_canonical():
    assert dumps({"b": (1, 2.0000001), "a": 0.1 + 0.2}) == dumps({"a": 0.3, "b": [1, 2.0]})
    assert dumps({"a": "Gießerei"}).endswith("\n") and "Gießerei" in dumps({"a": "Gießerei"})
    with pytest.raises(ValueError):
        dumps({"x": float("nan")})


def test_build_writes_the_same_bytes_twice(tmp_path, fixture_pkg):
    one, two = tmp_path / "one", tmp_path / "two"
    files = write_all(build_all(fixture_pkg), one)
    write_all(build_all(fixture_pkg), two)
    assert files == ["1.json", "2.json", "3.json", "index.json"]
    assert all((one / f).read_bytes() == (two / f).read_bytes() for f in files)
    idx = json.loads((one / "index.json").read_text(encoding="utf-8"))
    assert idx["suppliers"]["sup:1"]["file"] == "1.json" and idx["built_from"]["package"] == "9.9.9"
    (one / "99.json").write_text("{}")
    write_all(build_all(fixture_pkg), one)
    assert not (one / "99.json").exists()


def test_the_cli_builds_checks_and_shows(tmp_path, fixture_pkg, capsys):
    data, out = str(fixture_pkg.root), str(tmp_path / "dossiers")
    assert cli(["--data", data, "--out", out, "build"]) == 0
    assert cli(["--data", data, "--out", out, "check"]) == 0
    (tmp_path / "dossiers" / "1.json").write_text("{}")
    assert cli(["--data", data, "--out", out, "check"]) == 1
    assert cli(["--data", data, "--out", out, "show", "2"]) == 0 and "Shop Two" in capsys.readouterr().out
    assert cli(["--data", data, "--out", out, "signals-report", "--to", str(tmp_path / "r.md")]) == 0
    assert "## sup:1 Foundry One GmbH" in (tmp_path / "r.md").read_text(encoding="utf-8")


def test_the_committed_dossiers_are_current(real_pkg):
    if not (DOSSIERS / "index.json").is_file():
        pytest.skip("no dossiers built yet")
    assert cli(["--data", str(REAL), "--out", str(DOSSIERS), "check"]) == 0
