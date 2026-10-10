# ruff: noqa: E501  (long e-mail texts)
"""Sandbox probes for the hypotheses in runs/BASELINE.md.

Free: sandbox sessions do not use the practice quota. Each probe plays one sandbox session with a
fixed script (H1, H2, H8) or with the kit's LLM agent (H3) and prints what the supplier did. The
full sessions are saved afterwards by `scripts/pull-runs`; this script only labels them. Results
and what follows from them: experiments/RESULTS.md.

    uv run python experiments/sandbox_probes.py h1a h1c h2-push h2-hold --repeat 2   # case D01
    uv run python experiments/sandbox_probes.py h3-seq h3-par --repeat 2             # case D02

H1  can a supplier's alternative term sheet be accepted by its ID?
    h1a: accept it in the round it was offered; h1b: one round later;
    h1c: send the alternative's terms back as our own sheet, then accept what the supplier agrees
H2  what happens after `final_offer`?
    h2-trade: lower price plus a give (earlier start); h2-push: lower price only;
    h2-shift: same price, later start; h2-hold: a holding message without a term sheet
H3  RFQ: how to keep every thread inside its 60 seconds?
    h3-seq: the kit's play(), one thread at a time; h3-par: one loop per thread, each answering as
    soon as its own reply arrives, accepting the first ready thread if it is the cheapest
H8  what does the supplier's final price follow: our level or our steps?
    h8-low: open at 49.00 instead of 50.00; h8-slow: steps of 0.05 instead of 0.15
H10 does the supplier come down further when we move further? (follows from H8)
    h10-a: open at 48.60, steps of 0.30; h10-b: open at 48.00, steps of 0.40
H11 RFQ: does citing the rival's standing offer by its ID pull prices down?
    h11: scripted, one loop per thread, every e-mail cites the other supplier's offer if it is lower
"""

import argparse
import json
import math
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from arena_kit.agents import LLMAgent, llm_from_env  # noqa: E402
from arena_kit.cli import load_env  # noqa: E402
from arena_kit.client import ArenaClient, ArenaError  # noqa: E402
from arena_kit.cost import complete_offer, must_haves_ok, total_cost  # noqa: E402
from arena_kit.data import DataPackage  # noqa: E402
from arena_kit.docs import standard_terms  # noqa: E402
from arena_kit.play import ENDED, RemoteTable, fetch_documents, latest, live_threads, moves_left, play  # noqa: E402

LABELS = ROOT / "runs" / "labels.json"
SIGN = "\n\nBest regards\nPurchasing, Hollerau Pumpenwerke"
READY = {"final_offer", "agreed"}


class Session:
    """One sandbox session driven by a script, with a record of every step."""

    def __init__(self, client, case_id):
        self.client = client
        opened = client.open_session(case_id)
        self.sid, self.case, self.threads = opened["session_id"], opened["case"], opened["threads"]
        self.steps, self.last_reply_at = [], time.monotonic()
        for events in self.threads.values():
            for message in events:
                fetch_documents(self, message)

    def attachment(self, attachment_id):
        return self.client.attachment(self.sid, attachment_id)

    def sheets(self, supplier):
        """Every term sheet in the supplier's latest e-mail: (id, terms, C, keeps the must-haves)."""
        std = standard_terms(self.threads[supplier])
        return [
            (s["term_sheet_id"], s["terms"], total_cost(self.case, s["terms"], std), must_haves_ok(self.case, s["terms"], std))
            for s in latest(self.threads[supplier]).get("term_sheets") or []
        ]

    def send(self, supplier, body, sheets, note):
        message = {
            "subject": self.case["title"],
            "body": body + SIGN,
            "term_sheets": [{"terms": complete_offer(self.case, s)} for s in sheets],
        }
        return self.post(supplier, message, note)

    def post(self, supplier, message, note):
        """Send a ready message and record the supplier's reply."""
        waited = time.monotonic() - self.last_reply_at
        t0 = time.monotonic()
        try:
            reply = self.client.send_message(self.sid, supplier, message)
        except ArenaError as e:
            self.steps.append({"note": note, "to": supplier, "error": str(e)})
            raise
        self.last_reply_at = time.monotonic()
        self.threads[supplier] += [{**message, "from": "buyer"}, fetch_documents(self, reply)]
        self.steps.append(
            {
                "note": note,
                "to": supplier,
                "sent": [s["terms"] for s in message.get("term_sheets") or []],
                "seconds_since_their_reply": round(waited, 1),
                "reply_seconds": round(self.last_reply_at - t0, 1),
                "status": reply.get("status"),
                "their_sheets": [{"id": i, "terms": t, "c": c} for i, t, c, _ in self.sheets(supplier)],
                "claim_results": reply.get("claim_results"),
            }
        )
        return reply

    def accept(self, supplier, sheet_id, note):
        try:
            out = self.client.send_message(self.sid, supplier, {"action": {"type": "accept", "term_sheet_id": sheet_id}})
        except ArenaError as e:
            self.steps.append({"note": note, "to": supplier, "accept": sheet_id, "error": str(e)})
            return None
        result = out.get("result", out)
        self.steps.append({"note": note, "to": supplier, "accept": sheet_id, "deal": result.get("deal"), "score": result.get("score")})
        return result

    def close(self, supplier):
        """Accept the supplier's standing sheet (only the first sheet of an e-mail can be accepted)."""
        offered = self.sheets(supplier)
        if offered and offered[0][3]:
            result = self.accept(supplier, offered[0][0], "accept the standing sheet")
            if result:
                return result
        return self.result()

    def result(self):
        state = self.client.session(self.sid)
        return state.get("result") or {"deal": False, "end_reason": state.get("end_reason")}

    def summary(self, probe, result, **extra):
        return {
            "probe": probe,
            "session_id": self.sid,
            "case_id": self.case["case_id"],
            "deal": result.get("deal"),
            "score": result.get("score"),
            "c_deal": result.get("c_deal"),
            "timeouts": {s: len(self.client.thread(self.sid, s).get("timeouts") or []) for s in self.threads},
            **extra,
            "steps": self.steps,
        }


