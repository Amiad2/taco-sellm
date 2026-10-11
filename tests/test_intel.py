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


def test_a_stranger_gets_every_field_of_the_contract():
    d = dossier("sup:99999", ["part:310011"])
    assert set(d) == set(TOP_KEYS) and set(CORE_FIELDS) <= set(d)
    assert d["schema_version"] == SCHEMA_VERSION == 1
    assert d["supplier_id"] == "sup:99999" and d["coverage"] == "case_only"
    assert isinstance(d["economics"]["cost_of_money"], float) and 0 < d["economics"]["cost_of_money"] <= 1
    assert d["economics"]["cash_pressure"] in ("low", "medium", "high")
    assert isinstance(d["signals"], list) and isinstance(d["citable"], list)
    assert set(d["parts"]) == {"part:310011"} and isinstance(d["parts"]["part:310011"]["drivers"], list)
    assert "informal_costing" in SIGNAL_KINDS


@pytest.mark.parametrize(
    "sid, parts", [(None, None), (123, "part:X"), ("", [None, 5]), ("sup:1", 7), ("sup:1", {"a": 1})]
)
def test_dossier_never_raises(sid, parts):
    d = dossier(sid, parts, case={"weird": True}, opening=["not", "messages"])
    assert d["schema_version"] == 1 and isinstance(d["parts"], dict)


def test_dossier_is_fast():
    dossier("sup:70130", ["part:310011"])
    t0 = time.perf_counter()
    for _ in range(100):
        dossier("sup:70130", ["part:310011", "part:310012"])
    assert (time.perf_counter() - t0) / 100 < 0.005


def test_a_stored_dossier_is_valid():
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
    sunday = 1 if real_pkg.release else 0  # the Sunday release adds one market news item
    assert len(src.documents("sup:70130")) == 7 and len(src.market_news()) == 7 + sunday


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
    letters = 4 if real_pkg.release else 0  # the Sunday release: four supplier letters (the memo has no supplier)
    assert sum(len(d["parts"]) for d in ds) == 90 and sum(len(d["documents"]) for d in ds) == 208 + letters
    assert sum(len(d["news"]) for d in ds) == 32 + (5 if real_pkg.release else 0)  # five supplier news on Sunday
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
    sunday = 1 if real_pkg.release else 0  # the Sunday release: one more noise item, one more market item
    assert len(noise) == 10 + sunday and len(market) == 7 + sunday
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


CASES = Path(__file__).resolve().parents[1] / "sellm" / "lab" / "cases"
RUNS = Path(__file__).resolve().parents[1] / "runs"


def _openings():
    seen, out = set(), []
    for f in sorted(RUNS.glob("practice/*/*.json")) + sorted(RUNS.glob("sandbox/*/*.json")):
        s = json.loads(f.read_text(encoding="utf-8"))
        if not isinstance(s, dict) or "threads" not in s:
            continue
        for sid in s["case"]["suppliers"]:
            if (s["case_id"], sid) not in seen and s["threads"].get(sid, {}).get("messages"):
                seen.add((s["case_id"], sid))
                out.append((s["case"], s["threads"], sid))
    return out


def test_overlay_on_every_case_file(real_pkg):
    files = sorted(CASES.glob("*.json"))
    assert len(files) == 21
    for f in files:
        case = json.loads(f.read_text(encoding="utf-8"))
        for sid in case["suppliers"]:
            d = dossier(sid, case["parts"], case=case, package=real_pkg)
            assert validate(d) == [] and set(d["parts"]) == set(case["parts"]), (case["case_id"], sid)
            assert d["built_from"]["case_id"] == case["case_id"]
            assert not any("failed" in w or "overlay:" in w for w in d["warnings"]), d["warnings"]


