"""The runner for the Live Final (and for measured runs on the sandbox and practice cases).

    uv run python -m sellm.runner --set final --agent sellm              # the Live Final: waits for the waves
    uv run python -m sellm.runner --set sandbox --cases D01 D02 --repeat 3
    uv run python -m sellm.runner --set practice --cases all --label "runner v1, sellm"

Why not the kit's `arena run`: its `play()` handles one thread at a time and waits for each reply,
so in an RFQ the other threads' 60-second clocks run out; a timeout replaces the offer ID, and
accepting the old ID is a 422 that stops `play()` and loses the case (lab: 6 refused accepts in
408 negotiations; sandbox D02: 2 timeouts per session). This runner plays every case with one loop
per thread, after Jonathan's `experiments/ab_sandbox.py:play_case`, and adds what the final needs:

- **one loop per thread**: each thread answers as soon as its own reply is in; a thread is re-read
  after a silence and before every accept (offer ID changed: decide again); 409/422 are survived;
- **a deadline per move**: the agent decides on a copy of the threads in a worker, so a slow LLM
  never blocks the other threads; warning at 15 s, at 40 s its fallback (if it has one of its own)
  or a holding e-mail without a term sheet (the offer stands, the clock restarts). Logged, never silent;
- **final-offer guard**: a supplier waiting at its final offer gets a holding e-mail after 45 s if the
  agent sends nothing to it (in the sandbox a waiting supplier withdrew);
- **the cap**: shortly before a wave's cap (90 s, or the slowest round so far plus 15 s) every
  thread is re-read and the kit's `closing_move` closes the case;
- **resume**: `POST /sessions` answering 409 "one session per case in the final: <id>" picks the
  running session up again (after a crash, or a second start of the runner);
- **waves**: polls `/v1/cases?set=final`, starts each case of an open wave once, at most 10 at a time,
  follows the cap in `seconds_left` (the host may extend a wave), stops after the last wave.

It calls only cases, sessions, threads, attachments and me - never the live feed (events, screen,
leaderboard, results), which the rules forbid to the agent's code path. Everything goes to a log
file in runs/logs/ and one JSON line per case.
"""

import argparse
import copy
import importlib
import inspect
import json
import logging
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from concurrent.futures import TimeoutError as FutureTimeout
from dataclasses import dataclass
from pathlib import Path

from arena_kit.client import ArenaError
from arena_kit.play import ENDED, closing_move, fetch_documents, latest, live_threads, moves_left

ROOT = Path(__file__).resolve().parents[1]
RUNNING = re.compile(r"one session per case in the final: (\S+)")
ENDS = {"accept": "accepted", "walk_away": "walked_away"}
HOLD_BODY = "Dear Sir or Madam,\n\nthank you for your offer. We are reviewing it internally and will revert shortly."
log = logging.getLogger("sellm.runner")


@dataclass
class Limits:
    """Timing in seconds. The defaults are the arena's; tests shrink them."""

    silence: float = 50.0  # re-read a thread we have not heard from for this long (it may have timed out)
    move_warn: float = 15.0  # a decision this slow is logged
    move_hard: float = 40.0  # then the fallback or a holding e-mail (the arena allows 60 per message)
    hold_after: float = 42.0  # a live thread left unanswered this long gets a holding e-mail (it has 60)
    max_holds: int = 2  # ... at most this often per thread
    close_before_cap: float = 90.0  # close this long before the cap at the latest
    round_margin: float = 15.0  # ... or the slowest round so far plus this
    max_case: float = 540.0  # without a cap (practice, sandbox): close after this
    flight_wait: float = 70.0  # an accept waits this long for a message still on its way to that supplier
    docs: float = 20.0  # a reply's attachments are waited for this long, then it goes on without their text
    idle: float = 2.0  # a loop with nothing to send waits this long (an LLM agent is asked again after it)
    poll: float = 5.0  # the final's case list is read this often
    serial: bool = False  # at most one message of a session on its way to the arena (see CaseRunner.post)
    turns: bool = False  # one loop for all threads, the agent picks the thread (the kit's play() order), see run()