def h1(client, mode):
    """D01: ask for two payment variants so the supplier sends an alternative, then try to take the
    alternative: accept its ID at once (a), one round later (b), or send its terms back as ours (c)."""
    s = Session(client, "case:D01")
    sup = s.case["suppliers"][0]
    base = {"unit_price": 50.0, "contract_months": 24, "effective_date": "2027-02-01"}
    body = (
        "Dear Mr Moser,\n\nthank you for your offer and for twelve years of reliable supply. A two-year "
        "commitment gives you planning security. Could you quote both variants below, one with 60 and one "
        "with 30 days payment, so that we can compare them?"
    )
    s.send(sup, body, [{**base, "payment_days": 60}, {**base, "payment_days": 30}], "ask for two payment variants")
    for attempt in range(2):
        if len(s.sheets(sup)) > 1 or latest(s.threads[sup]).get("status") in ENDED:
            break
        body = "Dear Mr Moser,\n\nthank you. Could you also state the price for the 30-day variant next to the 60-day one?"
        step = {**base, "unit_price": 50.2 + 0.1 * attempt}
        s.send(sup, body, [{**step, "payment_days": 60}, {**step, "payment_days": 30}], "ask again for two variants")
    offered = s.sheets(sup)
    if len(offered) < 2:
        return s.summary(f"h1{mode}", s.close(sup), verdict="inconclusive: the supplier sent no alternative")
    alt_id, alt_terms, _, _ = min(offered[1:], key=lambda x: x[2])
    if mode == "c":
        body = (
            "Dear Mr Moser,\n\nthank you for both variants. We would like to go with your second variant, "
            f"EUR {alt_terms['unit_price']:.2f} at {alt_terms['payment_days']} days. Please confirm."
        )
        reply = s.send(sup, body, [alt_terms], "send the alternative's terms back as our sheet")
        now_id, now_terms, _, _ = s.sheets(sup)[0]
        same = all(now_terms.get(k) == alt_terms.get(k) for k in s.case["negotiable"])
        verdict = f"status {reply.get('status')}, standing sheet {'equals' if same else 'differs from'} the alternative"
        return s.summary("h1c", s.close(sup), alternative_id=alt_id, verdict=verdict)
    if mode == "b":
        body = "Dear Mr Moser,\n\nthank you for both variants. Could you improve the 30-day variant to EUR 50.60?"
        s.send(sup, body, [{**base, "unit_price": 50.6, "payment_days": 30}], "one more round, then accept the old alternative")
    result = s.accept(sup, alt_id, "accept the alternative by its ID")
    verdict = "accepted" if result else f"refused: {s.steps[-1].get('error')}"
    return s.summary(f"h1{mode}", result or s.close(sup), alternative_id=alt_id, verdict=verdict)


