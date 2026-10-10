"""The final runner (sellm/runner.py) against a fake arena built on the lab's LocalTable: the cases that
lose points in the final - an RFQ timeout that replaces the offer ID, a slow agent, the wave's cap, a
crash and its resume, waves that start and close - are played in seconds, without quota."""

import copy
import threading
import time
from pathlib import Path

import pytest

from arena_kit.client import ArenaError
from sellm import runner
from sellm.lab import twins
from sellm.lab.table import LocalTable

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "package"
FAST = runner.Limits(silence=0.5, move_warn=1.0, move_hard=2.0, hold_after=0.6, close_before_cap=0.4,
                     round_margin=0.05, max_case=20.0, idle=0.01, poll=0.05)  # fmt: skip


def _package():
    if not (DATA / "facts.json").is_file():
        pytest.skip("data package not downloaded (uv run arena data)")
    from arena_kit.data import DataPackage

    pkg = DataPackage(DATA)
    pkg.lookup("")
    return pkg


def _scenario(name):
    return next(s for s in twins.load() if s.name == name)


def _agent(pkg):
    from sellm.agent import make_agent

    runner.warm_up(lambda: make_agent(pkg))  # as run_final and run_cases do before the first case
    return make_agent(pkg)


class FakeArena:
    """The arena's API over LocalTable sessions: the calls sellm.runner makes, nothing else."""

    def __init__(self, scenarios, facts, waves=None):
        self.scenarios = {s.case["case_id"]: s for s in scenarios}
        self.facts, self.waves, self.t0 = facts, waves or [], time.time()
        self.sessions, self.by_case, self.timeouts = {}, {}, {}
        self.lock, self.calls, self.practice_remaining = threading.RLock(), [], None

    def _log(self, *what):
        self.calls.append(what)

    def open_session(self, case_id):
        with self.lock:
            self._log("open", case_id)
            sid = self.by_case.get(case_id)
            if sid is not None:
                raise ArenaError(409, f"one session per case in the final: {sid}")
            table = LocalTable(self.scenarios[case_id], self.facts, seed=len(self.sessions))
            case, threads = table.open()
            sid = f"fake{len(self.sessions)}"
            self.sessions[sid], self.by_case[case_id] = table, sid
            return {"session_id": sid, "case": case, "threads": threads}

    def send_message(self, sid, sup, message):
        with self.lock:
            self._log("send", sid, sup, (message.get("action") or {}).get("type") or "e-mail")
            table = self.sessions[sid]
            if message.get("action"):
                return {"result": table.close(sup, message)}
            return table.send(sup, message)

    def thread(self, sid, sup):
        with self.lock:
            self._log("thread", sid, sup)
            th = self.sessions[sid].threads[sup]
            return {
                "supplier_id": sup,
                "offer_id": th.standing["term_sheet_id"] if th.standing else None,
                "status": th.status,
                "closed": th.closed,
                "messages": [dict(m) for m in th.history],
                "timeouts": list(self.timeouts.get((sid, sup), [])),
            }

    def session(self, sid):
        with self.lock:
            self._log("session", sid)
            t = self.sessions[sid]
            ended = t.outcome is not None
            return {"session_id": sid, "status": "ended" if ended else "open", "case": t.case,
                    "end_reason": t.outcome["end_reason"] if ended else None,
                    "result": t._result() if ended else None, "threads": {s: {} for s in t.threads}}  # fmt: skip

    def attachment(self, sid, attachment_id):
        return self.sessions[sid].attachment(attachment_id)

    def cases(self, set_="practice"):
        self._log("cases", set_)
        if set_ != "final":
            return [s.case for s in self.scenarios.values()]
        now, out = time.time() - self.t0, []
        for n, (start, cap, ids) in enumerate(self.waves, 1):
            if now < start:
                continue
            left = max(0.0, start + cap - now)
            out += [{**self.scenarios[c].case, "wave": n, "theme": f"wave {n}", "open": left > 0, "seconds_left": left}
                    for c in ids]  # fmt: skip
        if not out:
            raise ArenaError(403, "the final's case list opens with the first wave")
        return out

    def time_out(self, sid, sup):
        """The arena counts a timeout: the supplier re-issues its offer under a new ID."""
        th = self.sessions[sid].threads[sup]
        follow = th.timeout()
        sheet = (follow.get("term_sheets") or [{}])[0]
        late = {"offer_id": sheet.get("term_sheet_id"), "status": follow["status"], "terms": sheet.get("terms") or {},
                "text": follow["body"]}  # fmt: skip
        self.timeouts.setdefault((sid, sup), []).append(late)


