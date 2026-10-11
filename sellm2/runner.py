# ruff: noqa: E501  (long sentences and messages)
"""Play cases against the arena: practice, sandbox, and the Live Final's waves.

One loop per case and one message in flight per session, the agent choosing the thread (fewest of
our messages first). That is how the kit's play() handles an RFQ, and it scored best there: the arena
works through a session's messages one after another, so parallel e-mails to three bidders were
counted late (P05: one loop per thread 0.665, one loop per case 0.820). On top of the kit's loop:

- every decision has a hard deadline (40 s; a slow or failing agent gives a holding e-mail, which
  keeps the standing offer and restarts the clock), and is logged with its reasons;
- a 422 (e.g. an offer ID replaced by a timeout) re-reads the thread and decides again instead of
  ending the case; a 409 reads what happened (late, ended, at the cap);
- an attachment is waited for at most 20 s (the arena may hold it behind another bidder's reply);
- a thread left waiting 45 s while the agent moves another one gets a holding e-mail (at most two);
- shortly before a wave's cap the case is closed by the agent's own close (the cheapest valid offer
  by our total cost, relationship term included, against our alternative), the kit's closing move
  as the last resort;
- a final case already started is resumed (409 'one session per case').

It calls only the case list, sessions, threads, attachments and messages - never the live feed
(/events, /screen, /leaderboard, /results), as the rules require.
"""

import concurrent.futures as cf
import json
import logging
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from arena_kit.client import ArenaError
from arena_kit.docs import read_document
from arena_kit.play import RemoteTable, closing_move, hosted, live_threads, quota_used_up, standing

log = logging.getLogger("sellm2")
ROOT = Path(__file__).resolve().parents[1]


@dataclass
class Limits:
    move_hard: float = 40.0  # a decision that takes longer is replaced by a holding e-mail
    docs: float = 20.0  # wait at most this long for an attachment
    hold_after: float = 40.0  # the best offer, final or agreed, waiting this long gets a holding e-mail
    max_holds: int = 2
    close_before_cap: float = 90.0  # close this long before a wave's cap ...
    round_margin: float = 15.0  # ... or the slowest round so far plus this margin
    max_case: float = 540.0  # practice/sandbox: give a case at most this long, then close it
    retries_422: int = 3
    poll: float = 5.0


_POOL = cf.ThreadPoolExecutor(max_workers=32, thread_name_prefix="sellm2-work")


def _within(fn, seconds, *args):
    """fn(*args) in a worker, or TimeoutError after `seconds`."""
    return _POOL.submit(fn, *args).result(timeout=seconds)


