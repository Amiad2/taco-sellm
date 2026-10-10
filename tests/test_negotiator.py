"""The negotiator (`sellm/negotiator.py`): every move is valid, a pure function of the thread, never
better for us than the one before, and it never throws a case away. Replayed on the real sessions
saved in runs/ (no network, no LLM)."""

import glob
import json
import os
from pathlib import Path

import pytest

from arena_kit.cost import RELATIONSHIP_GOALS, must_haves_ok, total_cost
from sellm.agent import make_agent
from sellm.negotiator import TARGET_SHARE, Negotiator, Thread

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "package"
SESSIONS = sorted(
    glob.glob(str(ROOT / "runs" / "practice" / "*" / "*.json"))
    + glob.glob(str(ROOT / "runs" / "sandbox" / "*" / "*.json"))
)


@pytest.fixture(scope="module")
def package():
    if not DATA.is_dir():
        return None
    from arena_kit.data import DataPackage

    return DataPackage(DATA)


@pytest.fixture(autouse=True)
def strict(monkeypatch):
    monkeypatch.setenv("SELLM_STRICT", "1")  # a bug must fail the test, not hide behind the rescue move


def sessions(limit=None):
    if not SESSIONS:
        pytest.skip("no saved sessions in runs/")
    return [json.loads(Path(p).read_text(encoding="utf-8")) for p in SESSIONS[:limit]]


def states(record):
    """Every state a thread of this session went through: its e-mails up to a supplier message,
    the other threads at their opening."""
    openings = {s: [t["messages"][0]] for s, t in record["threads"].items()}
    for sid, thread in record["threads"].items():
        for i, message in enumerate(thread["messages"]):
            if message.get("from") != "buyer" and not message.get("action"):
                yield sid, {**openings, sid: thread["messages"][: i + 1]}


def check(case, threads, decision):
    """What the arena would refuse, and what would cost the case."""
    sid, message = decision["supplier_id"], decision["message"]
    assert sid in threads
    view = Thread(case, sid, threads[sid])
    if message.get("action"):
        if message["action"]["type"] == "accept":
            offer_id, terms = view.standing
            assert message["action"]["term_sheet_id"] == offer_id, "only the standing sheet can be accepted"
            assert must_haves_ok(case, terms, view.std), "a deal that breaks a must-have scores 0"
        return
    assert set(message) <= {"subject", "body", "term_sheets", "refs", "attachments"}
    assert 0 < len(message["body"]) <= 8000 and len(message["subject"]) <= 300
    sheets = [s["terms"] for s in message["term_sheets"]]
    assert len(sheets) <= 3
    for terms in sheets:
        assert set(terms) == set(case["negotiable"]), "a term sheet carries exactly the negotiable fields"
        assert terms["unit_price"] > 0
        assert must_haves_ok(case, terms, view.std)
        for field, options in case.get("term_options", {}).items():
            if field in terms and options:
                assert terms[field] in options
        assert f"{terms['unit_price']:.2f}" in message["body"], "the e-mail names the price of every sheet"


def test_every_real_state_gets_a_valid_move(package):
    played = 0
    for record in sessions():
        for sid, threads in states(record):
            agent = make_agent(package)
            for focus in (None, sid):
                check(record["case"], threads, agent.decide(record["case"], threads, focus=focus))
                played += 1
    assert played > 100


def test_a_move_is_a_pure_function_of_the_thread(package):
    for record in sessions(limit=25):
        for sid, threads in list(states(record))[:4]:
            agent = make_agent(package)
            first = agent.decide(record["case"], threads, focus=sid)
            assert agent.decide(record["case"], threads, focus=sid) == first, "asking twice must not advance anything"
            assert make_agent(package).decide(record["case"], threads, focus=sid) == first, (
                "a fresh agent resumes the case"
            )
            assert agent.fallback.decide(record["case"], threads, focus=sid)["message"].get("term_sheets") == first[
                "message"
            ].get("term_sheets")


