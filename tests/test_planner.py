# ruff: noqa: E501  (the wants are written out)
"""The planner (`sellm/planner.py`): the model names what a supplier would give price for, code
checks it and acts on two measured kinds. No network here: the LLM call is replaced by a function."""

import glob
import json
from pathlib import Path

import pytest

from sellm import llm, planner
from sellm.agent import KNOBS
from sellm.endgame import Persistent
from sellm.negotiator import Thread

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "package"


@pytest.fixture(scope="module")
def package():
    if not DATA.is_dir():
        pytest.skip("needs the data package")
    from arena_kit.data import DataPackage

    return DataPackage(DATA)


def opening(case_id):
    files = sorted(glob.glob(str(ROOT / "runs" / "practice" / case_id / "*.json")))
    if not files:
        pytest.skip(f"no saved session of {case_id}")
    rec = json.loads(Path(files[-1]).read_text(encoding="utf-8"))
    case = rec["case"]
    sid = case["suppliers"][0]
    return case, sid, {s: t["messages"][:1] for s, t in rec["threads"].items()}


def fake(monkeypatch, tmp_path, answers):
    """`answers`: one dict per call, in turn (the last one repeats); an Exception is raised instead."""
    calls = []

    def chat_json(system, user, timeout_s=20.0):
        answer = answers[min(len(calls), len(answers) - 1)]
        calls.append(user)
        if isinstance(answer, Exception):
            raise answer
        return answer, 0.1

    monkeypatch.setattr(llm, "chat_json", chat_json)
    monkeypatch.setattr(llm, "configured", lambda: True)
    monkeypatch.setenv("SELLM_PLANS", str(tmp_path / "plans"))
    monkeypatch.setenv("SELLM_STRICT", "1")
    return calls


CLAUSE = {
    "field": "index_clause",
    "option": "B",
    "evidence": "CU-NOTATION rose 47.7 % in twelve months and is 20 % of our cost.",
    "because": "x",
}
FAST = {"field": "payment_days", "option": "A", "evidence": "Zahlungsziel 30 days net", "because": "x"}


def test_a_want_needs_a_real_option_and_a_passage_of_the_material():
    case, sid, threads = opening("P02")
    view = Thread(case, sid, threads[sid])
    quoted = view.filled(view.opening["term_sheets"][0]["terms"])
    text = planner.brief(case, view.opening, {}, quoted)
    answer = {
        "wants": [
            CLAUSE,
            {
                "field": "index_clause",
                "option": "B",
                "evidence": "the supplier told us on the phone it loves clauses",
                "because": "x",
            },
        ]
    }
    plan = planner.check(answer, case, quoted, text)
    assert [w["field"] for w in plan["wants"]] == ["index_clause"] and plan["wants"][0]["value"]["deadband_pct"] == 0
    assert [d["why"] for d in plan["dropped"]] == ["evidence is not in the material"]
    for bad, why in (
        ({**CLAUSE, "field": "colour"}, "no such field or option"),
        ({**CLAUSE, "option": "Z"}, "no such field or option"),
        ({**CLAUSE, "option": "A"}, "that is what it quotes already"),
    ):
        assert planner.check({"wants": [bad]}, case, quoted, text)["dropped"][0]["why"] == why


def test_two_of_three_calls_must_agree_and_the_plan_is_kept(monkeypatch, tmp_path):
    case, sid, threads = opening("P02")
    view = Thread(case, sid, threads[sid])
    quoted = view.filled(view.opening["term_sheets"][0]["terms"])
    calls = fake(monkeypatch, tmp_path, [{"wants": [CLAUSE, FAST]}, {"wants": [CLAUSE]}, {"wants": []}])
    wants = planner.voted(case, view.opening, {"supplier_id": sid}, quoted)
    assert (
        set(wants) == {"index_clause"}
        and wants["index_clause"]["votes"] == 2
        and wants["index_clause"]["direction"] == "clause"
    )
    assert len(calls) == 3
    again = planner.voted(case, view.opening, {"supplier_id": sid}, quoted)
    assert again == wants and len(calls) == 3, "the second time the plan comes from disk"