def h2(client, variant, start=50.0, step=0.15, name=None):
    """D01: concede in small steps until the supplier says final_offer, then answer with one move."""
    name = name or f"h2-{variant}"
    s = Session(client, "case:D01")
    sup = s.case["suppliers"][0]
    fixed = {"payment_days": 30, "contract_months": 24, "effective_date": "2027-02-01"}
    ask = start
    body = (
        "Dear Mr Moser,\n\nthank you for your offer and for twelve years of reliable supply. We would like "
        "to settle this in a way that works for both sides. A two-year commitment gives you planning security; "
        "in return we ask for the package below."
    )
    reply = s.send(sup, body, [{**fixed, "unit_price": ask}], "opening ask")
    for _ in range(7):
        if reply.get("status") != "open":
            break
        ask = round(max(ask, min(ask + step, s.sheets(sup)[0][1]["unit_price"] - 0.3)), 2)  # stay below them
        body = f"Dear Mr Moser,\n\nthank you for moving. We can improve our proposal to EUR {ask:.2f} per housing on the same terms. Could you meet us there?"
        reply = s.send(sup, body, [{**fixed, "unit_price": ask}], "small concession")
    reached = reply.get("status")
    if reached in ENDED:
        return s.summary(name, s.result(), reached=reached, verdict="ended before the test")
    _, theirs, c_before, _ = s.sheets(sup)[0]
    facts = {"reached": reached, "our_messages": len(s.steps), "their_price": theirs["unit_price"], "our_last_ask": ask, "c_before": c_before}
    if variant == "none":
        return s.summary(name, s.close(sup), **facts)
    dates = s.case["term_options"]["effective_date"]
    price = round(theirs["unit_price"] - 0.3, 2)
    if variant == "trade":
        earlier = dates[max(dates.index(theirs["effective_date"]) - 1, 0)]
        sheets = [{**theirs, "unit_price": price, "effective_date": earlier}]
        body = (
            "Dear Mr Moser,\n\nunderstood, and thank you for the clear answer. One more idea that should help you "
            f"as well: we can accept the new price a month earlier, from {earlier}, if you can do EUR {price:.2f} "
            "per housing. Otherwise the terms stay as they are."
        )
    elif variant == "push":
        sheets = [{**theirs, "unit_price": price}]
        body = f"Dear Mr Moser,\n\nthank you. We are close. Could you do EUR {price:.2f} per housing on the same terms? Then we have an agreement."
    elif variant == "shift":
        sheets = [{**theirs, "effective_date": dates[-1]}]
        body = (
            f"Dear Mr Moser,\n\nthank you, the price works for us. Could the new price apply from {dates[-1]} "
            "instead? That would align it with our budget year. Everything else stays as offered."
        )
    else:  # hold: no term sheet, no ask
        sheets = []
        body = (
            "Dear Mr Moser,\n\nthank you for your final offer. We are taking it through our internal approval "
            "and will confirm shortly. There are no further changes from our side."
        )
    try:
        after = s.send(sup, body, sheets, f"answer to {reached}: {variant}")
    except ArenaError:
        return s.summary(name, s.result(), **facts, verdict="message refused")
    status = after.get("status")
    c_after = s.sheets(sup)[0][2] if s.sheets(sup) else None
    result = s.result() if status in ENDED else s.close(sup)
    gained = None if c_after is None else round(c_before - c_after, 2)
    return s.summary(name, result, **facts, status_after=status, c_after=c_after, gained=gained)


class ThreadAgent(LLMAgent):
    """The kit's LLM agent, told to write to one supplier. It still sees every thread of the case."""

    def __init__(self, complete, package, target):
        super().__init__(complete, package)
        self.target = target

    def render(self, case, threads):
        return super().render(case, threads) + f"\n\nIn this reply write to supplier {self.target} only (supplier_id {self.target})."

    def guard(self, case, threads, d):
        return super().guard(case, threads, {**d, "supplier_id": self.target})

    def decide(self, case, threads):
        out = super().decide(case, threads)
        return out if out["supplier_id"] == self.target else self.fallback.decide(case, {self.target: threads[self.target]})


def h3_seq(client, complete, package):
    """D02 with the kit's play(): one thread at a time."""
    table = RemoteTable(client)
    result = play(table, "case:D02", LLMAgent(complete, package))
    state = client.session(table.session_id)
    return {
        "probe": "h3-seq",
        "session_id": table.session_id,
        "case_id": "case:D02",
        "deal": result.get("deal"),
        "score": result.get("score"),
        "c_deal": result.get("c_deal"),
        "supplier": result.get("supplier_id"),
        "timeouts": {s: len(client.thread(table.session_id, s).get("timeouts") or []) for s in state["threads"]},
        "thread_status": {s: (t["status"], t["closed"]) for s, t in state["threads"].items()},
        "rounds": state.get("rounds"),
    }


