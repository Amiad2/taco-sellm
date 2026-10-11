# ruff: noqa: E501  (long test data lines)
"""sellm2's runner against a fake arena built on the lab's LocalTable (the team's simulator): the
things that cost cases - a supplier that leaves mid-case, an offer ID replaced by a timeout, a slow
or broken agent, the wave's cap, a crash, the waves - played in seconds, without quota."""

import threading
import time
from pathlib import Path

import pytest

from arena_kit.client import ArenaError
from sellm2 import runner
from sellm2.agent import make_agent

ROOT = Path(__file__).resolve().parents[2]
FAST = runner.Limits(move_hard=1.0, docs=0.5, hold_after=0.3, close_before_cap=0.4, round_margin=0.05, max_case=20.0, poll=0.05)


def _lab():
    twins = pytest.importorskip("sellm.lab.twins")
    table = pytest.importorskip("sellm.lab.table")
    return twins, table.LocalTable


def _scenario(name):
    twins, _ = _lab()
    return next(s for s in twins.load() if s.name == name)


class FakeArena:
    """The arena's API over LocalTable sessions: the calls the runner makes, nothing else."""

    def __init__(self, scenarios, facts, waves=None):
        _, self.Table = _lab()
        self.scenarios = {s.case["case_id"]: s for s in scenarios}
        self.facts, self.waves, self.t0 = facts, waves or [], time.time()
        self.sessions, self.by_case, self.timeouts = {}, {}, {}
        self.lock, self.calls, self.practice_remaining = threading.RLock(), [], None

    def open_session(self, case_id):
        with self.lock:
            self.calls.append(("open", case_id))
            sid = self.by_case.get(case_id)
            if sid is not None:
                raise ArenaError(409, f"one session per case in the final: {sid}")
            table = self.Table(self.scenarios[case_id], self.facts, seed=len(self.sessions))
            case, threads = table.open()
            sid = f"fake{len(self.sessions)}"
            self.sessions[sid], self.by_case[case_id] = table, sid
            return {"session_id": sid, "case": case, "threads": threads}

    def send_message(self, sid, sup, message):
        with self.lock:
            self.calls.append(("send", sid, sup, (message.get("action") or {}).get("type") or "e-mail"))
            table = self.sessions[sid]
            if table.threads[sup].closed:
                raise ArenaError(409, f"the thread with {sup} has ended: walked_away")
            if message.get("action"):
                return {"result": table.close(sup, message)}
            return table.send(sup, message)

    def thread(self, sid, sup):
        with self.lock:
            self.calls.append(("thread", sid, sup))
            th = self.sessions[sid].threads[sup]
            return {"supplier_id": sup, "offer_id": th.standing["term_sheet_id"] if th.standing else None,
                    "status": th.status, "closed": th.closed, "messages": [dict(m) for m in th.history],
                    "timeouts": list(self.timeouts.get((sid, sup), []))}  # fmt: skip

    def session(self, sid):
        with self.lock:
            self.calls.append(("session", sid))
            t = self.sessions[sid]
            ended = t.outcome is not None
            return {"session_id": sid, "status": "ended" if ended else "open", "case": t.case,
                    "end_reason": t.outcome["end_reason"] if ended else None,
                    "result": t._result() if ended else None, "threads": {s: {} for s in t.threads}}  # fmt: skip

    def attachment(self, sid, attachment_id):
        return self.sessions[sid].attachment(attachment_id)

    def cases(self, set_="practice"):
        self.calls.append(("cases", set_))
        if set_ != "final":
            return [s.case for s in self.scenarios.values()]
        now, out = time.time() - self.t0, []
        for n, (start, cap, ids) in enumerate(self.waves, 1):
            if now < start:
                continue
            left = max(0.0, start + cap - now)
            out += [{**self.scenarios[c].case, "wave": n, "theme": f"wave {n}", "open": left > 0, "seconds_left": left} for c in ids]
        if not out:
            raise ArenaError(403, "the final's case list opens with the first wave")
        return out

    def time_out(self, sid, sup):
        th = self.sessions[sid].threads[sup]
        follow = th.timeout()
        sheet = (follow.get("term_sheets") or [{}])[0]
        self.timeouts.setdefault((sid, sup), []).append(
            {"offer_id": sheet.get("term_sheet_id"), "status": follow["status"], "terms": sheet.get("terms") or {}, "text": follow["body"]})


def _agent(pkg):
    return lambda: make_agent(pkg)


def test_plays_a_case_to_its_end(pkg):
    arena = FakeArena([_scenario("P01")], pkg.facts)
    row = runner.play_case(arena, "case:P01", _agent(pkg), limits=FAST)
    assert row["crash"] is None and row["deal"] is not None
    assert 0.0 <= (row["score"] or 0.0) <= 1.0