def test_overlay_reads_the_opening_e_mails(real_pkg):
    from arena_kit.docs import standard_terms

    openings = _openings()
    assert len(openings) >= 15
    for case, threads, sid in openings:
        d = dossier(sid, case["parts"], case=case, opening=threads, package=real_pkg)
        msg = threads[sid]["messages"][0]
        assert validate(d) == [], (case["case_id"], sid)
        std = standard_terms([msg])
        assert all(d["standard_terms"][k] == v for k, v in std.items() if k in d["standard_terms"])
        assert d["standard_terms"]["source"] == ("quote_pdf" if std else d["standard_terms"]["source"])
        assert d["contact"]["role"] == msg["from_name"].split(",")[0].strip() and d["contact"]["name"]
        assert d["opening_offer"]["offer_id"] == msg["term_sheets"][0]["term_sheet_id"]
    p01 = next((c, t, s) for c, t, s in openings if c["case_id"] == "case:P01")
    d = dossier(p01[2], p01[0]["parts"], case=p01[0], opening=p01[1], package=real_pkg)
    assert (d["contact"]["name"], d["contact"]["role"]) == ("Thomas Brandlhuber", "Owner")
    assert [
        (x["series"], x["stated_change_pct"], x["cost_share_pct"], x["true_change_12m_pct"], x["matches"])
        for x in d["stated_drivers"]
    ] == [
        ("LCI-C", 2.7, 30.0, 2.66, True),
        ("PPI-C241", 6.5, 24.0, 6.54, True),
    ]
    assert d["standard_terms"]["payment_days"] == 30 and d["opening_offer"]["offer_id"] == "offer:70110-0"
    buyer = [a for a in d["parts"]["part:310010"]["alternatives"] if a.get("kind") == "buyer_alternative"]
    assert [(a["supplier_id"], a["quote_id"]) for a in buyer] == [("sup:70140", "quote:7200001")]


def test_an_rfq_shows_each_bidder_its_rivals(real_pkg):
    case, threads, _ = next(o for o in _openings() if o[0]["case_id"] == "case:P05")
    for sid in case["suppliers"]:
        d = dossier(sid, case["parts"], case=case, opening=threads, package=real_pkg)
        rivals = [a for a in d["parts"][case["parts"][0]]["alternatives"] if a.get("kind") == "rfq_rival"]
        assert len(rivals) == 2 and all(a["private"] and a["offer_id"].startswith("offer:") for a in rivals)
        assert sid not in {a["supplier_id"] for a in rivals}


@pytest.mark.parametrize("facts", ["dict", "list"])
def test_a_stranger_gets_a_dossier_from_the_case_alone(fixture_pkg, facts):
    fact = {"part": "part:X1", "supplier": "sup:99999", "unit_cost": 10.0}
    case_facts = {"cost:X1": fact} if facts == "dict" else [{"id": "cost:X1", **fact}]
    case = {"case_id": "case:H1", "parts": ["part:X1"], "suppliers": ["sup:99999"], "facts": case_facts}
    d = dossier("sup:99999", ["part:X1"], case=case, package=fixture_pkg)
    assert validate(d) == [] and d["coverage"] == "case_only"
    part = d["parts"]["part:X1"]
    assert part["should_cost"]["unit_cost"] == 10.0 and part["should_cost"]["plant_specific"] is True
    assert part["floor_estimate"]["value"] == 10.0 and d["case_facts"] == {"cost:X1": fact}


def test_the_old_record_maps_to_the_living_company(real_pkg):
    d = dossier("sup:71999", ["part:330010"], package=real_pkg)
    assert d["supplier_id"] == "sup:70210" and any("old, blocked record" in w for w in d["warnings"])


def test_without_a_package_the_stored_dossier_still_comes(tmp_path):
    d = dossier("sup:70130", ["part:310012"], package=tmp_path / "nothing")
    assert validate(d) == [] and any("no data package" in w for w in d["warnings"])
    if (DOSSIERS / "70130.json").is_file():
        assert d["coverage"] == "full" and d["parts"]["part:310012"]["should_cost"]["id"] == "cost:310012"


