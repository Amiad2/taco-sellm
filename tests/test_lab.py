"""The lab (sellm/lab): twins match their cases, the local table keeps the arena's rules, the
claim checker follows the published rules, any agent can play every twin to the end."""

import random
from pathlib import Path

import pytest

from arena_kit.agents.naive import NaiveAgent
from arena_kit.client import ArenaError
from arena_kit.cost import must_haves_ok
from arena_kit.play import play
from sellm.lab import LocalTable, best_package
from sellm.lab import twins as twin_lib
from sellm.lab.bot import SupplierThread
from sellm.lab.claims import ClaimChecker

DATA = Path(__file__).resolve().parents[1] / "data" / "package" / "facts.json"
SCENARIOS = twin_lib.load()


def facts():
    if not DATA.is_file():
        pytest.skip("data package not downloaded (uv run arena data)")
    import json

    return json.loads(DATA.read_text(encoding="utf-8"))


@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda s: s.name)
def test_twin_reaches_c_best(scenario):
    best = min(best_package(scenario.case, p)[0] for p in scenario.personas.values())
    assert best == pytest.approx(scenario.c_best, rel=1e-4)


@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda s: s.name)
def test_naive_agent_plays_every_twin(scenario):
    for seed in range(3):
        table = LocalTable(scenario, {}, seed=seed)
        result = play(table, scenario.case["case_id"], NaiveAgent())
        assert 0.0 <= result["score"] <= 1.0
        if result["deal"]:
            persona = scenario.personas[result["supplier_id"]]
            assert persona.value(scenario.case, result["terms"]) >= persona.full_cost - 1e-6
            assert result["must_haves_ok"] == must_haves_ok(scenario.case, result["terms"])


def _p01():
    return next(s for s in SCENARIOS if s.name == "P01")


def test_table_refuses_what_the_arena_refuses():
    s = _p01()
    table = LocalTable(s, {})
    case, threads = table.open()
    sid = case["suppliers"][0]
    with pytest.raises(ArenaError) as e:  # a field missing
        table.send(sid, {"body": "x", "term_sheets": [{"terms": {"unit_price": 130.0}}]})
    assert e.value.status == 422
    with pytest.raises(ArenaError) as e:  # a value not in term_options
        table.send(
            sid, {"term_sheets": [{"terms": {"unit_price": 130.0, "effective_date": "2027-02-01", "payment_days": 30}}]}
        )
    assert e.value.status == 422
    reply = table.send(
        sid,
        {
            "body": "x",
            "term_sheets": [{"terms": {"unit_price": 120.0, "effective_date": "2027-01-01", "payment_days": 30}}],
        },
    )
    if len(reply["term_sheets"]) > 1:  # only the first sheet is a standing offer
        with pytest.raises(ArenaError) as e:
            table.close(sid, {"action": {"type": "accept", "term_sheet_id": reply["term_sheets"][1]["term_sheet_id"]}})
        assert e.value.status == 422
    for _ in range(case["round_limit"] - 1):
        if table.threads[sid].closed:
            return
        table.send(
            sid,
            {
                "body": "x",
                "term_sheets": [{"terms": {"unit_price": 120.0, "effective_date": "2027-01-01", "payment_days": 30}}],
            },
        )
    with pytest.raises(ArenaError) as e:
        table.send(sid, {"body": "x"})
    assert e.value.status == 409


def test_walk_away_scores_the_alternative():
    s = _p01()
    table = LocalTable(s, {})
    case, _ = table.open()
    result = table.close(case["suppliers"][0], {"action": {"type": "walk_away"}})
    assert result["deal"] is False
    assert result["score"] == 0.0  # P01's alternative is worse than the opening