def test_our_ask_never_goes_back(package):
    """Played against the supplier's real replies: while the structure stays the same, our price
    never falls and each ask costs us at least as much as the last."""
    for record in sessions():
        case = record["case"]
        for sid, thread in record["threads"].items():
            theirs = [m for m in thread["messages"] if m.get("from") != "buyer"]
            threads = {s: [t["messages"][0]] for s, t in record["threads"].items()}
            agent, asks = make_agent(package), []
            for reply in theirs[1:] + [None]:
                decision = agent.decide(case, threads, focus=sid)
                message = decision["message"]
                if decision["supplier_id"] != sid or message.get("action") or not message.get("term_sheets"):
                    break
                view = Thread(case, sid, threads[sid])
                terms = message["term_sheets"][0]["terms"]
                if view.sheets and terms in [view.filled(sheet["terms"]) for sheet in view.sheets]:
                    break  # we take one of its own sheets: the asking is over
                asks.append((terms, total_cost(case, terms, view.std)))
                if reply is None:
                    break
                threads[sid] = threads[sid] + [{**message, "from": "buyer"}, reply]
            for (a, cost_a), (b, cost_b) in zip(asks, asks[1:], strict=False):
                if {f: x for f, x in a.items() if f != "unit_price"} == {
                    f: x for f, x in b.items() if f != "unit_price"
                }:
                    assert b["unit_price"] >= a["unit_price"], (
                        f"{case['case_id']} {sid}: {[x[0]['unit_price'] for x in asks]}"
                    )
                    assert cost_b >= cost_a


def test_first_ask_costs_us_less_than_its_own_terms_at_the_price_we_aim_for(package):
    """The calculator's package: at the price we expect to end at it costs us no more than the
    structure the supplier quoted; its Incoterm stays; payment days later than quoted are asked
    only of a supplier the dossier calls relaxed about cash, or as a second offer of equal cost."""
    for record in sessions():
        case = record["case"]
        threads = {s: [t["messages"][0]] for s, t in record["threads"].items()}
        for sid in threads:
            view = Thread(case, sid, threads[sid])
            its = view.filled(view.opening["term_sheets"][0]["terms"])
            if its.get("unit_price") is None or not view.valid(its):
                continue
            agent = make_agent(package)
            sheets = [s["terms"] for s in agent.decide(case, threads, focus=sid)["message"]["term_sheets"]]
            first = sheets[0]
            if "incoterm" in first:
                assert first["incoterm"] == its["incoterm"]
            if first.get("payment_days", 0) > its.get("payment_days", 0):
                assert agent.cash(case, view) == "low"
            if first.get("payment_days", 0) < its.get("payment_days", 0):  # faster payment for a supplier short of cash
                assert agent.cash(case, view) in ("medium", "high")
                first = {**first, "payment_days": its["payment_days"]}
            price = its["unit_price"] * TARGET_SHARE[case["buyer"].get("category_goal") in RELATIONSHIP_GOALS]
            assert view.c({**first, "unit_price": price}) <= view.c({**its, "unit_price": price}) + 0.01, (
                f"{case['case_id']}: {first}"
            )
            for other in sheets[1:]:  # a second offer costs us the same as the first
                assert abs(view.c(other) - view.c(first)) <= max(1.0, 0.002 * view.c(first)), (
                    f"{case['case_id']}: {sheets}"
                )


def one_supplier(record):
    case = record["case"]
    sid = case["suppliers"][0]
    return case, sid, record["threads"][sid]["messages"]


def reply(opening, status, price, sheet_id="offer:test-9", **terms):
    sheet = {**opening["term_sheets"][0]["terms"], **terms, "unit_price": price}
    return {
        **opening,
        "status": status,
        "term_sheets": [{"term_sheet_id": sheet_id, "terms": sheet}],
        "attachments": [],
        "body": "Our offer.",
    }


def first_single(goal=None):
    for record in sessions():
        case = record["case"]
        if len(case["suppliers"]) == 1 and (goal is None or case["buyer"]["category_goal"] == goal):
            return one_supplier(record)
    pytest.skip("no such session saved")