def test_no_answer_is_no_plan_and_nothing_is_kept(monkeypatch, tmp_path):
    case, sid, threads = opening("P02")
    view = Thread(case, sid, threads[sid])
    quoted = view.filled(view.opening["term_sheets"][0]["terms"])
    fake(monkeypatch, tmp_path, [llm.LLMError("no answer within 12 s")])
    assert planner.voted(case, view.opening, {"supplier_id": sid}, quoted) == {}
    assert not list((tmp_path / "plans").glob("*.json"))


def test_without_a_plan_the_agent_plays_as_without_the_planner(package, monkeypatch, tmp_path):
    for answers in ([llm.LLMError("down")], [{"wants": []}], [{"nonsense": 1}]):
        fake(monkeypatch, tmp_path, answers)
        for case_id in ("P01", "P02", "P05", "P08"):
            case, _, threads = opening(case_id)
            for sid in threads:
                with_plan = Persistent(package, **{**KNOBS, "plan": "llm"}).decide(case, threads, focus=sid)
                assert with_plan == Persistent(package, **KNOBS).decide(case, threads, focus=sid), case_id


def test_the_planner_alone_finds_the_clause_and_the_fast_payment(package, monkeypatch, tmp_path):
    """With the dossier's own triggers switched off (`plan_only`), the wants give the same first e-mail
    as the rules: P02 the clause sheet at the same price, P01 the fastest payment."""
    fake(monkeypatch, tmp_path, [{"wants": [CLAUSE]}])
    case, sid, threads = opening("P02")
    ruled = Persistent(package, **KNOBS).decide(case, threads)
    assert len(ruled["message"]["term_sheets"]) == 2
    assert Persistent(package, **{**KNOBS, "plan": "llm", "plan_only": True}).decide(case, threads) == ruled
    alone = Persistent(package, **{**KNOBS, "plan_only": True}).decide(case, threads)
    assert len(alone["message"]["term_sheets"]) == 1, "no plan and no rule: no clause"
    case, sid, threads = opening("P01")
    view = Thread(case, sid, threads[sid])
    quoted = view.filled(view.opening["term_sheets"][0]["terms"])
    passage = max((view.opening.get("body") or "").split("\n"), key=len).strip()
    days = sorted(case["term_options"]["payment_days"])
    letter = chr(65 + case["term_options"]["payment_days"].index(days[0]))
    fake(
        monkeypatch,
        tmp_path,
        [{"wants": [{"field": "payment_days", "option": letter, "evidence": passage, "because": "x"}]}],
    )
    assert days[0] < quoted["payment_days"]
    ruled = Persistent(package, **KNOBS).decide(case, threads)
    assert ruled["message"]["term_sheets"][0]["terms"]["payment_days"] == days[0]
    assert Persistent(package, **{**KNOBS, "plan": "llm", "plan_only": True}).decide(case, threads) == ruled
    slow = Persistent(package, **{**KNOBS, "plan_only": True}).decide(case, threads)
    assert slow["message"]["term_sheets"][0]["terms"]["payment_days"] > days[0]


def test_a_clause_want_does_nothing_without_a_relationship_term(package, monkeypatch, tmp_path):
    """P08, P18: offered in the first ask the clause scored 0.39-0.53 against 0.47-0.55 (Sun 02:50)."""
    for case_id in ("P08", "P18"):
        case, sid, threads = opening(case_id)
        view = Thread(case, sid, threads[sid])
        passage = max((view.opening.get("body") or "").split("\n"), key=len).strip()
        fake(
            monkeypatch,
            tmp_path,
            [{"wants": [{"field": "index_clause", "option": "B", "evidence": passage, "because": "x"}]}],
        )
        planned = Persistent(package, **{**KNOBS, "plan": "llm"})
        assert planned.decide(case, threads) == Persistent(package, **KNOBS).decide(case, threads)
        assert planned.wants(case, view), "the want was read, and logged only"


# -- index arguments (experiments/LEDGER-JONATHAN.md J1-J3) -------------------------------------------


def first_two_facts(package, case, sid, threads, **knobs):
    """The index sentences of our first two e-mails, the second from the recorded reply."""
    from sellm.endgame import IDX_LINE

    out = []
    for upto in (1, 3):
        events = threads[sid][:upto]
        if len(events) < upto:
            break
        body = Persistent(package, **{**KNOBS, **knobs}).decide(case, {sid: events})["message"].get("body") or ""
        out.append(
            next(
                (s.strip() + "." for s in body.replace("\n", " ").split(". ") if IDX_LINE.match(s.strip() + ".")), None
            )
        )
    return out