def test_a_supplier_that_left_is_never_asked_again(pkg):
    """Practice P05 (Sun 03:06): a bidder walked away, its end showed only in the thread's state, and the
    old loop asked it 188 times while the best bidder at final_offer withdrew. Here the first bidder
    leaves after our first message to it, without a message that says so."""

    class Leaving(FakeArena):
        left = None

        def send_message(self, sid, sup, message):
            with self.lock:
                table = self.sessions[sid]
                if self.left is None and not message.get("action"):
                    self.left = sup
                    reply = super().send_message(sid, sup, message)
                    table.threads[sup].closed = "walked_away"
                    table.threads[sup].status = "walked_away"
                    return reply
            return super().send_message(sid, sup, message)

    arena = Leaving([_scenario("P05")], pkg.facts)
    row = runner.play_case(arena, "case:P05", _agent(pkg), limits=FAST)
    assert row["crash"] is None and arena.left
    sends_after = [c for c in arena.calls if c[0] == "send" and c[2] == arena.left]
    assert len(sends_after) <= 2, sends_after
    assert row["stats"]["late"] <= 1 and row["deal"] is not None


def test_a_timeout_that_replaces_the_offer_id_does_not_lose_the_case(pkg):
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
    assert row["crash"] is None and arena.raced
    assert row["stats"]["refused"] == 1 and row["deal"] is True  # the other bidders, or the re-issued offer


def test_a_slow_or_broken_agent_keeps_the_case_alive(pkg):
    inner = make_agent(pkg)

    class Slow:
        n = 0

        def decide(self, case, threads, focus=None):
            self.n += 1
            if self.n == 2:
                time.sleep(2.0)
            return inner.decide(case, threads, focus)

    class Broken:
        def decide(self, case, threads, focus=None):
            raise RuntimeError("down")

    row = runner.play_case(FakeArena([_scenario("P01")], pkg.facts), "case:P01", Slow, limits=FAST)
    assert row["crash"] is None and row["stats"]["slow"] >= 1 and row["deal"] is not None
    row = runner.play_case(FakeArena([_scenario("P01")], pkg.facts), "case:P01", Broken, limits=FAST)
    assert row["crash"] is None and row["deal"] is not None  # closed by the time limit on what stands


def test_closes_with_our_own_close_before_the_cap(pkg):
    class Stalling:
        """Never closes: only the runner's close before the cap can end the case."""

        def __init__(self):
            self.inner = make_agent(pkg)
            self.policy = self.inner.policy

        def decide(self, case, threads, focus=None):
            time.sleep(0.3)  # slow enough that the cap comes before the round limit
            d = self.inner.decide(case, threads, focus)
            if d["message"].get("action"):
                return self.policy.rescue(case, threads)
            return d

    cap = time.time() + 1.5
    row = runner.play_case(FakeArena([_scenario("P01")], pkg.facts), "case:P01", Stalling, cap=lambda: cap, limits=FAST)
    assert row["crash"] is None and row["stats"]["closed_at_cap"] == 1 and row["deal"] is not None


def test_resumes_a_final_session_already_running(pkg):
    arena = FakeArena([_scenario("P01")], pkg.facts)
    opened = arena.open_session("case:P01")
    case = opened["case"]
    row = runner.play_case(arena, case, _agent(pkg), limits=FAST)
    assert row["crash"] is None and row["session_id"] == opened["session_id"] and row["deal"] is not None


def test_waves_start_their_cases_and_the_runner_stops_after_the_last(pkg):
    scen = [_scenario(n) for n in ("P01", "P04", "P07")]
    arena = FakeArena(scen, pkg.facts, waves=[(0.2, 8.0, ["case:P01", "case:P04"]), (0.6, 8.0, ["case:P07"])])
    rows = runner.run_final(arena, _agent(pkg), waves=2, parallel=10, poll=0.05, limits=FAST)
    assert set(rows) == {"case:P01", "case:P04", "case:P07"}
    assert all(r["crash"] is None and r["deal"] is not None for r in rows.values())


def test_one_message_in_flight_per_session(pkg):
    class Watch(FakeArena):
        inflight, peak = 0, 0

        def send_message(self, sid, sup, message):
            with self.lock:
                self.inflight += 1
                self.peak = max(self.peak, self.inflight)
            try:
                time.sleep(0.01)
                return super().send_message(sid, sup, message)
            finally:
                with self.lock:
                    self.inflight -= 1

    arena = Watch([_scenario("P05")], pkg.facts)
    row = runner.play_case(arena, "case:P05", _agent(pkg), limits=FAST)
    assert row["crash"] is None and arena.peak == 1


def test_sellm2_never_calls_the_live_feed():
    """docs/CONTEXT.md section 11: reading events, screen, leaderboard or results disqualifies."""
    for path in (ROOT / "sellm2").rglob("*.py"):
        if "tests" in path.parts:
            continue
        code = "\n".join(line for line in path.read_text(encoding="utf-8").splitlines() if not line.lstrip().startswith("#"))
        code = code.replace("never the live feed\n(/events, /screen, /leaderboard, /results)", "")
        for word in ("events/stream", ".leaderboard(", "/v1/events", "/v1/screen", "/v1/results", "/v1/leaderboard"):
            assert word not in code, (path.name, word)