def ask_then(case, sid, messages, package, their):
    """The thread after our first ask and the supplier's `their` reply."""
    threads = {sid: [messages[0]]}
    ours = make_agent(package).decide(case, threads)["message"]
    return {sid: [messages[0], {**ours, "from": "buyer"}, their]}


def test_a_final_offer_is_accepted_not_pushed(package):
    case, sid, messages = first_single()
    price = messages[0]["term_sheets"][0]["terms"]["unit_price"] * 0.99
    their = reply(
        messages[0],
        "final_offer",
        price,
        contract_months=max(case.get("term_options", {}).get("contract_months") or [24]),
    )
    decision = make_agent(package).decide(case, ask_then(case, sid, messages, package, their))
    assert decision["message"].get("action") == {"type": "accept", "term_sheet_id": "offer:test-9"}


def test_no_walk_away_while_a_valid_offer_stands(package):
    """Walking away is right only when the alternative is the better deal."""
    for record in sessions():
        case = record["case"]
        alt = (case["buyer"].get("alternative") or {}).get("terms") or {}
        for sid, threads in states(record):
            decision = make_agent(package).decide(case, threads, focus=sid)
            if (decision["message"].get("action") or {}).get("type") != "walk_away":
                continue
            views = [Thread(case, s, events) for s, events in threads.items()]
            takable = [v for v in views if v.status not in ("walked_away", "no_bid") and v.valid(v.standing[1])]
            if not takable:
                continue  # nothing left to take: the case is over
            assert alt.get("unit_price"), f"{case['case_id']}: walked away from a valid offer without an alternative"
            c_alt = total_cost(case, alt)
            for view in takable:
                cost = total_cost(case, view.standing[1], view.std)
                assert cost > c_alt, f"{case['case_id']}: walked away from an offer better than the alternative"


def test_strategic_case_stops_when_the_offer_reaches_our_target(package):
    """In stabilise and secure_supply cases a lower price costs more in the relationship term."""
    case, sid, messages = first_single("stabilise")
    agent = make_agent(package)
    view = Thread(case, sid, [messages[0]])
    target = agent.aim(case, view, agent.opening_structure(case, view))["target"]
    their = reply(messages[0], "open", round(target * 0.995, 2), **agent.opening_structure(case, view))
    decision = make_agent(package).decide(case, ask_then(case, sid, messages, package, their))
    assert (decision["message"].get("action") or {}).get("type") == "accept"


def test_the_email_names_the_person_and_reads_like_one(package):
    case, sid, messages = first_single()
    message = make_agent(package).decide(case, {sid: [messages[0]]})["message"]
    lines = [ln.strip() for ln in messages[0]["body"].strip().splitlines() if ln.strip()]
    assert message["body"].startswith(f"Dear {lines[-2]},"), message["body"][:60]
    assert "Dear Sir or Madam" not in message["body"]
    for forbidden in ("unacceptable", "urgent", "budget", "no alternative", "last chance"):
        assert forbidden not in message["body"].lower()


def test_rfq_with_focus_moves_in_that_thread_only(package):
    for record in sessions():
        case = record["case"]
        if len(case["suppliers"]) < 2:
            continue
        threads = {s: [t["messages"][0]] for s, t in record["threads"].items()}
        for sid in threads:
            decision = make_agent(package).decide(case, threads, focus=sid)
            assert decision["supplier_id"] == sid and decision["message"].get("term_sheets")
        return
    pytest.skip("no RFQ session saved")


def test_agent_needs_no_llm_and_no_data(monkeypatch):
    for name in ("LLM_MODEL", "LLM_API_KEY", "LLM_PROVIDER", "SELLM_WRITER"):
        monkeypatch.delenv(name, raising=False)
    agent = make_agent()
    assert isinstance(agent, Negotiator) and agent.fallback is agent
    case, sid, messages = first_single()
    check(case, {sid: [messages[0]]}, agent.decide(case, {sid: [messages[0]]}))