def ended(result, reason):
    """The result with its end reason: the arena puts it on the session, the accept reply may leave it out."""
    return {**result, "end_reason": result.get("end_reason") or reason}


class Table:
    """What `fetch_documents` needs: the session's attachments."""

    def __init__(self, client, sid):
        self.client, self.sid = client, sid

    def attachment(self, attachment_id):
        return self.client.attachment(self.sid, attachment_id)


def _hold(case, sid):
    return {"supplier_id": sid, "message": {"subject": f"Re: {case.get('title', '')}"[:300], "body": HOLD_BODY,
                                            "term_sheets": []}}  # fmt: skip


class CaseRunner:
    """One case from open to close. `deadline`: a callable giving the wave's cap (time.time()), or None."""

    def __init__(self, client, case_id, agent, deadline=None, limits=None, case=None):
        self.client, self.case_id, self.agent = client, case_id, agent
        self.deadline, self.lim, self.case_file = deadline, limits or Limits(), case
        self.lock, self.done = threading.Lock(), threading.Event()
        self.closing = threading.Lock()  # one accept or walk-away at a time: two threads may both decide to close
        self.wire = threading.Lock()  # with lim.serial: one message of this session in flight at a time
        self.flying, self.notes, self.outcome = set(), [], {}
        self.stats = {
            "moves": 0,
            "slow": 0,
            "fallbacks": 0,
            "holds": 0,
            "refused": 0,
            "rereads": 0,
            "clock_holds": 0,
            "slow_docs": 0,
        }
        self.slowest, self.t_start = 0.0, time.monotonic()
        self.clock_holds, self.heard, self.replied, self.threads = {}, {}, {}, {}  # replied: its last reply
        self.pending, self.failures, self.broken = {}, {}, False  # per thread: a running decision, failures in a row
        self.takes_focus = "focus" in inspect.signature(agent.decide).parameters
        self.pool = ThreadPoolExecutor(max_workers=8, thread_name_prefix=f"decide-{case_id}")
        self.docs_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix=f"docs-{case_id}")

    # -- the session ---------------------------------------------------------------------------
    def note(self, text, level=logging.INFO):
        self.notes.append(text)
        log.log(level, "%s %s %s", self.case_id, getattr(self, "sid", "-"), text)

    def open(self):
        try:
            opened = self.client.open_session(self.case_id)
        except ArenaError as e:
            running = RUNNING.search(str(e.detail)) if e.status == 409 else None
            if not running:
                raise
            return self.resume(running.group(1))
        self.sid, self.case, self.threads = opened["session_id"], opened["case"], opened["threads"]
        self.table = Table(self.client, self.sid)
        for events in self.threads.values():
            for m in events:
                fetch_documents(self.table, m)
        self.note(f"session {self.sid} opened, {len(self.threads)} thread(s)")
        return True

    def resume(self, sid):
        """A running session of this case (after a crash or a second start): every thread from the arena."""
        self.sid, self.table = sid, Table(self.client, sid)
        state = self.client.session(sid)
        self.case = self.case_file or state.get("case") or {"case_id": self.case_id, "title": ""}
        if state.get("status") == "ended":
            self.outcome["result"] = ended(state.get("result") or {"deal": False}, state.get("end_reason"))
            self.note(f"session {sid} had already ended: {state.get('end_reason')}")
            return False
        self.threads = {}
        for s in state["threads"]:
            msgs = self.client.thread(sid, s).get("messages") or []
            self.threads[s] = [fetch_documents(self.table, m) for m in msgs]
        for s in self.threads:
            self.refresh(s)
        self.note(f"resumed session {sid}, {len(self.threads)} thread(s)", logging.WARNING)
        return True

    def refresh(self, sup):
        """Add what the arena did in this thread without us: timeout follow-ups carry a new offer ID."""
        t = self.client.thread(self.sid, sup)  # outside the lock: the arena may hold it behind a reply
        with self.lock:
            self._merge(sup, t)
        return t

    def _merge(self, sup, t):
        self.stats["rereads"] += 1
        events = self.threads[sup]
        seen = sum(1 for m in events if m.get("_timeout"))
        for k, late in enumerate((t.get("timeouts") or [])[seen:], start=seen):
            sheets = (
                [{"term_sheet_id": late["offer_id"], "terms": late.get("terms") or {}}] if late.get("offer_id") else []
            )
            events.append({"from": f"timeout@{sup}", "_timeout": True, "message_id": f"timeout:{sup}:{k}",
                           "status": late.get("status") or "open", "term_sheets": sheets,
                           "body": late.get("text") or "", "missing_fields": late.get("missing_fields") or [],
                           "attachments": []})  # fmt: skip
            self.note(f"{sup}: timeout, now {late.get('status')} {late.get('offer_id')}", logging.WARNING)
            self.heard[sup] = self.replied[sup] = time.monotonic()  # the follow-up restarts its clock
        if t.get("closed") and latest(events).get("status") not in ENDED:
            events.append({"from": f"closed@{sup}", "_timeout": True, "message_id": f"closed:{sup}",
                           "status": "walked_away", "term_sheets": [], "body": "", "attachments": []})  # fmt: skip
            self.note(f"{sup}: thread closed ({t.get('closed')})", logging.WARNING)

    # -- time ----------------------------------------------------------------------------------
    def closing_due(self):
        if self.deadline is not None:
            cap = self.deadline() if callable(self.deadline) else self.deadline
            if cap and time.time() > cap - max(self.lim.close_before_cap, self.slowest + self.lim.round_margin):
                return True
        return time.monotonic() - self.t_start > self.lim.max_case

    def decide(self, focus):
        """The agent's move on a copy of the threads, within the move deadline; else a safe move."""
        with self.lock:
            snapshot = copy.deepcopy(self.threads)
        t0 = time.monotonic()
        kwargs = {"focus": focus} if self.takes_focus and focus is not None else {}
        prev = self.pending.get(focus)
        if prev is not None and not prev.done():  # an earlier decision still hangs: no second one behind it
            decision, reason = None, "the previous decision for this thread is still running"
        else:
            future = self.pending[focus] = self.pool.submit(self.agent.decide, self.case, snapshot, **kwargs)
            try:
                decision = future.result(timeout=self.lim.move_hard)
                reason = None
            except FutureTimeout:
                decision, reason = None, f"no decision within {self.lim.move_hard:.1f} s"
            except Exception as e:  # the agent failed: never the case
                decision, reason = None, f"agent raised {type(e).__name__}: {e}"
        took = time.monotonic() - t0
        if took > self.lim.move_warn and decision is not None:
            self.stats["slow"] += 1
            self.note(f"{focus}: slow decision, {took:.1f} s", logging.WARNING)
        if decision is not None:
            self.failures[focus] = 0
        else:
            self.failures[focus] = self.failures.get(focus, 0) + 1
            if self.failures[focus] >= 2:  # it fails again: close on what stands rather than burn the rounds
                self.broken = True
                self.note(
                    f"{focus}: {reason}, the second time in a row: closing the case on what stands", logging.ERROR
                )
                return None
        if decision is None:
            fallback = getattr(self.agent, "fallback", None)
            if fallback is not None and fallback is not self.agent:
                try:
                    decision = fallback.decide(self.case, copy.deepcopy(snapshot), **kwargs)
                    self.stats["fallbacks"] += 1
                    self.note(f"{focus}: {reason}; the agent's fallback decided", logging.WARNING)
                except Exception as e:
                    reason += f"; fallback raised {type(e).__name__}"
            if decision is None:
                live = live_threads(snapshot)
                target = focus if focus in live else (live[0] if live else None)
                if target is not None and moves_left(self.case, snapshot[target]) > 1:
                    decision = _hold(self.case, target)
                    self.stats["holds"] += 1
                    self.note(f"{target}: {reason}; holding e-mail instead", logging.WARNING)
                else:
                    decision = closing_move(self.case, snapshot) if live else None
                    self.note(f"{target}: {reason}; no message left, closing", logging.WARNING)
        self.stats["moves"] += 1
        return decision

    # -- closing -------------------------------------------------------------------------------
    def close(self, decision):
        """An accept or a walk-away, the thread re-read first. True when the case has ended."""
        with self.closing:
            return self.done.is_set() or self._close(decision)

    def _close(self, decision):
        target, action = decision["supplier_id"], decision["message"]["action"]
        if action["type"] == "accept":
            t0 = time.monotonic()  # a message to it still on its way gets a new offer ID with its reply
            while target in self.flying and time.monotonic() - t0 < self.lim.flight_wait:
                time.sleep(min(0.2, self.lim.idle))
            current = self.refresh(target).get("offer_id")
            if current != action.get("term_sheet_id"):
                old = action.get("term_sheet_id")
                self.note(f"{target}: offer ID changed before the accept ({old} -> {current}), deciding again")
                return False
        try:
            reply = self.post(target, decision["message"])
        except ArenaError as e:
            self.stats["refused"] += 1
            self.note(f"{target}: {action['type']} refused: {e}", logging.WARNING)
            if e.status in (409, 422):
                for s in list(self.threads):
                    self.refresh(s)
                if self.ended_on_server():
                    return True
                return False
            raise
        self.outcome["result"] = ended(reply.get("result", reply), ENDS.get(action["type"]))
        self.note(f"{target}: {action['type']} -> {self.outcome['result'].get('end_reason') or 'ended'}")
        self.done.set()
        return True

    def ended_on_server(self):
        state = self.client.session(self.sid)
        if state.get("status") == "ended":
            self.outcome["result"] = ended(state.get("result") or {"deal": False}, state.get("end_reason"))
            self.done.set()
            return True
        return False

    def documents(self, message):
        """The message with its attachments' text, waited for at most lim.docs. The arena answers an
        attachment of a session only after a pending reply in it (P05: 37-61 s while another bidder
        wrote); without the text the move goes on, the thread's clock matters more."""
        if not any(a.get("attachment_id") and "text" not in a for a in message.get("attachments") or []):
            return message
        msg = copy.deepcopy(message)  # filled in the worker; a late fill never touches the threads
        future = self.docs_pool.submit(fetch_documents, self.table, msg)
        try:
            return future.result(timeout=self.lim.docs)
        except FutureTimeout:
            self.stats["slow_docs"] += 1
            self.note(f"{message.get('from')}: attachments not there after {self.lim.docs:.0f} s, going on without",
                      logging.WARNING)  # fmt: skip
        except Exception as e:
            self.note(f"{message.get('from')}: attachments failed: {type(e).__name__}: {e}", logging.WARNING)
        return message

    def post(self, sup, message):
        """POST one message. With `lim.serial` one at a time per session: the arena works through a
        session's messages one after another, so with three bidders in flight a reply took up to 131 s
        and the message behind it was counted late (P05, docs/LOG.md Sat 21:23: a timeout on 70250 in
        every runner session, 0.665, against 0.820 with the kit's one-at-a-time play()). One message in
        flight gets its reply in seconds, so the others wait seconds, not minutes."""
        if not self.lim.serial:
            return self.client.send_message(self.sid, sup, message)
        with self.wire:
            return self.client.send_message(self.sid, sup, message)

    # -- the loops -----------------------------------------------------------------------------
    def send(self, sup, message):
        """One e-mail and its reply. Returns False if the loop should stop."""
        t0 = time.monotonic()
        try:
            reply = self.post(sup, message)
        except ArenaError as e:
            self.stats["refused"] += 1
            self.note(f"{sup}: send refused: {e}", logging.WARNING)
            with self.lock:
                self.flying.discard(sup)
            if e.status in (409, 422):
                if self.ended_on_server():
                    return False
                self.refresh(sup)
                return True
            raise
        with self.lock:
            self.heard[sup] = self.replied[sup] = time.monotonic()  # its 60 s run from here
            self.slowest = max(self.slowest, time.monotonic() - t0)
            if "result" in reply:
                self.flying.discard(sup)
                self.outcome["result"] = reply["result"]
                self.done.set()
                return False
        reply = self.documents(reply)  # outside the lock: the other threads keep playing meanwhile
        with self.lock:
            self.flying.discard(sup)
            self.threads[sup] += [{**message, "from": "buyer"}, reply]
            status = latest(self.threads[sup]).get("status")
        prices = [s.get("terms", {}).get("unit_price") for s in reply.get("term_sheets") or []]
        self.note(f"{sup}: sent {len(message.get('term_sheets') or [])} sheet(s); reply {status} {prices}")
        return True

    def loop(self, sup):
        """One supplier's thread (or, for an agent without `focus`, every thread: sup is None)."""
        while not self.done.is_set():
            if self.closing_due() or self.broken:
                return
            if sup is not None:
                if latest(self.threads[sup]).get("status") in ENDED:
                    return
                if time.monotonic() - self.heard[sup] > self.lim.silence:
                    self.refresh(sup)
                    self.heard[sup] = time.monotonic()
                    if latest(self.threads[sup]).get("status") in ENDED:
                        return
            elif not live_threads(self.threads):
                return
            decision = self.decide(sup)
            if self.done.is_set() or decision is None:
                return
            target, message = decision["supplier_id"], decision["message"]
            if message.get("action"):
                if message["action"]["type"] != "accept" and self.flying - {sup}:
                    decision = None  # a walk-away waits until no other reply is on its way
                elif self.close(decision):
                    return
                else:
                    decision = None
            elif sup is not None and target != sup:
                decision = None  # a move for another thread: its own loop sends it
            if decision is None:
                if any([self.guard_clock(s) for s in ([sup] if sup is not None else list(self.threads))]):
                    continue
                time.sleep(self.lim.idle)
                continue
            with self.lock:
                if target in self.flying:
                    decision = None
                else:
                    self.flying.add(target)
            if decision is None:
                time.sleep(self.lim.idle)
                continue
            if not self.send(target, message):
                return

    def guard_clock(self, sup):
        """A live thread must not run out of its 60 s while the agent works on another thread (sandbox
        D02: a waiting supplier hardened to its final offer, or withdrew). A holding e-mail keeps its
        offer and restarts its clock, at most max_holds times per thread. True if one was sent."""
        events = self.threads[sup]
        waited = time.monotonic() - self.replied.get(sup, time.monotonic())
        if latest(events).get("status") in ENDED or self.clock_holds.get(sup, 0) >= self.lim.max_holds:
            return False
        if waited < self.lim.hold_after or moves_left(self.case, events) <= 1:
            return False
        with self.lock:
            if sup in self.flying:
                return False
            self.flying.add(sup)
        self.clock_holds[sup] = self.clock_holds.get(sup, 0) + 1
        self.stats["clock_holds"] += 1
        status = latest(events).get("status")
        self.note(f"{sup}: {status}, unanswered for {waited:.0f} s while the agent works elsewhere: holding e-mail",
                  logging.WARNING)  # fmt: skip
        return self.send(sup, _hold(self.case, sup)["message"]) or True

    def finish(self):
        """Time is up or every loop ended: re-read everything and close on what stands."""
        if "result" in self.outcome or self.ended_on_server():
            return
        for s in list(self.threads):
            self.refresh(s)
        for attempt in range(3):
            if live_threads(self.threads):
                decision = closing_move(self.case, self.threads)
            else:
                decision = {"supplier_id": next(iter(self.threads)), "message": {"action": {"type": "walk_away"}}}
            self.note(f"closing: {decision['message']['action']}")
            try:
                reply = self.client.send_message(self.sid, decision["supplier_id"], decision["message"])
                self.outcome["result"] = reply.get("result", reply)
                return
            except ArenaError as e:
                self.note(f"closing refused ({attempt + 1}/3): {e}", logging.WARNING)
                if self.ended_on_server():
                    return
                for s in list(self.threads):
                    self.refresh(s)
        self.outcome["result"] = self.client.session(self.sid).get("result") or {"deal": False}

    def run(self):
        self.t_start = time.monotonic()
        crash = None
        try:
            if self.open():
                self.heard = {s: self.heard.get(s, time.monotonic()) for s in self.threads}
                self.replied = {s: self.replied.get(s, time.monotonic()) for s in self.threads}
                # `turns`: the agent chooses whom to write next, one message at a time, as in the kit's play().
                # In P05 that order (fewest of our messages first) gave 0.820 in five sessions; one loop per
                # thread gave 0.665 (timeouts at the arena) and 0.735 with `serial` (no timeout, but the
                # rivals' prices stood at other moments when each ask was priced)
                loops = list(self.threads) if self.takes_focus and not self.lim.turns else [None]
                with ThreadPoolExecutor(max_workers=len(loops), thread_name_prefix=f"thread-{self.case_id}") as pool:
                    for f in [pool.submit(self.loop, s) for s in loops]:
                        try:
                            f.result()
                        except Exception as e:  # keep going: a crash in one loop must not lose the case
                            crash = f"{type(e).__name__}: {e}"
                            self.note(f"a thread loop crashed: {crash}", logging.ERROR)
                            log.exception("%s loop crash", self.case_id)
                self.finish()
        except Exception as e:
            crash = crash or f"{type(e).__name__}: {e}"
            log.exception("%s failed", self.case_id)
        finally:
            self.pool.shutdown(wait=False, cancel_futures=True)
            self.docs_pool.shutdown(wait=False, cancel_futures=True)
        return self.row(crash)

    def row(self, crash):
        r = self.outcome.get("result") or {}
        return {
            "case_id": self.case_id,
            "session_id": getattr(self, "sid", None),
            "deal": r.get("deal"),
            "score": r.get("score"),
            "end_reason": r.get("end_reason"),
            "supplier": r.get("supplier_id"),
            "c_deal": r.get("c_deal"),
            "seconds": round(time.monotonic() - self.t_start, 1),
            "crash": crash,
            "stats": self.stats,
            "agent_stats": getattr(self.agent, "stats", None),
            "notes": self.notes[-40:],
        }