def test_dossier_survives_garbage(fixture_pkg):
    import random

    rng = random.Random(42)
    junk = [None, 0, "x", [], {}, [None], {"messages": "x"}, {"sup:1": [1, 2]}, {"suppliers": 5}, 3.5]
    for _ in range(200):
        case = rng.choice(
            [
                None,
                {},
                {
                    "case_id": rng.choice(junk),
                    "suppliers": rng.choice(junk),
                    "facts": rng.choice(junk),
                    "buyer": rng.choice(junk),
                    "briefing": rng.choice(junk),
                    "trigger_doc": rng.choice(junk),
                },
            ]
        )
        d = dossier(
            rng.choice(["sup:1", "sup:2", "sup:404", None, 7]),
            rng.choice(junk + [["part:A"]]),
            case=case,
            opening=rng.choice(junk),
            package=fixture_pkg,
        )
        assert validate(d) == [], (case, d["warnings"])


def test_the_overlay_is_fast(real_pkg):
    calls = []
    for case, threads, sid in _openings():
        dossier(sid, case["parts"], case=case, opening=threads, package=real_pkg)
        t0 = time.perf_counter()
        dossier(sid, case["parts"], case=case, opening=threads, package=real_pkg)
        calls.append(time.perf_counter() - t0)
    calls.sort()
    assert calls[int(len(calls) * 0.95) - 1] < 0.1


def test_citable_for_is_called_once_group_c_ships_it(monkeypatch, fixture_pkg):
    import sys
    import types

    entry = {
        "ids": ["cost:A"],
        "kind": "cost",
        "figure": 101.0,
        "unit": "EUR",
        "about": "part:A",
        "statement": "Our estimate cost:A is EUR 101.0.",
        "helps_buyer": True,
        "private": False,
    }
    module = types.ModuleType("sellm.claims")
    module.citable_for = lambda pkg, sid, parts, case=None: [entry] if sid == "sup:1" else []
    monkeypatch.setitem(sys.modules, "sellm.claims", module)
    assert build_one(Source(fixture_pkg), "sup:1")["citable"] == [entry]
    assert dossier("sup:1", ["part:A"], package=fixture_pkg)["citable"] == [entry]

    def broken(pkg, sid, parts, case=None):
        raise RuntimeError("boom")

    module.citable_for = broken
    d = build_one(Source(fixture_pkg), "sup:1")
    assert d["citable"] == [] and any("citable_for failed" in w for w in d["warnings"]) and validate(d) == []


def test_verify_checks_pass_on_the_fixture(tmp_path, fixture_pkg):
    from sellm.intel import verify

    out = tmp_path / "dossiers"
    write_all(build_all(fixture_pkg), out)
    data = str(fixture_pkg.root)
    for check in (
        verify.v2_schema,
        verify.v3_determinism,
        verify.v4_completeness,
        verify.v5_numbers,
        verify.v6_citations,
        verify.v9_sunday,
    ):
        ok, detail = check(data, out)
        assert ok, (check.__name__, detail)
    (out / "1.json").write_text((out / "1.json").read_text().replace('"price": 102.0', '"price": 99.0'))
    assert not verify.v5_numbers(data, out)[0] and not verify.v3_determinism(data, out)[0]


@pytest.mark.parametrize("case_id, lab_floor", [("P01", 129.91), ("P02", 363.96), ("P03", 397.46), ("P10", 25.64)])
def test_golden_floors_match_the_lab_within_ten_percent(real_pkg, case_id, lab_floor):
    case = json.loads((CASES / f"{case_id}.json").read_text(encoding="utf-8"))
    d = dossier(case["suppliers"][0], case["parts"], case=case, package=real_pkg)
    value = d["parts"][case["parts"][0]]["floor_estimate"]["value"]
    assert abs(lab_floor - value) / value <= 0.10, (value, lab_floor)


def test_concurrent_first_calls_build_the_package_once(real_pkg):
    import threading

    import sellm.intel as intel

    case = json.loads((CASES / "P01.json").read_text(encoding="utf-8"))
    intel._SOURCES.clear()
    out = []
    threads = [
        threading.Thread(target=lambda: out.append(dossier("sup:70110", case["parts"], case=case))) for _ in range(13)
    ]
    t0 = time.perf_counter()
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert time.perf_counter() - t0 < 2.0  # 6.6-8.3 s without the lock
    assert len(out) == 13 and all(d["coverage"] == "full" and d["citable"] and validate(d) == [] for d in out)


