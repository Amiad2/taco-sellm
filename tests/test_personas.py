"""The personas (`sellm/personas.py`) describe the rules; they must say what the agent really does."""

import glob
import json
from pathlib import Path

import pytest

from arena_kit.cost import RELATIONSHIP_GOALS
from sellm.agent import make_agent
from sellm.negotiator import TARGET_SHARE, Thread
from sellm.personas import PERSONAS, describe, traits

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "package"


@pytest.fixture(scope="module")
def package():
    if not DATA.is_dir():
        pytest.skip("no data package")
    from arena_kit.data import DataPackage

    return DataPackage(DATA)


def openings():
    seen = {}
    for path in sorted(
        glob.glob(str(ROOT / "runs" / "practice" / "*" / "*.json"))
        + glob.glob(str(ROOT / "runs" / "sandbox" / "*" / "*.json"))
    ):
        rec = json.loads(Path(path).read_text(encoding="utf-8"))
        seen[rec["case"]["case_id"]] = (rec["case"], {s: t["messages"][:1] for s, t in rec["threads"].items()})
    if not seen:
        pytest.skip("no saved sessions")
    return seen.values()


def test_a_dossier_gets_one_cash_persona_and_at_most_one_for_price():
    fixed = {"kind": "list_price_fixed", "strength": 3, "excerpt": "List conditions.", "evidence": ["doc:1"]}
    economics = {"cash_pressure": "low", "cost_of_money": 0.065, "cost_of_money_basis": "rule"}
    known = {"coverage": "full", "economics": economics, "signals": [fixed, {"kind": "wants_volume", "strength": 3}]}
    assert [p for p, _ in traits(known)] == ["relaxed_about_cash", "fixed_list_price"], (
        "a fixed list price goes before volume"
    )
    short = {
        **known,
        "signals": [
            {"kind": "cash_short", "strength": 1, "excerpt": "Pay within 10 days?"},
            {"kind": "wants_volume", "strength": 2},
        ],
    }
    assert [p for p, _ in traits(short)] == ["short_of_cash", "hungry_for_volume"]
    assert [p for p, _ in traits({"coverage": "case_only"})] == ["unknown"] == [p for p, _ in traits(None)]
    info = describe(short)
    assert len(info["lines"]) == 2 and all(p in PERSONAS for p in info["personas"])
    assert "Pay within 10 days?" in info["lines"][0]


def test_the_description_matches_the_first_ask(package):
    """For every supplier we have played: the payment days and the depth of the first ask are the
    ones its personas announce."""
    checked = set()
    for case, threads in openings():
        relationship = case["buyer"].get("category_goal") in RELATIONSHIP_GOALS
        for sid in threads:
            agent = make_agent(package)
            sheets = [s["terms"] for s in agent.decide(case, threads, focus=sid)["message"]["term_sheets"]]
            view = Thread(case, sid, threads[sid])
            personas = agent.persona(case, view)["personas"]
            options = case.get("term_options", {}).get("payment_days") or []
            quoted = view.filled(view.opening["term_sheets"][0]["terms"]).get("payment_days")
            if options and "payment_days" in sheets[0]:
                if "short_of_cash" in personas:
                    assert sheets[0]["payment_days"] == min(options), (case["case_id"], sid)
                if "relaxed_about_cash" in personas:
                    assert sheets[0]["payment_days"] == max(options), (case["case_id"], sid)
                if personas == ["unknown"]:
                    assert (
                        sheets[0]["payment_days"] == quoted
                        and len(sheets) == 2
                        and sheets[1]["payment_days"] == max(options)
                    )
            share = agent.share(case, view, relationship)
            if "fixed_list_price" in personas:
                assert share == 0.96
            elif "hungry_for_volume" in personas:
                assert share == 0.84
            else:
                assert share == TARGET_SHARE[relationship]
            checked.update(personas)
    assert {"short_of_cash", "relaxed_about_cash", "fixed_list_price", "hungry_for_volume", "unknown"} <= checked


def test_known_suppliers(package):
    from sellm.intel import dossier

    assert [p for p, _ in traits(dossier("sup:70110"))] == ["short_of_cash", "fixed_list_price"]
    assert [p for p, _ in traits(dossier("sup:70620"))] == ["relaxed_about_cash", "fixed_list_price"]
    assert [p for p, _ in traits(dossier("sup:70740"))] == ["relaxed_about_cash", "hungry_for_volume"]
    assert [p for p, _ in traits(dossier("sup:DEMO-F1"))] == ["unknown"]