def play_case(client, case_id, agent, deadline=None, limits=None, case=None, retries=1):
    """One case; after a crash it is resumed once while time is left (the arena allows one session)."""
    row = CaseRunner(client, case_id, agent, deadline, limits, case).run()
    for _ in range(retries):
        if not row["crash"] or row["deal"] is not None and row.get("end_reason"):
            break
        log.warning("%s: resuming after a crash: %s", case_id, row["crash"])
        time.sleep(1.0)
        row = CaseRunner(client, case_id, agent, deadline, limits, case).run() | {"resumed_after": row["crash"]}
    return row


_WARM = threading.Lock()
_WARMED = []


def warm_up(new_agent):
    """Load once, in this thread, what the agent's first move would load in every thread at once.
    Found on Sat 21:15: the negotiator's first decide() builds sellm.intel's data source (the package's
    whole ID index) with no lock, so the 1-3 threads of every case of a wave built it in parallel and
    the first move took over 2 s even in a test; in a wave of 10 cases it could pass the arena's 60 s."""
    with _WARM:
        if _WARMED:
            return
        t0 = time.monotonic()
        try:
            agent = new_agent()
            package = getattr(agent, "package", None)
            if package is not None and hasattr(package, "lookup"):
                package.lookup("")  # its own ID index
            from sellm.intel import dossier

            dossier("sup:70110", ["part:310010"])  # the source the negotiator's dossier() calls use
            if package is not None:
                dossier("sup:70110", ["part:310010"], package=package)
        except Exception as e:  # warming is an optimisation: never a reason not to play
            log.warning("warm-up incomplete: %s", e)
        _WARMED.append(True)
        log.warning("warm-up: %.1f s", time.monotonic() - t0)


