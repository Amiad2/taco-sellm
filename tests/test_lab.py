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