def test_a_case_fact_is_citable_in_its_case(real_pkg):
    case = json.loads((CASES / "P01.json").read_text(encoding="utf-8"))
    case["facts"] = {"cost:310010-H": {"part": "part:310010", "supplier": "sup:70110", "unit_cost": 128.5}}
    d = dossier("sup:70110", case["parts"], case=case, package=real_pkg)
    assert any("cost:310010-H" in c["ids"] and "128.50" in c["statement"] for c in d["citable"])
    assert d["parts"]["part:310010"]["should_cost"]["id"] == "cost:310010-H"


def test_a_trigger_letter_of_the_release_speaks_for_its_writer_only(real_pkg):
    """A hidden case may be triggered by a Sunday letter: one bidder asking for payment within 10 days does not make
    the other bidders short of cash, and our own memo (headlines about many suppliers) is nobody's statement."""
    if real_pkg.release is None:
        pytest.skip("needs the Sunday release")
    import sellm.intel as intel

    lab = Path(__file__).resolve().parents[1] / "sellm" / "lab" / "cases"
    rfq = json.loads((lab / "P05.json").read_text(encoding="utf-8"))

    def kinds(case, sid):
        d = intel.dossier(sid, case.get("parts"), case, None, package=real_pkg)
        return {s["kind"]: s["strength"] for s in d["signals"]}

    letter = {**rfq, "trigger_doc": "doc:20261005-70250-S2"}
    for sid in rfq["suppliers"]:
        assert kinds(letter, sid) == kinds(rfq, sid), sid
    assert kinds(rfq, "sup:70250")["cash_short"] >= 2  # its own letter is in its dossier
    bundle = json.loads((lab / "P07.json").read_text(encoding="utf-8"))
    memo = {**bundle, "trigger_doc": "doc:20261009-HPW-MEMO"}
    assert kinds(memo, bundle["suppliers"][0]) == kinds(bundle, bundle["suppliers"][0])
    for sid in ("sup:70510", "sup:70650"):  # the two letters that name the terms still open
        d = intel.dossier(sid, (), None, None, package=real_pkg)
        assert "wants_planning" in {s["kind"] for s in d["signals"]}
        assert not any(s["kind"] == "price_claim" and "S" in s["evidence"][-1].rsplit("-", 1)[-1] for s in d["signals"])
        assert all(doc["asked_pct"] != "" for doc in d.get("documents") or [])


def test_the_sunday_release_is_read_by_its_wording(real_pkg):
    """Release of Sun 11 Oct: its letters carry empty asked_pct fields, which are no price demand
    (extract._released); forward buying at fixed prices is a hedge, insolvency is cash pressure, an acquisition an
    ownership change, and 'supply back to normal' voids the earlier capacity news."""
    if not real_pkg.release:
        pytest.skip("Sunday release not downloaded (uv run arena data)")
    src = Source(real_pkg)
    by_id = {s: signals.apply(build_supplier(src, s)) for s in ("sup:70720", "sup:70250", "sup:70510", "sup:70540")}
    got = {s: _signals(d) for s, d in by_id.items()}
    assert got["sup:70720"] == {"material_hedged": 1}
    assert got["sup:70250"]["cash_short"] == 2 and "price_claim" not in got["sup:70250"]
    assert got["sup:70510"]["price_claim"] == 1 and got["sup:70510"]["list_price_fixed"] == 1
    assert "capacity_tight" not in got["sup:70540"]
    insolvent = signals.apply(build_supplier(src, "sup:70140"))
    assert any("news:20261006-S1" in s["evidence"] for s in insolvent["signals"] if s["kind"] == "cash_short")
    sold = signals.apply(build_supplier(src, "sup:70650"))
    assert any("news:20261006-S9" in s["evidence"] for s in sold["signals"] if s["kind"] == "ownership_change")