def run_final(client, new_agent, waves=5, parallel=10, limits=None, on_row=None):
    """The Live Final: wait for each wave, play its cases in parallel within its cap, stop after
    `waves` waves have closed and every case has finished. Returns {case_id: row}."""
    lim = limits or Limits()
    warm_up(new_agent)  # before the first wave, not during it
    started, closed, caps, rows = {}, set(), {}, {}
    pool = ThreadPoolExecutor(max_workers=parallel, thread_name_prefix="case")

    def one(case):
        wave = case["wave"]
        row = play_case(client, case["case_id"], new_agent(), lambda: caps.get(wave), lim, case)
        row["wave"] = wave
        rows[case["case_id"]] = row
        if on_row:
            on_row(row)
        return row

    announced = set()
    while len(closed) < waves or not all(f.done() for f in started.values()):
        try:
            cases = client.cases("final")
        except ArenaError as e:
            if e.status != 403:
                log.warning("case list: %s", e)
            cases = []
        for case in cases:
            wave = case.get("wave")
            if not case.get("open"):
                closed.add(wave)
                continue
            if case.get("seconds_left") is not None:
                caps[wave] = time.time() + float(case["seconds_left"])  # follows an extension
            if wave not in announced:
                announced.add(wave)
                log.warning("wave %s started: %s", wave, case.get("theme"))
            if case["case_id"] not in started and case.get("seconds_left"):
                log.info("%s: starting (wave %s, %.0f s left)", case["case_id"], wave, case["seconds_left"])
                started[case["case_id"]] = pool.submit(one, case)
        time.sleep(lim.poll)
    pool.shutdown(wait=True)
    return rows


