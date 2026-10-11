# ruff: noqa: E501  (long test data lines)
"""sellm2's decisions on every state of every session the team played (runs/), and on states made up
to hit the rules the arena taught us: valid moves only, a pure function of the threads, never a push
after a final offer, never a deal thrown away."""

import copy
import math
import threading

import pytest

from arena_kit.cost import complete_offer, must_haves_ok, total_cost
from sellm2.agent import make_agent
from sellm2.model import CaseModel, Thread
from sellm2.replay import replay

from .conftest import records, states

MEASURED = "67001e7"  # the 74.9 run of jonathans_branch: sellm2 must play its moves where nothing new applies


def check(case, threads, decision):
    sid, msg = decision["supplier_id"], decision["message"]
    assert sid in threads
    v = Thread(CaseModel(case), sid, threads[sid])
    if msg.get("action"):
        if msg["action"]["type"] == "accept":
            assert msg["action"]["term_sheet_id"] == v.standing[0], "only the first sheet can be accepted"
        return
    assert len(msg["body"]) <= 8000 and len(msg["subject"]) <= 300
    assert len(msg["term_sheets"]) <= 3
    for s in msg["term_sheets"]:
        t = s["terms"]
        assert set(t) == set(case["negotiable"]), "exactly the negotiable fields"
        for f, x in t.items():
            opts = (case.get("term_options") or {}).get(f)
            if f != "unit_price" and opts:
                assert x in opts or x == v.std.get(f), (f, x)
        assert t["unit_price"] > 0 and must_haves_ok(case, t, v.std)
        assert f"{t['unit_price']:.2f}" in msg["body"], "the price in the text is the price in the sheet"


def test_every_recorded_state_gets_a_valid_move(pkg):
    n = 0
    for r in records():
        for sid, threads in states(r):
            check(r["case"], threads, make_agent(pkg).decide(r["case"], threads, focus=sid if len(threads) > 1 else None))
            n += 1
    assert n > 1000


def test_a_move_is_a_pure_function_of_the_threads(pkg):
    for r in records()[::7]:
        for _sid, threads in states(r):
            a = make_agent(pkg).decide(r["case"], copy.deepcopy(threads))
            b = make_agent(pkg).decide(r["case"], copy.deepcopy(threads))
            assert a == b


def test_never_asks_after_a_final_offer_and_never_walks_from_a_deal_that_beats_the_alternative(pkg):
    """A push after final_offer lost the deal 3 of 5 times (P04, P08, P02 x5 withdrew)."""
    n = 0
    for r in records():
        case = r["case"]
        for sid, threads in states(r):
            if len(threads) > 1 or threads[sid][-1].get("status") != "final_offer":
                continue
            d = make_agent(pkg).decide(case, threads)
            msg = d["message"]
            if msg.get("term_sheets"):  # only its own alternative sent back may follow a final offer
                v = Thread(CaseModel(case), sid, threads[sid])
                theirs = [v.filled(s["terms"]) for s in v.sheets]
                assert complete_offer(case, msg["term_sheets"][0]["terms"]) in theirs
            elif not msg.get("action"):
                continue  # a holding e-mail
            else:
                n += 1
                if msg["action"]["type"] == "walk_away":
                    alt = case["buyer"].get("alternative") or {}
                    c_alt = total_cost(case, alt["terms"]) if (alt.get("terms") or {}).get("unit_price") else math.inf
                    v = Thread(CaseModel(case), sid, threads[sid])
                    assert c_alt < v.c(v.filled(v.standing[1]))
    assert n > 20


def test_our_price_never_goes_back_on_an_unchanged_structure(pkg):
    for r in records():
        case = r["case"]
        for sid, threads in states(r):
            v = Thread(CaseModel(case), sid, threads[sid])
            d = make_agent(pkg).decide(case, threads, focus=sid if len(threads) > 1 else None)
            if d["supplier_id"] != sid or not v.asks or not d["message"].get("term_sheets"):
                continue
            ours = complete_offer(case, d["message"]["term_sheets"][0]["terms"])
            last = complete_offer(case, v.asks[-1])
            if {k: x for k, x in ours.items() if k != "unit_price"} == {k: x for k, x in last.items() if k != "unit_price"}:
                assert ours["unit_price"] >= last["unit_price"] - 1e-9


@pytest.mark.parametrize("case_id", ["P03", "P04"])
def test_a_fixed_list_price_that_repeats_is_asked_just_below(pkg, case_id):
    """P03/P04: up to the supplier's repeated price the measured moves; then one ask 0.2 % below it."""
    recs = [r for r in records(MEASURED) if r["case_id"] == f"case:{case_id}"]
    if not recs:
        pytest.skip("the measured session is not in runs/")
    rows = replay(recs[0], lambda: make_agent(pkg))
    first = next(i for i, row in enumerate(rows) if row[2] != row[3])
    assert all(row[4] for row in rows[:first])
    v = Thread(CaseModel(recs[0]["case"]), rows[first][0], recs[0]["threads"][rows[first][0]]["messages"][: rows[first][1]])
    quoted = v.standing[1]["unit_price"]
    assert rows[first][3][1][0][0] == round(quoted * (1 - 0.002), 2)