def h3_par(client, complete, package):
    """D02 with one loop per thread. A thread answers as soon as its own reply arrives, so no thread
    waits on another. When a thread is ready to close (final_offer, agreed, the agent wants to
    accept, or no messages left) it is accepted at once if it is the cheapest standing sheet of the
    case and beats the alternative; otherwise we leave that thread. A ready thread is never held:
    a supplier at final_offer that hears nothing for 60 seconds withdraws."""
    s = Session(client, "case:D02")
    agents = {sup: ThreadAgent(complete, package, sup) for sup in s.threads}
    lock, done, outcome = threading.Lock(), threading.Event(), {}
    alt = s.case["buyer"].get("alternative") or {}
    c_alt = total_cost(s.case, alt["terms"]) if alt.get("terms", {}).get("unit_price") else math.inf

    def standing_c(sup):
        offered = s.sheets(sup)
        return offered[0][2] if offered and offered[0][3] else math.inf

    def loop(sup):
        while not done.is_set():
            events = s.threads[sup]
            status = latest(events).get("status")
            if status in ENDED:
                return
            ready = status in READY or moves_left(s.case, events) <= 0
            message = None
            if not ready:
                message = agents[sup].decide(s.case, s.threads)["message"]
                kind = (message.get("action") or {}).get("type")
                if kind == "walk_away":
                    s.steps.append({"note": "the agent leaves this thread", "to": sup})
                    return
                ready = kind == "accept"
            if ready:
                with lock:
                    if done.is_set():
                        return
                    mine = standing_c(sup)
                    others = [standing_c(o) for o in live_threads(s.threads) if o != sup]
                    if mine < c_alt and mine <= min(others, default=math.inf):
                        result = s.accept(sup, s.sheets(sup)[0][0], f"ready ({status}) and cheapest: accept at once")
                        if result:
                            outcome["result"] = result
                            done.set()
                        return
                    s.steps.append({"note": f"ready ({status}) but not the cheapest (C {mine:,.0f}): leave this thread", "to": sup})
                    return
            try:
                s.post(sup, message, "negotiate")
            except ArenaError:
                return

    with ThreadPoolExecutor(max_workers=len(s.threads)) as pool:
        list(pool.map(loop, list(s.threads)))
    result = outcome.get("result")
    if result is None:  # nobody was accepted in time: take what still stands, cheapest first
        for sup in sorted(s.threads, key=standing_c):
            thread = client.thread(s.sid, sup)
            if thread.get("offer_id") and not thread.get("closed") and standing_c(sup) < c_alt:
                result = s.accept(sup, thread["offer_id"], "late accept of what still stands")
                if result:
                    break
    if result is None:
        try:
            out = client.send_message(s.sid, next(iter(s.threads)), {"action": {"type": "walk_away"}})
            result = out.get("result", out)
        except ArenaError:
            result = s.result()
        s.steps.append({"note": "no acceptable sheet left: walk away"})
    state = client.session(s.sid)
    return s.summary(
        "h3-par",
        result,
        supplier=result.get("supplier_id"),
        thread_status={sup: (t["status"], t["closed"]) for sup, t in state["threads"].items()},
        rounds=state.get("rounds"),
    )