def test_supplier_mirrors_steps_and_holds_its_final_offer():
    s = _p01()
    persona = s.personas["sup:70110"]
    bot = SupplierThread(persona, s.case, random.Random(0))
    bot.opening()
    terms = {"effective_date": "2027-01-01", "payment_days": 30}
    asks = []
    price = 120.0
    while bot.status != "final_offer":
        reply = bot.respond({"body": "", "term_sheets": [{"terms": {**terms, "unit_price": price}}]})
        asks.append(bot.ask)
        price += 1.0
    assert all(a >= b for a, b in zip(asks, asks[1:], strict=False))  # it never asks for more
    assert asks[-1] >= persona.full_cost
    standing = reply["term_sheets"][0]["terms"]
    met = bot.respond({"body": "", "term_sheets": [{"terms": standing}]})
    assert met["status"] == "agreed"


def test_claims_follow_the_published_rules():
    f = facts()
    s = _p01()
    checker = ClaimChecker(f, s.case, ["PPI-C241", "LCI-C", "PPI-D351"])
    months = sorted(k for k in f if k.startswith("idx:PPI-D351@"))[-13:]
    a, b = months[0], months[-1]
    change = (f[b]["value"] / f[a]["value"] - 1) * 100
    used = set()
    good = checker.check("sup:70110", f"Electricity {a} to {b} changed by {change:.1f} %.", used=used)
    assert [r["result"] for r in good] == ["verified"]
    again = checker.check("sup:70110", f"As {a} and {b} showed, {change:.1f} %.", used=used)
    assert [r["result"] for r in again] == ["duplicate"]
    wrong = checker.check("sup:70110", f"Between {a} and {b} it moved {change + 3:.1f} %.", used=set())
    assert [r["result"] for r in wrong] == ["contradicted"]
    unknown = checker.check("sup:70110", "See cost:999999 at EUR 10.00.", used=set())
    assert [r["result"] for r in unknown] == ["contradicted"]
    cost = checker.check("sup:70110", "Our estimate cost:310010 puts your full cost at EUR 132.64.", used=set())
    assert [r["result"] for r in cost] == ["verified"]


def test_invented_scenarios_are_valid_and_playable():
    from arena_kit.data import DataPackage
    from sellm.lab.invent import generate
    from sellm.lab.strategies import Calculator

    facts()  # skips without the data package
    pkg = DataPackage(DATA.parent)
    for s in generate(8, pkg, seed=7):
        assert s.c_open > s.c_best
        for p in s.personas.values():
            assert set(p.opening) <= set(s.case["negotiable"])
        for agent in (NaiveAgent(), Calculator(pkg)):
            result = play(LocalTable(s, pkg.facts, seed=0), s.case["case_id"], agent)
            assert 0.0 <= result["score"] <= 1.0


def test_calculator_never_breaks_a_must_have():
    from sellm.lab.strategies import Calculator

    for s in SCENARIOS:
        result = play(LocalTable(s, {}, seed=0), s.case["case_id"], Calculator(None))
        assert not result["deal"] or result["must_haves_ok"]


def _scenario(name):
    return next(s for s in SCENARIOS if s.name == name)


def test_clock_rfq_one_thread_at_a_time_times_out_the_others():
    from sellm.lab.strategies import Calculator
    from sellm.lab.table import play_lab

    s = _scenario("P05")
    seq = [play_lab(LocalTable(s, {}, seed=i, clock=True, think_s=2.0), Calculator(None)) for i in range(3)]
    par = [
        play_lab(LocalTable(s, {}, seed=i, clock=True, think_s=2.0), Calculator(None), mode="parallel")
        for i in range(3)
    ]
    assert sum(r["timeouts"] for r in seq) > sum(r["timeouts"] for r in par)


def test_wave_cap_ends_the_session_without_a_deal():
    s = _scenario("P01")
    table = LocalTable(s, {}, clock=True, think_s=2.0, wave_cap_s=100)
    case, _ = table.open()
    sid = case["suppliers"][0]
    terms = {"unit_price": 120.0, "effective_date": "2027-01-01", "payment_days": 30}
    with pytest.raises(ArenaError):
        for _ in range(10):
            table.send(sid, {"body": "x", "term_sheets": [{"terms": terms}]})
    assert table.outcome["end_reason"] in ("wave_cap", "no_deal") and not table.outcome["deal"]