class CaseRun:
    def __init__(self, client, case, agent, cap=None, limits=None):
        self.client, self.case, self.agent = client, case, agent
        self.case_id = case["case_id"] if isinstance(case, dict) else case
        self.cap = cap  # a function returning the wave's cap as time.time(), or None
        self.lim = limits or Limits()
        self.table = RemoteTable(client, case if isinstance(case, dict) else None)
        self.seen = {}  # supplier -> time of its last message we received
        self.holds = {}
        self.stats = {"moves": 0, "refused": 0, "late": 0, "holds": 0, "slow": 0, "closed_at_cap": 0}
        self.slowest = 0.0
        self.started = time.time()

    # -- documents -------------------------------------------------------------------------------
    def docs(self, message):
        for att in message.get("attachments") or []:
            if att.get("attachment_id") and "text" not in att:
                try:
                    raw = _within(self.table.attachment, self.lim.docs, att["attachment_id"])
                    att["text"] = read_document(att.get("name", ""), raw)
                except Exception as e:  # without its text: the opening PDF is read already
                    log.warning("%s: attachment %s not read (%s)", self.case_id, att.get("name"), type(e).__name__)
        return message

    def reread(self, sid):
        """The thread as the arena has it now. A timeout follow-up (new offer ID) or the end of the
        thread is not always among its messages: it is added from the thread's state, so the agent
        never asks a supplier that has left, nor accepts an offer ID that was replaced."""
        t = self.client.thread(self.table.session_id, sid)
        msgs = [self.docs(dict(m)) for m in t.get("messages") or []]
        last = next((m for m in reversed(msgs) if m.get("from") != "buyer"), {})
        standing = ((last.get("term_sheets") or [{}])[0]).get("term_sheet_id")
        timeouts = t.get("timeouts") or []
        if t.get("closed") or t.get("status") in ("walked_away", "no_bid"):
            if last.get("status") not in ("walked_away", "no_bid"):
                text = (timeouts[-1].get("text") if timeouts else None) or "(the thread has ended)"
                msgs.append({"from": f"arena@{sid}", "status": t.get("status") if t.get("status") in ("walked_away", "no_bid") else "walked_away",
                             "term_sheets": [], "body": text, "attachments": []})  # fmt: skip
        elif timeouts and t.get("offer_id") and t.get("offer_id") != standing:
            to = timeouts[-1]
            msgs.append({"from": f"arena@{sid}", "status": to.get("status") or t.get("status"),
                         "term_sheets": [{"term_sheet_id": t["offer_id"], "terms": to.get("terms") or (last.get("term_sheets") or [{}])[0].get("terms", {})}],
                         "body": to.get("text") or "", "attachments": [], "missing_fields": to.get("missing_fields") or []})  # fmt: skip
        self.seen[sid] = time.time()
        return msgs

    # -- decisions -------------------------------------------------------------------------------
    def decide(self, threads):
        t0 = time.monotonic()
        try:
            d = _within(self.agent.decide, self.lim.move_hard, self.case, threads)
        except Exception as e:  # too slow or broken: keep the offers alive
            self.stats["slow"] += 1
            log.warning("%s: decision failed (%s) - holding e-mail", self.case_id, type(e).__name__)
            policy = getattr(self.agent, "policy", None)
            d = policy.rescue(self.case, threads) if policy else closing_move(self.case, threads)
        took = time.monotonic() - t0
        if took > 15:
            log.warning("%s: decision took %.1f s", self.case_id, took)
        return d

    def closing(self, threads):
        """Close now: the agent's own close (our cost incl. relationship term, our alternative)."""
        policy = getattr(self.agent, "policy", None)
        try:
            if policy is not None:
                from .model import CaseModel, Thread

                cm = CaseModel(self.case)
                views = [Thread(cm, s, ev) for s, ev in threads.items()]
                live = [v for v in views if v.live]
                if live:
                    draft = policy.close(cm, live, {v.sid: policy.offer_cost(cm, v) for v in live})
                    return policy.message(self.case, threads, draft)
        except Exception as e:
            log.warning("%s: own close failed (%s), kit closing move", self.case_id, e)
        return closing_move(self.case, threads)

    def waiting(self, threads, target):
        """The best standing offer, if it is a final offer or an agreement that has waited too long
        while the agent moves another bidder: a supplier at final_offer left over a minute withdrew
        (sandbox D02, P05). Only that thread is held: with one message in flight per session every
        hold costs the others a turn, so open threads are not held."""
        policy = getattr(self.agent, "policy", None)
        if policy is None or len(threads) < 2:
            return None
        from .model import READY, CaseModel, Thread

        cm = CaseModel(self.case)
        views = [Thread(cm, s, threads[s]) for s in live_threads(threads)]
        costs = {v.sid: policy.offer_cost(cm, v) for v in views}
        if not costs:
            return None
        best = min(costs, key=costs.get)
        v = next(v for v in views if v.sid == best)
        if best == target or v.status not in READY or costs[best] == float("inf"):
            return None
        if time.time() - self.seen.get(best, time.time()) > self.lim.hold_after and self.holds.get(best, 0) < self.lim.max_holds and v.left > 1:
            return best
        return None

    def hold_message(self, threads, sid):
        policy = getattr(self.agent, "policy", None)
        if policy is not None:
            draft = {"kind": "hold", "sid": sid, "sheets": [], "n": 0}
            return policy.message(self.case, threads, draft)["message"]
        return {"subject": f"Re: {self.case.get('title', '')}"[:300], "body": "Dear Sir or Madam,\n\nthank you, we are reviewing your offer and will revert shortly.\n\nBest regards", "term_sheets": []}

    # -- the loop --------------------------------------------------------------------------------
    def due(self):
        cap = self.cap() if callable(self.cap) else self.cap
        if cap is None:
            return time.time() - self.started > self.lim.max_case
        return time.time() > cap - max(self.lim.close_before_cap, self.slowest + self.lim.round_margin)

    def play(self, resume=None):
        case, threads = self.table.resume(resume) if resume else self.table.open(self.case_id)
        if isinstance(case, dict):
            self.case = case
        if getattr(self.table, "done", None):
            return self.table.done
        threads = {s: [self.docs(dict(m)) for m in ev] for s, ev in threads.items()}
        for s in threads:
            self.seen[s] = time.time()
        refused = 0
        while live_threads(threads):
            t0 = time.monotonic()
            closing = self.due()
            d = self.closing(threads) if closing else self.decide(threads)
            sid, msg = d["supplier_id"], d["message"]
            if not msg.get("action"):
                other = self.waiting(threads, sid)
                if other:
                    sid, msg = other, self.hold_message(threads, other)
                    self.holds[other] = self.holds.get(other, 0) + 1
                    self.stats["holds"] += 1
            try:
                if msg.get("action"):
                    if closing:
                        self.stats["closed_at_cap"] += 1
                    log.info("%s %s %s", self.case_id, sid, msg["action"])
                    return self.table.close(sid, msg)
                reply = self.table.send(sid, msg)
                refused = 0
            except ArenaError as e:
                if e.status == 422:
                    refused += 1
                    self.stats["refused"] += 1
                    log.warning("%s %s: refused (%s), re-reading the thread", self.case_id, sid, str(e.detail)[:120])
                    threads[sid] = self.reread(sid)
                    if refused >= self.lim.retries_422:
                        d = closing_move(self.case, threads)
                        return self.table.close(d["supplier_id"], d["message"])
                    continue
                if e.status != 409:
                    raise
                self.stats["late"] += 1
                log.info("%s %s: %s", self.case_id, sid, e.detail)
                state = self.client.session(self.table.session_id)
                if state.get("status") == "ended":
                    return state.get("result") or {"deal": False, "end_reason": state.get("end_reason")}
                threads[sid] = self.reread(sid)
                if self.stats["late"] > 30:  # something we do not understand: close on what stands
                    d = self.closing(threads)
                    if d["message"].get("action"):
                        return self.table.close(d["supplier_id"], d["message"])
                continue
            self.stats["moves"] += 1
            if "result" in reply:
                return reply["result"]
            threads[sid] = threads[sid] + [{**msg, "from": "buyer"}, self.docs(reply)]
            self.seen[sid] = time.time()
            self.slowest = max(self.slowest, time.monotonic() - t0)
            log.info("%s %s %s %s", self.case_id, sid, reply.get("status"), standing(threads[sid])[1].get("unit_price"))
        return self.table.result()