def h11(client):
    """D02, scripted: one loop per thread. Each e-mail asks for 0.40 less than the lower of the two
    standing prices and, when the other supplier is cheaper, cites that offer by its ID. A ready
    thread is accepted at once if it is the cheapest standing sheet, else left (as in h3-par)."""
    s = Session(client, "case:D02")
    lock, done, outcome = threading.Lock(), threading.Event(), {}
    alt = s.case["buyer"]["alternative"]
    c_alt = total_cost(s.case, alt["terms"])

    def standing_c(sup):
        offered = s.sheets(sup)
        return offered[0][2] if offered and offered[0][3] else math.inf

    def loop(sup):
        while not done.is_set():
            events = s.threads[sup]
            status = latest(events).get("status")
            if status in ENDED:
                return
            if status in READY or moves_left(s.case, events) <= 0:
                with lock:
                    if done.is_set():
                        return
                    mine = standing_c(sup)
                    others = [standing_c(o) for o in live_threads(s.threads) if o != sup]
                    if mine < c_alt and mine <= min(others, default=math.inf):
                        result = s.accept(sup, s.sheets(sup)[0][0], f"ready ({status}) and cheapest: accept at once")
                        if result:
                            outcome["result"] = result
                            done.set()
                        return
                    s.steps.append({"note": f"ready ({status}) but not the cheapest (C {mine:,.0f}): leave this thread", "to": sup})
                    return
            mine = s.sheets(sup)[0][1]
            rivals = [s.sheets(o)[0] for o in live_threads(s.threads) if o != sup and s.sheets(o)]
            rival = min(rivals, key=lambda x: x[1]["unit_price"]) if rivals else None
            low = min([mine["unit_price"]] + ([rival[1]["unit_price"]] if rival else []))
            target = round(low - 0.4, 2)
            sheet = {**mine, "unit_price": target, "lead_time_days": 35}
            message = {"subject": s.case["title"], "term_sheets": [{"terms": complete_offer(s.case, sheet)}]}
            if rival and rival[1]["unit_price"] < mine["unit_price"]:
                message["refs"] = [rival[0]]
                message["body"] = (
                    "Dear Sir or Madam,\n\nthank you for your offer. We are comparing two qualified suppliers for this shaft. "
                    f"The other supplier currently offers EUR {rival[1]['unit_price']:.2f} per unit ({rival[0]}). "
                    f"If you can do EUR {target:.2f} on the terms below, the order is yours." + SIGN
                )
            else:
                message["body"] = (
                    "Dear Sir or Madam,\n\nthank you for your offer. You are currently ahead of the other supplier we are "
                    f"talking to, and we expect them to improve. If you can do EUR {target:.2f} on the terms below, the order is yours." + SIGN
                )
            try:
                s.post(sup, message, "cite the rival" if message.get("refs") else "ask the leader for more")
            except ArenaError:
                return

    with ThreadPoolExecutor(max_workers=len(s.threads)) as pool:
        list(pool.map(loop, list(s.threads)))
    result = outcome.get("result")
    if result is None:
        for sup in sorted(s.threads, key=standing_c):
            thread = client.thread(s.sid, sup)
            if thread.get("offer_id") and not thread.get("closed") and standing_c(sup) < c_alt:
                result = s.accept(sup, thread["offer_id"], "late accept of what still stands")
                if result:
                    break
    result = result or s.result()
    state = client.session(s.sid)
    return s.summary(
        "h11",
        result,
        supplier=result.get("supplier_id"),
        thread_status={sup: (t["status"], t["closed"]) for sup, t in state["threads"].items()},
        rounds=state.get("rounds"),
    )


def main():
    probes = ["h1a", "h1b", "h1c", "h2-trade", "h2-push", "h2-shift", "h2-hold", "h3-seq", "h3-par", "h8-low", "h8-slow", "h10-a", "h10-b", "h11"]
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("probes", nargs="+", choices=probes)
    ap.add_argument("--repeat", type=int, default=1, help="how often to run each probe (suppliers vary)")
    ap.add_argument("--workers", type=int, default=6, help="sessions at once (the key allows 10 open sessions)")
    ap.add_argument("--out", help="write the summaries to this JSON file")
    args = ap.parse_args()
    load_env()
    client = ArenaClient()
    complete = package = None
    if any(p.startswith("h3") for p in args.probes):
        complete, package = llm_from_env(), DataPackage(os.environ.get("ARENA_DATA", "data/package"))
        package.lookup("")
    jobs = {
        "h1a": lambda: h1(client, "a"),
        "h1b": lambda: h1(client, "b"),
        "h1c": lambda: h1(client, "c"),
        "h2-trade": lambda: h2(client, "trade"),
        "h2-push": lambda: h2(client, "push"),
        "h2-shift": lambda: h2(client, "shift"),
        "h2-hold": lambda: h2(client, "hold"),
        "h3-seq": lambda: h3_seq(client, complete, package),
        "h3-par": lambda: h3_par(client, complete, package),
        "h8-low": lambda: h2(client, "none", start=49.0, name="h8-low"),
        "h8-slow": lambda: h2(client, "none", step=0.05, name="h8-slow"),
        "h10-a": lambda: h2(client, "none", start=48.6, step=0.3, name="h10-a"),
        "h10-b": lambda: h2(client, "none", start=48.0, step=0.4, name="h10-b"),
        "h11": lambda: h11(client),
    }
    todo = [p for p in args.probes for _ in range(args.repeat)]

    def run(probe):
        try:
            return jobs[probe]()
        except Exception as e:  # one failed probe must not lose the others
            return {"probe": probe, "error": f"{type(e).__name__}: {e}"}

    with ThreadPoolExecutor(max_workers=min(len(todo), args.workers)) as pool:
        results = list(pool.map(run, todo))
    labels = json.loads(LABELS.read_text(encoding="utf-8")) if LABELS.is_file() else {}
    for r in results:
        if r.get("session_id"):
            labels[r["session_id"]] = f"probe {r['probe']}"
    LABELS.write_text(json.dumps(labels, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    text = json.dumps(results, indent=1, ensure_ascii=False)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
