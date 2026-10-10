"""The persistence layer (`sellm/endgame.py`): with its knobs off it is the negotiator; with them on
it changes only when we stop and how far a step goes. Replayed on the sessions in runs/."""

import glob
import inspect
import json
from pathlib import Path

import pytest

from sellm.agent import make_agent
from sellm.endgame import DEFAULTS
from sellm.endgame import make_agent as make_persistent
from sellm.negotiator import Negotiator, Thread

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "package"


@pytest.fixture(scope="module")
def package():
    if not DATA.is_dir():
        return None
    from arena_kit.data import DataPackage

    return DataPackage(DATA)


@pytest.fixture(autouse=True)
def strict(monkeypatch):
    monkeypatch.setenv("SELLM_STRICT", "1")


def record(case_id, label=None):
    files = sorted(glob.glob(str(ROOT / "runs" / "*" / case_id / "*.json")))
    records = [json.loads(Path(f).read_text(encoding="utf-8")) for f in files]
    if label:
        records = [r for r in records if label in (r.get("label") or "")]
    if not records:
        pytest.skip(f"no saved session of {case_id}")
    return records[-1]


def states(rec):
    """Every state of a single-supplier session at which we had to decide."""
    case = rec["case"]
    sid = case["suppliers"][0]
    messages = rec["threads"][sid]["messages"]
    for i, m in enumerate(messages):
        if m.get("from") != "buyer" and not m.get("action") and m.get("status") != "agreed":
            yield case, sid, {sid: messages[: i + 1]}


def test_the_seam_to_the_negotiator_is_there(package):
    """The layer overrides `plan` and reads these: a rename in the negotiator must fail here, not in a session."""
    for name in ("plan", "opening_structure", "aim", "value", "supplier", "quoted"):
        assert callable(getattr(Negotiator, name)), name
    assert list(inspect.signature(Negotiator.plan).parameters) == ["self", "case", "v", "rival"]
    case, sid, threads = next(states(record("P01")))
    agent = make_agent(package)
    view = Thread(case, sid, threads[sid])
    agent.move(case, threads)
    assert {"sheet", "capped", "enough", "structure", "target"} <= set(agent.plan(case, view))
    assert {"target", "full_cost"} <= set(agent.aim(case, view, agent.opening_structure(case, view)))


def test_with_its_knobs_off_it_plays_exactly_like_the_negotiator(package):
    assert not any(DEFAULTS[k] for k in ("past_target", "creep"))
    for case_id in ("P01", "P08", "P11", "D01"):
        for case, _, threads in states(record(case_id)):
            assert make_persistent(package).decide(case, threads) == make_agent(package).decide(case, threads)


def test_past_target_keeps_asking_where_the_negotiator_accepts(package):
    """P01 at the supplier's 135.10: the negotiator accepts (target reached), the layer asks on,
    below its price and not below our own last ask."""
    rec = record("P01", "v1.4 (argument bank")
    case = rec["case"]
    sid = case["suppliers"][0]
    messages = rec["threads"][sid]["messages"]
    stop = next(i for i, m in enumerate(messages) if (m.get("action") or {}).get("type") == "accept")
    threads = {sid: messages[:stop]}
    plain = make_agent(package).decide(case, threads)["message"]
    if not plain.get("action"):
        pytest.skip("the negotiator no longer stops here")
    asked = make_persistent(package, past_target=True).decide(case, threads)["message"]
    view = Thread(case, sid, threads[sid])
    price = asked["term_sheets"][0]["terms"]["unit_price"]
    assert view.asks[-1]["unit_price"] <= price < view.standing[1]["unit_price"]


def test_past_target_still_accepts_a_final_offer(package):
    for case_id in ("P02", "P03"):
        rec = record(case_id)
        case = rec["case"]
        sid = case["suppliers"][0]
        messages = rec["threads"][sid]["messages"]
        final = next((i for i, m in enumerate(messages) if m.get("status") == "final_offer"), None)
        if final is None:
            continue
        decision = make_persistent(package, past_target=True, creep=0.25).decide(case, {sid: messages[: final + 1]})
        assert (decision["message"].get("action") or {}).get("type") == "accept"


def test_creep_never_steps_further_than_its_share_of_the_gap(package):
    """Every ask after the first: at or above our last one, and no more than a quarter of the way
    to the price the supplier quotes for that structure (or the smallest visible step)."""
    checked = 0
    for case_id in ("P01", "P04", "P07", "P08", "P11", "P18", "D01"):
        for case, sid, threads in states(record(case_id)):
            view = Thread(case, sid, threads[sid])
            if not view.asks:
                continue
            agent = make_persistent(package, creep=0.25)
            message = agent.decide(case, threads)["message"]
            if message.get("action") or not message.get("term_sheets"):
                continue
            sheet = message["term_sheets"][0]["terms"]
            last = view.asks[-1]
            same = all(sheet[f] == last.get(f) for f in sheet if f != "unit_price")
            quoted = view.filled(view.standing[1])
            if not same or any(quoted.get(f) != sheet[f] for f in sheet if f != "unit_price"):
                continue
            gap = quoted["unit_price"] - last["unit_price"]
            assert last["unit_price"] <= sheet["unit_price"] < quoted["unit_price"]
            assert sheet["unit_price"] - last["unit_price"] <= max(0.25 * gap, 0.01) + 0.006, (
                case_id,
                last["unit_price"],
                sheet["unit_price"],
                quoted["unit_price"],
            )
            plain = make_agent(package).decide(case, threads)["message"]
            if plain.get("term_sheets"):
                assert sheet["unit_price"] <= plain["term_sheets"][0]["terms"]["unit_price"] + 0.006
            checked += 1
    assert checked >= 10