def test_plays_a_case_to_its_end():
    pkg = _package()
    arena = FakeArena([_scenario("P01")], pkg.facts)
    row = runner.play_case(arena, "case:P01", _agent(pkg), limits=FAST)
    assert row["crash"] is None and row["end_reason"] in ("accepted", "walked_away", "no_deal")
    assert 0.0 <= (row["score"] or 0.0) <= 1.0


def test_rfq_timeout_replacing_the_offer_id_does_not_lose_the_case():
    """The first accept meets a timeout that has just replaced the offer ID: a 422, as on the arena.
    The runner re-reads the threads and accepts the current offer."""
    pkg = _package()

    class Racy(FakeArena):
        raced = False

        def send_message(self, sid, sup, message):
            if (message.get("action") or {}).get("type") == "accept" and not self.raced:
                self.raced = True
                with self.lock:
                    self.time_out(sid, sup)
                raise ArenaError(422, "not a standing offer in this session")
            return super().send_message(sid, sup, message)

    arena = Racy([_scenario("P05")], pkg.facts)
    row = runner.play_case(arena, "case:P05", _agent(pkg), limits=FAST)
    assert row["crash"] is None
    assert arena.raced, "the agent never tried to accept: the test did not test the race"
    assert row["stats"]["refused"] >= 1 and row["end_reason"] in ("accepted", "walked_away")
    assert any("refused" in n for n in row["notes"])
    accepts = [c for c in arena.calls if c[0] == "send" and c[3] == "accept"]
    assert len(accepts) <= 2


def test_a_slow_agent_gets_a_holding_email_not_a_lost_thread():
    pkg = _package()
    inner = _agent(pkg)

    class Slow:
        stats = {}

        def __init__(self):
            self.n = 0

        def decide(self, case, threads, focus=None):
            self.n += 1
            if self.n == 2:
                time.sleep(3.0)  # longer than FAST.move_hard
            return inner.decide(case, threads, focus=focus)

    arena = FakeArena([_scenario("P01")], pkg.facts)
    row = runner.play_case(arena, "case:P01", Slow(), limits=FAST)
    assert row["crash"] is None
    assert row["stats"]["holds"] >= 1
    assert any("holding e-mail instead" in n for n in row["notes"])


def test_an_agent_that_keeps_failing_is_closed_on_what_stands():
    pkg = _package()

    class Broken:
        def decide(self, case, threads, focus=None):
            raise RuntimeError("the LLM is down")

    arena = FakeArena([_scenario("P01")], pkg.facts)
    row = runner.play_case(arena, "case:P01", Broken(), limits=FAST)
    assert row["crash"] is None and row["stats"]["holds"] == 1
    assert row["end_reason"] in ("accepted", "walked_away")
    assert any("second time in a row" in n for n in row["notes"])


def test_a_thread_the_agent_leaves_waiting_gets_a_holding_email_before_its_clock_runs_out():
    """Sandbox D02: the agent worked one bidder for 71 s, the other timed out and hardened to its
    final offer. Here the agent only ever moves the first bidder; the others must be held, at most
    max_holds times each."""
    pkg = _package()

    class Fixated:
        def __init__(self):
            self.inner = _agent(pkg)

        def decide(self, case, threads, focus=None):
            first = sorted(threads)[0]
            return self.inner.decide(case, threads, focus=first)

    class SlowFirst(FakeArena):
        def send_message(self, sid, sup, message):
            if sup == sorted(self.sessions[sid].threads)[0]:
                time.sleep(0.4)  # its replies take time, as on the arena: the others wait
            return super().send_message(sid, sup, message)

    arena = SlowFirst([_scenario("P05")], pkg.facts)
    row = runner.play_case(arena, "case:P05", Fixated(), limits=FAST)
    assert row["crash"] is None and row["stats"]["clock_holds"] >= 1
    first = sorted(arena.sessions[row["session_id"]].threads)[0]
    held = [c[2] for c in arena.calls if c[0] == "send" and c[3] == "e-mail" and c[2] != first]
    assert held and all(held.count(s) <= FAST.max_holds for s in set(held))
    assert any("while the agent works elsewhere" in n for n in row["notes"])