def test_a_timeout_replaces_the_offer_id():
    s = _scenario("P01")
    table = LocalTable(s, {}, clock=True, think_s=61.0)
    case, threads = table.open()
    sid = case["suppliers"][0]
    old = threads[sid][0]["term_sheets"][0]["term_sheet_id"]
    with pytest.raises(ArenaError) as e:  # we waited 61 s: late, and the old ID is gone
        table.close(sid, {"action": {"type": "accept", "term_sheet_id": old}})
    assert e.value.status == 422
    assert table.threads[sid].standing["term_sheet_id"] != old


def test_a_sheet_may_use_the_suppliers_standard_value():
    s = _scenario("D02")
    table = LocalTable(s, {})
    case, _ = table.open()
    sid = "sup:DEMO-C1"
    std = table.personas[sid].standard["lead_time_days"]  # 45, not one of the options
    assert std not in case["term_options"]["lead_time_days"]
    sheet = {"unit_price": 15.0, "payment_days": 30, "lead_time_days": std, "incoterm": "DAP"}
    table.send(sid, {"body": "x", "term_sheets": [{"terms": sheet}]})


def _pkg():
    from arena_kit.data import DataPackage

    facts()  # skips without the data package
    return DataPackage(DATA.parent)


def test_scenarios_survive_a_round_trip(tmp_path):
    from sellm.lab import store

    path = tmp_path / "s.json.gz"
    store.save(SCENARIOS, path)
    back = store.load(path)
    assert [s.name for s in back] == [s.name for s in SCENARIOS]
    assert back[0].personas.keys() == SCENARIOS[0].personas.keys()


@pytest.mark.parametrize("mode", ["sequential", "parallel"])
def test_every_edge_case_is_playable_by_both_agents(mode):
    from sellm.lab.invent import EDGES, edge_suite
    from sellm.lab.strategies import Calculator
    from sellm.lab.table import play_lab

    pkg = _pkg()
    suite = edge_suite(pkg, per_edge=1, seed=300)
    assert {t for s in suite for t in s.tags} >= set(EDGES) - {"current_contract"}
    for s in suite:
        assert s.c_open > s.c_best
        for agent in (NaiveAgent(), Calculator(pkg)):
            table = LocalTable(s, pkg.facts, seed=1, clock=True, think_s=2.0, wave_cap_s=480)
            r = play_lab(table, agent, mode=mode)
            assert 0.0 <= r["score"] <= 1.0


def test_calculator_walks_away_when_the_alternative_is_best():
    from sellm.lab.invent import generate
    from sellm.lab.strategies import Calculator
    from sellm.lab.table import play_lab

    pkg = _pkg()
    for s in generate(3, pkg, seed=11, data_share=0.0, edges=["walk_away_best"]):
        r = play_lab(LocalTable(s, pkg.facts, seed=0), Calculator(pkg))
        assert r["score"] == pytest.approx(1.0) and not r["deal"]


def test_tournament_compare_runs_in_worker_processes(tmp_path):
    from sellm.lab import tournament

    _pkg()
    opts = {"clock": True, "mode": "parallel", "wave_cap_s": 480, "think_s": 2.0, "vary": True}
    run = tournament.Run(tmp_path / "run", opts, SCENARIOS[:4], SCENARIOS[4:6], workers=2, log=lambda _: None)
    try:
        rows = tournament.compare(run, ["naive", "calc"], seeds=1)
    finally:
        run.close()
    assert len(rows) == 2 * 6 and not [r for r in rows if "crash" in r]
    text = tournament.report(rows, "test")
    assert "| 1 | calc" in text or "| 1 | naive" in text


def test_stress_verdict_fails_on_a_broken_must_have():
    from sellm.lab import stress

    row = {"strategy": "x", "knobs": {}, "scenario": "S", "kind": "invented", "seed": 0, "type": "rfq",
           "goal": "routine", "tags": [], "archetypes": ["family"], "pool": "train", "score": 0.0,
           "deal": True, "broken": True, "worse": False, "wall_s": 0.1, "mode": "parallel"}  # fmt: skip
    _, verdict = stress.report([row], "x", {})
    assert verdict == "FAIL"
    _, verdict = stress.report([{**row, "broken": False}], "x", {})
    assert verdict == "PASS"


