"""The persistence layer (`sellm/endgame.py`): with its knobs off it is the negotiator; with them on
it changes only when we stop and how far a step goes. Replayed on the sessions in runs/."""

import glob
import inspect
import json
from pathlib import Path

import pytest

from sellm.endgame import DEFAULTS, Persistent
from sellm.endgame import make_agent as make_persistent
from sellm.negotiator import Negotiator, Thread


def make_agent(package):
    """The negotiator alone, without the layer: the reference these tests compare with."""
    return Negotiator(package)


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


def test_the_agent_plays_the_rules_that_were_measured(package):
    """`--agent sellm`: past the relationship target, fast payment for a supplier short of cash, the clause offer."""
    from sellm.agent import KNOBS
    from sellm.agent import make_agent as the_agent

    assert KNOBS == {
        "past_target": True,
        "fast_pay": True,
        "clause_offer": True,
        "idx_recent": 2.0,
        "idx_many": 3,
        "idx_blamed": True,
    }
    agent = the_agent(package)
    assert isinstance(agent, Persistent) and agent.e["past_target"] and agent.e["fast_pay"] and agent.e["clause_offer"]
    assert not any(agent.e[k] for k in ("push_final", "pay_probe", "signal_facts", "soft_give", "creep", "zone"))
    if package is None:
        return
    rec = record("P01", "v1.4 (argument bank")
    case = rec["case"]
    sid = case["suppliers"][0]
    first = agent.decide(case, {sid: rec["threads"][sid]["messages"][:1]})["message"]["term_sheets"][0]["terms"]
    assert first["payment_days"] == 14, "the dossier holds this supplier's request for payment within ten days"


def test_no_ask_after_a_final_offer_by_default(package):
    """Measured Sat 23:15: one polite ask 1 % below a final offer and two of three suppliers withdrew."""
    from sellm.agent import make_agent as the_agent

    for case_id in ("P04", "P08", "P07"):
        rec = record(case_id, "v1.4 (argument bank")
        case = rec["case"]
        sid = case["suppliers"][0]
        messages = rec["threads"][sid]["messages"]
        final = next(i for i, m in enumerate(messages) if m.get("status") == "final_offer")
        decision = the_agent(package).decide(case, {sid: messages[: final + 1]})
        assert (decision["message"].get("action") or {}).get("type") == "accept"


# -- the clause offer (experiments/P02-ARGUMENTS.md) ---------------------------------------------------


def with_clause(package):
    from sellm.agent import KNOBS

    return make_persistent(package, **{**KNOBS, "clause_offer": True})


def without_clause(package):
    from sellm.agent import KNOBS

    return make_persistent(package, **{**KNOBS, "clause_offer": False})


def test_the_clause_offer_is_a_second_sheet_at_the_price_where_our_cost_is_lowest(package):
    """P02: the supplier quotes a fixed price, an index clause is negotiable, a relationship term applies."""
    if package is None:
        pytest.skip("needs the data package")
    rec = record("P02")
    case = rec["case"]
    sid = case["suppliers"][0]
    threads = {sid: rec["threads"][sid]["messages"][:1]}
    agent = with_clause(package)
    message = agent.decide(case, threads)["message"]
    plain = without_clause(package).decide(case, threads)["message"]
    assert len(plain["term_sheets"]) == 1 and plain["term_sheets"][0]["terms"]["index_clause"] is None
    first, second = (s["terms"] for s in message["term_sheets"])
    assert first == plain["term_sheets"][0]["terms"], "the fixed-price ask is the one we always sent"
    widest = max(o["deadband_pct"] for o in case["term_options"]["index_clause"] if o)
    assert second["index_clause"]["deadband_pct"] == widest, "the clause that costs us least"
    assert {f: x for f, x in second.items() if f not in ("unit_price", "index_clause")} == {
        f: x for f, x in first.items() if f not in ("unit_price", "index_clause")
    }
    view = Thread(case, sid, threads[sid])
    estimate = agent.estimate(case, view)
    here = view.c(second, estimate)
    for other in (-5.0, -1.0, 1.0, 5.0):  # dearer for us below (the relationship term) and above (the price)
        assert here < view.c({**second, "unit_price": second["unit_price"] + other}, estimate)
    even = estimate["full_cost"] / agent.value(case, view, {**second, "unit_price": 1.0})
    assert second["unit_price"] < even, "below the price that covers its cost: the clause is what it gets instead"
    assert "index clause" in message["body"] and str(second["unit_price"]) in message["body"]


def test_the_clause_offer_acts_only_with_a_relationship_term_and_a_clause_to_negotiate(package):
    """Every other recorded case is played move for move as without it."""
    seen = 0
    for case_id in ("P01", "P03", "P04", "P07", "P08", "P10", "P11", "P18", "D01"):
        for case, _, threads in states(record(case_id)):
            assert with_clause(package).decide(case, threads) == without_clause(package).decide(case, threads), case_id
            seen += 1
    assert seen >= 30


def test_a_clause_it_prices_too_low_is_neither_taken_nor_followed(package):
    """P02, Sun 01:55: asked for the clause at 343.47 it offered 351.45 and never went back up; taken,
    that scored 0.242 (relationship cost EUR 119,974) against 0.531 for its fixed price."""
    if package is None:
        pytest.skip("needs the data package")
    rec = record("P02", "ARG clause5-raise")
    case = rec["case"]
    sid = case["suppliers"][0]
    messages = rec["threads"][sid]["messages"]
    low = next(i for i, m in enumerate(messages) if m.get("from") != "buyer" and i and m.get("status") == "open")
    assert messages[low]["term_sheets"][0]["terms"]["index_clause"]
    plain = without_clause(package).decide(case, {sid: messages[: low + 1]})["message"]
    assert (plain.get("action") or {}).get("type") == "accept", "without the rule the low price looks like a gift"
    message = with_clause(package).decide(case, {sid: messages[: low + 1]})["message"]
    assert not message.get("action")
    assert message["term_sheets"][0]["terms"]["index_clause"] is None, "back to the fixed price"


def test_the_clause_at_our_price_is_accepted_once_it_agrees(package):
    if package is None:
        pytest.skip("needs the data package")
    rec = record("P02", "ARG clause5-direct")
    case = rec["case"]
    sid = case["suppliers"][0]
    messages = rec["threads"][sid]["messages"]
    agreed = next(i for i, m in enumerate(messages) if m.get("status") == "agreed")
    decision = with_clause(package).decide(case, {sid: messages[: agreed + 1]})["message"]
    assert decision["action"] == {
        "type": "accept",
        "term_sheet_id": messages[agreed]["term_sheets"][0]["term_sheet_id"],
    }