def session(case_id, label):
    files = sorted(glob.glob(str(ROOT / "runs" / "practice" / case_id / "*.json")))
    recs = [json.loads(Path(f).read_text(encoding="utf-8")) for f in files]
    recs = [r for r in recs if label in (r.get("label") or "")]
    if not recs:
        pytest.skip(f"no saved session of {case_id} labelled {label}")
    rec = recs[-1]
    sid = rec["case"]["suppliers"][0]
    return rec["case"], sid, {sid: rec["threads"][sid]["messages"]}


def test_every_fallen_cost_driver_index_is_cited_one_per_email(package):
    """P18: the alloy surcharge first, then the producer price of cold-drawn bars (0.520 -> 0.598)."""
    case, sid, threads = session("P18", "ARG idx2")
    one = first_two_facts(package, case, sid, threads, idx_many=1)
    many = first_two_facts(package, case, sid, threads)
    assert "AS-14404" in one[0] and one[1] is None
    assert "AS-14404" in many[0] and "PPI-C2431" in many[1] and "-2.3 %" in many[1]


def test_a_hedge_covers_the_material_of_its_clause_only(package):
    """P08: 'our AS-14404 is covered at fixed prices' - but it took the fall of PPI-C2431 (0.549 -> 0.637)."""
    case, sid, threads = session("P08", "ARG agent-idx")
    assert first_two_facts(package, case, sid, threads, idx_many=1)[0] is None
    first = first_two_facts(package, case, sid, threads)[0]
    assert first and "PPI-C2431" in first and "AS-14404" not in first


def test_an_index_the_supplier_blames_is_cited_with_its_larger_fall(package, monkeypatch, tmp_path):
    """P01: its letter blames energy; PPI-D351 fell 6.1 % from its peak and 3.7 % over the year (0.969 -> 0.997).
    Without a blame - P11 gave no reason - the yearly sentence stays (the larger one lost its close there)."""
    case, sid, threads = opening("P01")
    passage = "Owing to sustained increases in energy, raw material and wage costs"
    fake(monkeypatch, tmp_path, [{"wants": [], "blames": [{"series": "PPI-D351", "evidence": passage}]}])
    body = Persistent(package, **{**KNOBS, "plan": "llm"}).decide(case, threads)["message"]["body"]
    assert "PPI-D351 changed -6.1 % from 2025-11 to 2026-08" in body
    plain = Persistent(package, **KNOBS).decide(case, threads)["message"]["body"]
    assert "PPI-D351 changed -3.7 % from 2025-08 to 2026-08" in plain
    fake(
        monkeypatch,
        tmp_path / "b",
        [{"wants": [], "blames": [{"series": "PPI-D351", "evidence": "the bank told us so"}]}],
    )
    assert Persistent(package, **{**KNOBS, "plan": "llm"}).decide(case, threads)["message"]["body"] == plain
    case, sid, threads = opening("P11")
    fake(monkeypatch, tmp_path / "c", [{"wants": [], "blames": []}])
    body = Persistent(package, **{**KNOBS, "plan": "llm"}).decide(case, threads)["message"]["body"]
    assert "PPI-D351 changed -3.7 %" in body


def test_the_planner_does_not_overrule_the_dossiers_cash_reading(package, monkeypatch, tmp_path):
    """P03: 'He was open on payment terms' was read as a wish for faster payment in 2 of 3 calls (Sun 03:20);
    the dossier calls this supplier relaxed about cash, and that decides."""
    case, sid, threads = opening("P03")
    view = Thread(case, sid, threads[sid])
    quoted = view.filled(view.opening["term_sheets"][0]["terms"])
    days = sorted(case["term_options"]["payment_days"])
    letter = chr(65 + case["term_options"]["payment_days"].index(days[0]))
    passage = max((view.opening.get("body") or "").split("\n"), key=len).strip()
    fake(
        monkeypatch,
        tmp_path,
        [{"wants": [{"field": "payment_days", "option": letter, "evidence": passage, "because": "x"}]}],
    )
    planned = Persistent(package, **{**KNOBS, "plan": "llm"})
    decision = planned.decide(case, threads)
    assert planned.wants(case, view)["payment_days"]["direction"] == "lower" and days[0] < quoted["payment_days"]
    assert decision == Persistent(package, **KNOBS).decide(case, threads)