@pytest.mark.parametrize("case_id", ["P01", "P02", "P07", "P08", "P11"])
def test_the_measured_moves_are_kept_where_no_new_rule_applies(pkg, case_id):
    """Practice suppliers answer identical e-mails identically: these cases then score what the
    measured runs scored (P01 0.969, P02 0.725, P07 0.747, P08 0.549, P11 0.778)."""
    recs = [r for r in records(MEASURED) if r["case_id"] == f"case:{case_id}"]
    if not recs:
        pytest.skip("the measured session is not in runs/")
    rows = replay(recs[0], lambda: make_agent(pkg))
    assert rows and all(rec == ours and same for _, _, rec, ours, same in rows), [r for r in rows if r[2] != r[3] or not r[4]][:2]


def test_works_without_any_data(pkg):
    """A supplier we hold nothing on, or a machine without the package: still a valid move."""
    for r in records()[:40]:
        for _sid, threads in list(states(r))[:3]:
            check(r["case"], threads, make_agent(None).decide(r["case"], threads))
            check(r["case"], threads, make_agent(pkg, data=False).decide(r["case"], threads))


def test_a_bug_in_our_code_becomes_a_safe_move(pkg, monkeypatch):
    monkeypatch.setenv("SELLM_STRICT", "0")
    agent = make_agent(pkg)
    monkeypatch.setattr(agent.policy, "move", lambda *a, **k: 1 / 0)
    r = records()[0]
    sid, threads = next(states(r))
    d = agent.decide(r["case"], threads)
    assert d["supplier_id"] in threads and (d["message"].get("action") or d["message"]["term_sheets"] == [])
    assert agent.stats["errors"] == 1


def test_rfq_with_focus_moves_in_that_thread_while_it_has_something_to_ask(pkg):
    n = 0
    for r in [r for r in records() if len(r["threads"]) > 1][:6]:
        for sid, threads in states(r):
            agent = make_agent(pkg)
            cm = CaseModel(r["case"])
            v = Thread(cm, sid, threads[sid])
            if not v.live or agent.policy.ready(cm, v):
                continue
            d = agent.decide(r["case"], threads, focus=sid)
            if not d["message"].get("action"):
                n += 1
                assert d["supplier_id"] == sid
    assert n > 5


def test_cases_decided_at_the_same_time_decide_as_they_do_alone(pkg):
    """One package and one cache serve ten cases at once in the final."""
    firsts = [(r["case"], {s: t["messages"][:1] for s, t in r["threads"].items()}) for r in records(MEASURED)]
    alone = [make_agent(pkg).decide(c, t) for c, t in firsts]
    out, lock = [None] * len(firsts), threading.Lock()

    def one(i):
        d = make_agent(pkg).decide(*firsts[i])
        with lock:
            out[i] = d

    for _ in range(3):
        ts = [threading.Thread(target=one, args=(i,)) for i in range(len(firsts))]
        [t.start() for t in ts]
        [t.join() for t in ts]
        assert out == alone


def test_the_email_names_the_person_and_carries_one_checked_fact(pkg):
    r = next(r for r in records(MEASURED) if r["case_id"] == "case:P01")
    threads = {s: t["messages"][:1] for s, t in r["threads"].items()}
    body = make_agent(pkg).decide(r["case"], threads)["message"]["body"]
    assert body.startswith("Dear Thomas Brandlhuber,")
    assert "idx:PPI-D351@" in body and body.count("idx:") == 2  # one fact: the falling electricity index


def test_hidden_case_shapes_never_break(pkg):
    """Fields practice never negotiates (incoterm, tooling, ppm, volume, lead time, effective date), a
    price per 100 units, a short round limit, case facts and a stranger: valid first moves."""
    base = next(r for r in records(MEASURED) if r["case_id"] == "case:P01")
    case = copy.deepcopy(base["case"])
    opening = copy.deepcopy(base["threads"]["sup:70110"]["messages"][0])
    case["negotiable"] = ["unit_price", "payment_days", "effective_date", "incoterm", "tooling_eur", "lead_time_days"]
    case["term_options"].update({"incoterm": ["EXW", "FCA", "DAP"], "tooling_eur": [0.0, 5000.0], "lead_time_days": [21, 35, 49]})
    case["round_limit"] = 4
    case["facts"] = {"cost:H-1": {"part": case["parts"][0], "unit_cost": 120.0}}
    d = make_agent(pkg).decide(case, {"sup:70110": [opening]})
    check(case, {"sup:70110": [opening]}, d)
    opening2 = copy.deepcopy(opening)
    opening2["from"] = "sales@79999"
    d = make_agent(pkg).decide(case, {"sup:79999": [opening2]})
    check(case, {"sup:79999": [opening2]}, d)