def test_ui_serves_runs_exports_and_refuses_bad_input():
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from sellm.lab.ui import argv_for, create_app

    c = TestClient(create_app())
    assert c.get("/").status_code == 200
    assert "calc" in c.get("/api/meta").json()["agents"]
    assert c.post("/api/start", json={"cmd": "rm -rf", "options": {}}).status_code == 400
    assert c.get("/api/run/..%2F..%2Fdocs/report").status_code == 404
    args = argv_for("search", {"minutes": 5, "label": "a b;rm"})
    assert args[:3] == ["search", "--minutes", "5.0"] and args[-1] == "abrm"


class _FakeBrain:
    """Stands in for the LLM: always the same decision, no API calls."""

    def __init__(self, reply):
        self.reply, self.calls = reply, 0

    def ask(self, system, user):
        self.calls += 1
        return dict(self.reply)


def test_llm_supplier_cannot_break_the_engines_limits():
    from sellm.lab.table import play_lab

    s = _scenario("P01")
    brain = _FakeBrain({"decision": "counter", "price": 1.0, "email": "Our offer: EUR {PRICE}.", "reasons": ["x"]})
    table = LocalTable(s, {}, seed=0, supplier="llm", brain=brain)
    result = play_lab(table, NaiveAgent())
    p = table.personas["sup:70110"]
    for t in table.threads.values():
        for m in t.messages:
            for ts in m["term_sheets"]:
                assert p.value(s.case, ts["terms"]) >= p.full_cost - 1e-6  # never below its floor
            assert "{PRICE}" not in m["body"] and "€€" not in m["body"]
    assert brain.calls > 0 and result["llm_fail"] == 0


def test_llm_supplier_does_not_walk_without_a_reason():
    s = _scenario("P01")
    table = LocalTable(s, {}, seed=0, supplier="llm", brain=_FakeBrain({"decision": "walk_away", "email": "Bye."}))
    case, _ = table.open()
    sheet = {"unit_price": 130.0, "effective_date": "2027-01-01", "payment_days": 30}
    reply = table.send(case["suppliers"][0], {"body": "Thank you for your offer.", "term_sheets": [{"terms": sheet}]})
    assert reply["status"] != "walked_away"


def test_llm_supplier_failure_falls_back_to_the_engine_and_is_counted():
    from sellm.lab.table import play_lab

    class Broken:
        def ask(self, system, user):
            raise RuntimeError("the LLM is down")

    result = play_lab(LocalTable(_scenario("P01"), {}, seed=0, supplier="llm", brain=Broken()), NaiveAgent())
    assert result["llm_fail"] > 0 and 0.0 <= result["score"] <= 1.0


def test_a_lowball_opening_gets_a_smaller_first_counter_and_an_earlier_final_offer():
    import copy

    s = _scenario("D01")
    persona = copy.copy(s.personas["sup:DEMO-F1"])
    persona.noise = 0.0
    terms = {"payment_days": 30, "contract_months": 24, "effective_date": "2027-02-01"}

    def play(start, step):
        bot = SupplierThread(persona, s.case, random.Random(0))
        bot.opening()
        first, n, price = None, 0, start
        while bot.status == "open" and n < 10:
            bot.respond({"body": "", "term_sheets": [{"terms": {**terms, "unit_price": price}}]})
            first = bot.a0 - bot.ask if first is None else first
            n, price = n + 1, price + step
        return first, n

    low_first, low_n = play(40.5, 2.0)  # 16 % below its floor, as the lab-best Calculator did on D01
    mod_first, mod_n = play(47.0, 0.6)  # a few percent below, as the scripts that scored 0.95
    assert low_first < mod_first and low_n < mod_n