def play_case(client, case, new_agent, cap=None, limits=None):
    """One case to its end -> a row {case_id, session_id, score, deal, end_reason, seconds, stats, crash}."""
    t0 = time.time()
    run = CaseRun(client, case, new_agent(), cap, limits)
    crash, result = None, {}
    resume = None
    for attempt in range(2):
        try:
            result = run.play(resume) or {}
            crash = None
            break
        except Exception as e:  # one broken case must not stop the others: resume it once
            crash = f"{type(e).__name__}: {e}"
            log.exception("%s failed", run.case_id)
            resume = run.table.session_id
            if quota_used_up(e) or attempt == 1 or not resume:
                break
            stats, known = run.stats, run.case
            run = CaseRun(client, known if isinstance(known, dict) else case, new_agent(), cap, limits)
            run.case_id = known.get("case_id", run.case_id) if isinstance(known, dict) else run.case_id
            run.stats = stats
    row = {
        "case_id": run.case_id,
        "session_id": run.table.session_id,
        "score": result.get("score"),
        "deal": result.get("deal"),
        "end_reason": result.get("end_reason") or ("accepted" if result.get("deal") else ("no_deal" if result else None)),
        "terms": result.get("terms"),
        "seconds": round(time.time() - t0, 1),
        "stats": run.stats,
        "crash": crash,
    }
    log.warning("%s: score %s, %s, %s s, %s", row["case_id"], row["score"], row["end_reason"], row["seconds"], run.stats)
    return row


def run_cases(client, case_ids, new_agent, parallel=8, repeat=1, on_row=None):
    rows, jobs = [], [c for c in case_ids for _ in range(repeat)]
    with cf.ThreadPoolExecutor(max_workers=min(parallel, 10), thread_name_prefix="case") as pool:
        futures = [pool.submit(play_case, client, c, new_agent) for c in jobs]
        for f in cf.as_completed(futures):
            rows.append(f.result())
            if on_row:
                on_row(rows[-1])
    return rows


def run_final(client, new_agent, waves=5, parallel=10, poll=5.0, on_row=None, limits=None):
    """The Live Final: wait for each wave, play its cases in parallel within the wave's cap (following
    an extension), resume a case already started, stop after `waves` waves have closed."""
    started, closed, caps, rows = {}, set(), {}, {}
    lock = threading.Lock()

    def one(case):
        row = play_case(client, case, new_agent, lambda: caps.get(case["wave"]), limits)
        with lock:
            rows[case["case_id"]] = row
        if on_row:
            on_row(row)
        return row

    with cf.ThreadPoolExecutor(max_workers=min(parallel, 10), thread_name_prefix="final") as pool:
        while len(closed) < waves or not all(f.done() for f in started.values()):
            try:
                cases = client.cases("final")
            except ArenaError as e:
                if e.status != 403:  # 403: no wave has started yet
                    log.warning("case list: %s", e)
                cases = []
            except Exception as e:  # the network: try again at the next poll
                log.warning("case list: %s", e)
                cases = []
            for case in cases:
                if not case.get("open"):
                    closed.add(case.get("wave"))
                    continue
                if case.get("seconds_left") is not None:
                    caps[case["wave"]] = time.time() + case["seconds_left"]
                if case["case_id"] not in started and case.get("seconds_left"):
                    log.warning("wave %s: starting %s (%s s left)", case.get("wave"), case["case_id"], int(case["seconds_left"]))
                    started[case["case_id"]] = pool.submit(one, case)
            time.sleep(poll)
    return rows


def label_sessions(rows, label):
    path = ROOT / "runs" / "labels.json"
    try:
        labels = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        labels = {}
    for r in rows:
        if r.get("session_id"):
            labels[r["session_id"]] = label
    path.write_text(json.dumps(dict(sorted(labels.items())), indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def case_list(client, set_, ids):
    if not ids or ids == ["all"]:
        return [c["case_id"] for c in hosted(client.cases(set_))]
    return [i if i.startswith("case:") else f"case:{i}" for i in ids]