def test_a_bug_in_our_code_becomes_a_safe_move(monkeypatch):
    monkeypatch.setenv("SELLM_STRICT", "0")
    case, sid, messages = first_single()
    agent = make_agent()
    monkeypatch.setattr(agent, "move", lambda *a, **k: 1 / 0)
    decision = agent.decide(case, {sid: [messages[0]]})
    assert decision["supplier_id"] == sid and decision["message"]["term_sheets"] == [] and agent.stats["errors"] == 1
    assert os.environ["SELLM_STRICT"] == "0"


def test_a_changed_field_is_asked_once_more_at_the_option_cheapest_for_us(package):
    """The `second_choice` knob (off by default, see its note): it answers a fixed-price ask with an
    index clause without a deadband, we ask once for the clause that costs us least; if it changes
    the field again, its value stands. Without the knob we take its structure as it comes."""
    for record in sessions():
        case = record["case"]
        clauses = [o for o in case.get("term_options", {}).get("index_clause") or [] if o]
        if len(case["suppliers"]) != 1 or len(clauses) < 2 or "contract_months" not in case["negotiable"]:
            continue
        sid = case["suppliers"][0]
        first = record["threads"][sid]["messages"][0]
        threads = {sid: [first]}
        ours = make_agent(package).decide(case, threads)["message"]
        asked = ours["term_sheets"][0]["terms"]
        if asked.get("index_clause") is not None:
            continue
        view = Thread(case, sid, threads[sid])
        worst = max(clauses, key=lambda o: view.c({**asked, "index_clause": o}))
        cheapest = min(clauses, key=lambda o: view.c({**asked, "index_clause": o}))
        price = first["term_sheets"][0]["terms"]["unit_price"] * 0.95
        its = {**first, "status": "open", "attachments": [], "body": "A fixed price is not feasible."}

        def answer(n, p, its=its, asked=asked, worst=worst):
            terms = {**asked, "index_clause": worst, "unit_price": p}
            return {**its, "term_sheets": [{"term_sheet_id": f"offer:t-{n}", "terms": terms}]}

        threads = {sid: [first, {**ours, "from": "buyer"}, answer(1, price)]}
        plain = make_agent(package).decide(case, threads)["message"]["term_sheets"][0]["terms"]
        assert plain["index_clause"] == worst
        second = make_agent(package, second_choice=True).decide(case, threads)["message"]
        sheet = second["term_sheets"][0]["terms"]
        assert sheet["index_clause"] == cheapest, sheet
        assert asked["unit_price"] <= sheet["unit_price"] < price
        threads = {sid: [*threads[sid], {**second, "from": "buyer"}, answer(2, price * 0.99)]}
        third = make_agent(package, second_choice=True).decide(case, threads)["message"]["term_sheets"][0]["terms"]
        assert third["index_clause"] == worst, "changed twice: we take its clause"
        return
    pytest.skip("no saved case with an index clause and a contract length")


def test_cases_played_at_the_same_time_decide_as_they_do_alone(package):
    """The final plays ten cases at once on one data package. A lookup that fails under threads
    must not turn a should-cost target or a dossier into a guess (it did: 7 of 10 cases, Sat 21:40)."""
    from concurrent.futures import ThreadPoolExecutor

    if package is None:
        pytest.skip("no data package")
    openings = {}
    for record in sessions():
        case = record["case"]
        openings.setdefault(case["case_id"], (case, {s: [t["messages"][0]] for s, t in record["threads"].items()}))

    def first_asks(case_id):
        case, threads = openings[case_id]
        asks = []
        for sid in threads:
            message = make_agent(package).decide(case, threads, focus=sid)["message"]
            asks.append([sheet["terms"] for sheet in message.get("term_sheets") or []])
        return case_id, asks

    alone = dict(first_asks(case_id) for case_id in openings)
    with ThreadPoolExecutor(max_workers=10) as pool:
        for case_id, asks in pool.map(first_asks, list(openings) * 8):
            assert asks == alone[case_id], case_id