def test_an_attachment_held_behind_another_reply_does_not_stop_the_other_threads():
    """Practice P05: the arena answered an attachment only once another bidder's pending reply was
    written (37-61 s); the runner held the case lock meanwhile and a bidder timed out. Here every
    attachment waits for all of the session's replies in flight, and one bidder is slow."""
    pkg = _package()

    class Held(FakeArena):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            self.in_flight, self.cv = 0, threading.Condition()

        def send_message(self, sid, sup, message):
            with self.cv:
                self.in_flight += 1
            try:
                if sup == sorted(self.sessions[sid].threads)[0]:
                    time.sleep(1.0)
                reply = copy.deepcopy(super().send_message(sid, sup, message))
                for att in reply.get("attachments") or []:
                    att.pop("text", None)  # as on the arena: the text has to be fetched
                return reply
            finally:
                with self.cv:
                    self.in_flight -= 1
                    self.cv.notify_all()

        def attachment(self, sid, attachment_id):
            with self.cv:
                self.cv.wait_for(lambda: self.in_flight == 0, timeout=5.0)
            return super().attachment(sid, attachment_id)

    arena = Held([_scenario("P05")], pkg.facts)
    limits = runner.Limits(**{**FAST.__dict__, "docs": 0.2})
    row = runner.play_case(arena, "case:P05", _agent(pkg), limits=limits)
    assert row["crash"] is None and row["end_reason"] in ("accepted", "walked_away")
    assert row["stats"]["slow_docs"] >= 1
    assert any("going on without" in n for n in row["notes"])


def test_closes_on_what_stands_before_the_cap():
    pkg = _package()

    class Stalling:
        """Never accepts: only the runner's closing before the cap can end the case."""

        def __init__(self):
            self.inner = _agent(pkg)

        def decide(self, case, threads, focus=None):
            d = self.inner.decide(case, threads, focus=focus)
            if d["message"].get("action"):
                return runner._hold(case, focus)
            return d

    arena = FakeArena([_scenario("P01")], pkg.facts)
    cap = time.time() + 1.5
    row = runner.play_case(arena, "case:P01", Stalling(), deadline=lambda: cap, limits=FAST)
    assert row["crash"] is None
    assert row["end_reason"] in ("accepted", "walked_away")
    assert any(n.startswith("closing:") for n in row["notes"])


def test_resumes_a_session_that_is_already_running():
    pkg = _package()
    arena = FakeArena([_scenario("P01")], pkg.facts)
    opened = arena.open_session("case:P01")  # a first runner opened it, then crashed
    sup = next(iter(opened["threads"]))
    agent = _agent(pkg)
    first = agent.decide(opened["case"], opened["threads"], focus=sup)
    arena.send_message(opened["session_id"], first["supplier_id"], first["message"])
    row = runner.play_case(arena, "case:P01", _agent(pkg), limits=FAST)
    assert row["crash"] is None and row["session_id"] == opened["session_id"]
    assert any("resumed session" in n for n in row["notes"])
    assert row["end_reason"] in ("accepted", "walked_away", "no_deal")


def test_waves_start_their_cases_and_the_runner_stops_after_the_last():
    pkg = _package()
    scen = [_scenario(n) for n in ("P01", "P04", "P07")]
    arena = FakeArena(scen, pkg.facts, waves=[(0.2, 6.0, ["case:P01", "case:P04"]), (0.6, 6.0, ["case:P07"])])
    rows = runner.run_final(arena, lambda: _agent(pkg), waves=2, parallel=10, limits=FAST)
    assert set(rows) == {"case:P01", "case:P04", "case:P07"}
    assert all(r["crash"] is None for r in rows.values())
    assert {r["wave"] for r in rows.values()} == {1, 2}
    assert ("cases", "final") in arena.calls


def test_the_runner_never_calls_the_live_feed():
    """docs/CONTEXT.md section 11: reading events, screen, leaderboard or results disqualifies."""
    for path in (ROOT / "sellm" / "runner.py", ROOT / "sellm" / "negotiator.py", ROOT / "sellm" / "agent.py"):
        text = path.read_text(encoding="utf-8")
        code = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))
        for word in ("/events", "events/stream", "/screen", ".leaderboard(", "/leaderboard", "/results"):
            assert word not in code.replace("never the live feed (events, screen,", ""), (path.name, word)
