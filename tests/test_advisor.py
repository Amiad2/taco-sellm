"""The LLM layer (`sellm/advisor.py`): the model writes and gives a verdict, code keeps every number
and every accept. No network here: the two LLM calls are replaced by functions."""

import glob
import json
import math
from pathlib import Path

import pytest

from sellm import advisor, llm
from sellm.advisor import Advised, probability
from sellm.agent import KNOBS
from sellm.endgame import Persistent

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "package"


@pytest.fixture(scope="module")
def package():
    if not DATA.is_dir():
        return None
    from arena_kit.data import DataPackage

    return DataPackage(DATA)


def record(case_id):
    files = sorted(glob.glob(str(ROOT / "runs" / "practice" / case_id / "*.json")))
    records = [json.loads(Path(f).read_text(encoding="utf-8")) for f in files]
    records = [r for r in records if "v1.4 (argument bank" in (r.get("label") or "")]
    if not records:
        pytest.skip(f"no saved session of {case_id}")
    return records[-1]


def state(case_id, status="open", nth=2):
    rec = record(case_id)
    case = rec["case"]
    sid = case["suppliers"][0]
    messages = rec["threads"][sid]["messages"]
    hits = [
        i
        for i, m in enumerate(messages)
        if m.get("from") != "buyer" and not m.get("action") and m.get("status") == status
    ]
    i = hits[min(nth, len(hits) - 1)]
    return case, sid, {sid: messages[: i + 1]}


def fake(monkeypatch, tmp_path, letter="B", p=0.99, fail=False, writer_fails=True):
    def chat_tools(system, user, tools, handlers, timeout_s=12.0, max_rounds=2):
        if fail:
            raise llm.LLMError("no answer within 12 s")
        handlers["cost_of_price"](unit_price=1.0)  # the tools must work on any state
        handlers["supplier_profile"]()
        handlers["facts_left"]()
        other = "A" if letter == "B" else "B"
        first = [{"token": letter, "logprob": math.log(p)}, {"token": other, "logprob": math.log(max(1e-9, 1 - p))}]
        return f"{letter} - because.", [{"tool": "cost_of_price", "args": {"unit_price": 1.0}}], first, 0.1

    def chat_json(system, user, timeout_s=20.0):
        if writer_fails:
            raise llm.LLMError("writer off in this test")
        return {"body": "x"}, 0.1

    monkeypatch.setattr(llm, "chat_tools", chat_tools)
    monkeypatch.setattr(llm, "chat_json", chat_json)
    monkeypatch.setenv("SELLM_TRACE", str(tmp_path / "trace.jsonl"))
    monkeypatch.setenv("SELLM_STRICT", "1")
    return tmp_path / "trace.jsonl"


def moves(decision):
    message = decision["message"]
    return decision["supplier_id"], message.get("action"), message.get("term_sheets")


def test_the_probability_is_read_from_the_tokens_not_asked():
    first = [{"token": "A", "logprob": math.log(0.8)}, {"token": " B", "logprob": math.log(0.2)}]
    assert probability("A - take it", first) == ("A", pytest.approx(0.8))
    assert probability("b - go on", first) == ("B", pytest.approx(0.2))
    assert probability("Maybe", first) == (None, None)
    assert probability("A", []) == ("A", None)


def test_shadow_never_changes_a_move(package, monkeypatch, tmp_path):
    for letter in ("A", "B"):
        trace = fake(monkeypatch, tmp_path, letter=letter, p=0.999)
        for case_id, status in (("P08", "open"), ("P08", "final_offer"), ("P01", "open")):
            case, _, threads = state(case_id, status)
            plain = Persistent(package, **KNOBS).decide(case, threads)
            advised = Advised(package, verdict="shadow", **KNOBS).decide(case, threads)
            assert moves(advised) == moves(plain)
        lines = [json.loads(line) for line in trace.read_text(encoding="utf-8").splitlines()]
        assert lines and all(r["verdict"] == letter and r["applied"] is False for r in lines)
        trace.unlink()


def test_apply_takes_a_sure_a_before_the_final_offer_only(package, monkeypatch, tmp_path):
    case, sid, threads = state("P08", "open")
    fake(monkeypatch, tmp_path, letter="A", p=0.95)
    sure = Advised(package, verdict="apply", **KNOBS).decide(case, threads)
    assert sure["message"]["action"]["type"] == "accept"
    fake(monkeypatch, tmp_path, letter="A", p=0.70)
    unsure = Advised(package, verdict="apply", **KNOBS).decide(case, threads)
    assert moves(unsure) == moves(Persistent(package, **KNOBS).decide(case, threads))
    fake(monkeypatch, tmp_path, letter="B", p=0.99)  # "keep negotiating" after a final offer is never acted on
    case, sid, threads = state("P08", "final_offer")
    final = Advised(package, verdict="apply", **KNOBS).decide(case, threads)
    assert final["message"]["action"]["type"] == "accept"


def test_apply_never_takes_the_opening(package, monkeypatch, tmp_path):
    """An offer no better than the opening scores nothing: the verdict cannot make us take it."""
    rec = record("P04")
    case = rec["case"]
    sid = case["suppliers"][0]
    threads = {sid: rec["threads"][sid]["messages"][:1]}
    fake(monkeypatch, tmp_path, letter="A", p=0.999)
    decision = Advised(package, verdict="apply", **KNOBS).decide(case, threads)
    assert decision["message"].get("term_sheets") and not decision["message"].get("action")


def test_a_failing_model_costs_nothing(package, monkeypatch, tmp_path):
    trace = fake(monkeypatch, tmp_path, fail=True)
    case, _, threads = state("P01", "open")
    plain = Persistent(package, **KNOBS).decide(case, threads)
    advised = Advised(package, verdict="apply", **KNOBS).decide(case, threads)
    assert advised == plain, "no verdict and no LLM e-mail: the code's move with the template's text"
    assert json.loads(trace.read_text(encoding="utf-8").splitlines()[0])["verdict"] is None


def test_the_agent_calls_no_model_unless_asked(monkeypatch):
    from sellm.agent import make_agent

    monkeypatch.delenv("SELLM_LLM", raising=False)
    assert type(make_agent()) is Persistent
    monkeypatch.setenv("SELLM_LLM", "shadow")
    assert isinstance(make_agent(), Advised) and make_agent().verdict_mode == "shadow"
    assert advisor.TRACE.name == "advisor-trace.jsonl"