def run_cases(client, case_ids, new_agent, parallel=10, limits=None, repeat=1, on_row=None):
    """Practice or sandbox cases, all in parallel (at most `parallel` sessions at once)."""
    warm_up(new_agent)
    rows = []
    jobs = [cid for cid in case_ids for _ in range(repeat)]
    with ThreadPoolExecutor(max_workers=min(parallel, 10), thread_name_prefix="case") as pool:
        futures = [pool.submit(play_case, client, cid, new_agent(), None, limits) for cid in jobs]
        for f in as_completed(futures):  # each row as soon as its case ends, not behind a slow one
            rows.append(f.result())
            if on_row:
                on_row(rows[-1])
    return rows


def agent_maker(name, data):
    """naive, llm, sellm as the kit's `arena` CLI, or any 'module:Class|function' taking the package."""
    if ":" not in name:
        from arena_kit.cli import agent_factory

        return agent_factory(name, data)
    package = None
    if data:
        from arena_kit.data import DataPackage

        package = DataPackage(data)
        package.lookup("")
    module, attr = name.split(":", 1)
    make = getattr(importlib.import_module(module), attr)
    return lambda: make(package)


def setup_logging(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s %(levelname).1s %(message)s", "%H:%M:%S")
    fh, sh = logging.FileHandler(path, encoding="utf-8"), logging.StreamHandler()
    fh.setFormatter(fmt)
    sh.setFormatter(fmt)
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers[:] = [fh, sh]


def label_sessions(rows, label):
    """Name the sessions in runs/labels.json, so scripts/pull-runs files them under this label."""
    path = ROOT / "runs" / "labels.json"
    try:
        labels = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        labels = {}
    for r in rows:
        if r.get("session_id"):
            labels[r["session_id"]] = label
    path.write_text(json.dumps(dict(sorted(labels.items())), indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def main(argv=None):
    from arena_kit.cli import load_env, pull_first

    load_env(ROOT / ".env")
    ap = argparse.ArgumentParser(prog="python -m sellm.runner", description=__doc__.split("\n\n")[0])
    ap.add_argument("--set", default="final", choices=["final", "practice", "sandbox"])
    ap.add_argument("--agent", default="sellm", help="naive, llm, sellm, or module:Class")
    ap.add_argument("--cases", nargs="*", default=[], help="practice/sandbox: case IDs (P01 or case:P01), or 'all'")
    ap.add_argument("--repeat", type=int, default=1, help="practice/sandbox: sessions per case")
    ap.add_argument("--waves", type=int, default=5)
    ap.add_argument("--parallel", type=int, default=10)
    ap.add_argument("--data", default=os.environ.get("ARENA_DATA", "data/package"))
    ap.add_argument("--label", default="", help="practice/sandbox: label the sessions for scripts/pull-runs")
    ap.add_argument("--serial", action="store_true", help="one message per session in flight (RFQ timeouts)")
    ap.add_argument("--turns", action="store_true", help="one loop per case, the agent picks the thread (kit order)")
    a = ap.parse_args(argv)
    if a.set == "final":
        pull_first(final=True)  # the final runs the commit that is checked out: report only
    else:
        pull_first(restart=argv is None)
    from arena_kit.client import ArenaClient

    stamp = time.strftime("%Y%m%d-%H%M%S")
    log_path = ROOT / "runs" / "logs" / f"{stamp}-runner-{a.set}.log"
    rows_path = log_path.with_suffix(".jsonl")
    setup_logging(log_path)
    commit = os.popen(f"git -C {ROOT} rev-parse --short HEAD 2>/dev/null").read().strip()
    log.warning("runner: set %s, agent %s, commit %s, log %s", a.set, a.agent, commit, log_path)
    client = ArenaClient()
    new_agent = agent_maker(a.agent, a.data)
    write_lock = threading.Lock()

    def on_row(row):
        with write_lock, open(rows_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, default=str) + "\n")
        log.warning("%s: %s score %.3f (%s s, re-reads/refused %s/%s, holds %s, fallbacks %s)", row["case_id"],
                    row["end_reason"], row["score"] or 0.0, row["seconds"], row["stats"].get("rereads"),
                    row["stats"].get("refused"), row["stats"].get("holds"), row["stats"].get("fallbacks"))  # fmt: skip

    lim = Limits(serial=a.serial or a.turns, turns=a.turns)
    if a.set == "final":
        rows = list(run_final(client, new_agent, a.waves, min(a.parallel, 10), limits=lim, on_row=on_row).values())
    else:
        ids = a.cases
        if not ids or ids == ["all"]:
            from arena_kit.play import hosted

            ids = [c["case_id"] for c in hosted(client.cases(a.set))]
        ids = [i if i.startswith("case:") else f"case:{i}" for i in ids]
        rows = run_cases(client, ids, new_agent, a.parallel, limits=lim, repeat=a.repeat, on_row=on_row)
        if a.label:
            label_sessions(rows, a.label)
    scores = [r["score"] or 0.0 for r in rows]
    if scores:
        log.warning("done: %d cases, mean %.1f, crashes %d, refused moves %d; rows in %s", len(rows),
                    100 * sum(scores) / len(scores), sum(1 for r in rows if r["crash"]),
                    sum(r["stats"]["refused"] for r in rows), rows_path)  # fmt: skip
    if client.practice_remaining is not None:
        log.warning("practice sessions left: %s", client.practice_remaining)


if __name__ == "__main__":
    main()
