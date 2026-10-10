# ruff: noqa: E501  (long e-mail texts)
"""Sandbox probes for the hypotheses H1-H3 in runs/BASELINE.md.

Free: sandbox sessions do not use the practice quota. Each probe plays one sandbox session with a
fixed script (H1, H2) or with the kit's LLM agent (H3) and prints what the supplier did. The full
sessions are saved afterwards by `scripts/pull-runs`; this script only labels them.

    uv run python experiments/sandbox_probes.py h1a h1b h2-trade h2-push h2-shift   # case D01
    uv run python experiments/sandbox_probes.py h3-seq h3-par --repeat 2            # case D02

H1  can a supplier's alternative term sheet be accepted by its ID?
    h1a: accept the alternative in the round it was offered; h1b: one round later (stale?)
H2  what happens after `final_offer`?
    h2-trade: lower price plus a give (earlier start); h2-push: lower price only;
    h2-shift: same price, later start
H3  does writing to all RFQ threads in parallel remove the timeouts?
    h3-seq: the kit's play() as it is; h3-par: one LLM agent per thread, sent together
"""

import argparse
import json
import sys
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
from arena_kit.play import (  # noqa: E402
    ENDED,
    RemoteTable,
    closing_move,
    fetch_documents,
    latest,
    live_threads,
    play,
)

LABELS = ROOT / "runs" / "labels.json"
SIGN = "\n\nBest regards\nPurchasing, Hollerau Pumpenwerke"


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
        waited = time.monotonic() - self.last_reply_at
        t0 = time.monotonic()
        try:
            reply = self.client.send_message(self.sid, supplier, message)
        except ArenaError as e:
            self.steps.append({"note": note, "error": str(e)})
            raise
        self.last_reply_at = time.monotonic()
        self.threads[supplier] += [{**message, "from": "buyer"}, fetch_documents(self, reply)]
        self.steps.append(
            {
                "note": note,
                "sent": [s["terms"] for s in message["term_sheets"]],
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
            self.steps.append({"note": note, "accept": sheet_id, "error": str(e)})
            return None
        result = out.get("result", out)
        self.steps.append({"note": note, "accept": sheet_id, "deal": result.get("deal"), "score": result.get("score")})
        return result

    def close(self, supplier):
        """Accept the cheapest sheet in the latest e-mail that keeps the must-haves; first sheet if that fails."""
        offered = [s for s in self.sheets(supplier) if s[3]]
        for sheet_id in dict.fromkeys([min(offered, key=lambda s: s[2])[0], offered[0][0]] if offered else []):
            result = self.accept(supplier, sheet_id, "close on the cheapest sheet by C")
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


def h1(client, stale):
    """D01: ask for two payment variants so the supplier sends an alternative, then accept the
    alternative by its ID - at once (h1a) or one round later (h1b)."""
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
        return s.summary("h1b" if stale else "h1a", s.close(sup), verdict="inconclusive: the supplier sent no alternative")
    alt_id = min(offered[1:], key=lambda x: x[2])[0]
    if stale:
        body = "Dear Mr Moser,\n\nthank you for both variants. Could you improve the 30-day variant to EUR 50.60?"
        s.send(sup, body, [{**base, "unit_price": 50.6, "payment_days": 30}], "one more round, then accept the old alternative")
    result = s.accept(sup, alt_id, "accept the alternative from one round earlier" if stale else "accept the alternative at once")
    verdict = "accepted" if result else f"refused: {s.steps[-1].get('error')}"
    return s.summary("h1b" if stale else "h1a", result or s.close(sup), alternative_id=alt_id, verdict=verdict)


def h2(client, variant):
    """D01: concede slowly until the supplier says final_offer, then answer with one of three moves."""
    s = Session(client, "case:D01")
    sup = s.case["suppliers"][0]
    fixed = {"payment_days": 30, "contract_months": 24, "effective_date": "2027-02-01"}
    ask = 50.0
    body = (
        "Dear Mr Moser,\n\nthank you for your offer and for twelve years of reliable supply. We would like "
        "to settle this in a way that works for both sides. A two-year commitment gives you planning security; "
        "in return we ask for the package below."
    )
    reply = s.send(sup, body, [{**fixed, "unit_price": ask}], "opening ask")
    for _ in range(6):
        if reply.get("status") != "open":
            break
        ask = round(max(ask, min(ask + 0.15, s.sheets(sup)[0][1]["unit_price"] - 0.3)), 2)  # stay below them
        body = f"Dear Mr Moser,\n\nthank you for moving. We can improve our proposal to EUR {ask:.2f} per housing on the same terms. Could you meet us there?"
        reply = s.send(sup, body, [{**fixed, "unit_price": ask}], "small concession")
    reached = reply.get("status")
    if reached in ENDED:
        return s.summary(f"h2-{variant}", s.result(), reached=reached, verdict="ended before the test")
    _, theirs, c_before, _ = s.sheets(sup)[0]
    dates = s.case["term_options"]["effective_date"]
    price = round(theirs["unit_price"] - 0.3, 2)
    if variant == "trade":
        earlier = dates[max(dates.index(theirs["effective_date"]) - 1, 0)]
        sheet = {**theirs, "unit_price": price, "effective_date": earlier}
        body = (
            "Dear Mr Moser,\n\nunderstood, and thank you for the clear answer. One more idea that should help you "
            f"as well: we can accept the new price a month earlier, from {earlier}, if you can do EUR {price:.2f} "
            "per housing. Otherwise the terms stay as they are."
        )
    elif variant == "push":
        sheet = {**theirs, "unit_price": price}
        body = f"Dear Mr Moser,\n\nthank you. We are close. Could you do EUR {price:.2f} per housing on the same terms? Then we have an agreement."
    else:  # shift: same price, later start
        sheet = {**theirs, "effective_date": dates[-1]}
        body = (
            f"Dear Mr Moser,\n\nthank you, the price works for us. Could the new price apply from {dates[-1]} "
            "instead? That would align it with our budget year. Everything else stays as offered."
        )
    try:
        after = s.send(sup, body, [sheet], f"answer to {reached}: {variant}")
    except ArenaError:
        return s.summary(f"h2-{variant}", s.result(), reached=reached, verdict="message refused")
    status = after.get("status")
    c_after = s.sheets(sup)[0][2] if s.sheets(sup) else None
    result = s.result() if status in ENDED else s.close(sup)
    moved = None if c_after is None else round(c_before - c_after, 2)
    return s.summary(
        f"h2-{variant}", result, reached=reached, status_after=status, c_before=c_before, c_after=c_after, gained=moved
    )


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


def timeouts(client, sid, suppliers):
    return {s: len(client.thread(sid, s).get("timeouts") or []) for s in suppliers}


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
        "supplier": result.get("supplier_id"),
        "timeouts": timeouts(client, table.session_id, state["threads"]),
        "thread_status": {s: (t["status"], t["closed"]) for s, t in state["threads"].items()},
        "rounds": state.get("rounds"),
    }


def h3_par(client, complete, package):
    """D02 with one LLM agent per thread: every round all live threads get their e-mail together."""
    s = Session(client, "case:D02")
    agents = {sup: ThreadAgent(complete, package, sup) for sup in s.threads}
    dropped, last_round, rounds = set(), False, 0
    with ThreadPoolExecutor(max_workers=len(s.threads)) as pool:
        while True:
            live = [sup for sup in live_threads(s.threads) if sup not in dropped]
            if not live or rounds >= s.case.get("round_limit", 10):
                break
            decisions = dict(zip(live, pool.map(lambda sup: agents[sup].decide(s.case, s.threads), live), strict=True))
            actions = {sup: d["message"]["action"]["type"] for sup, d in decisions.items() if d["message"].get("action")}
            dropped |= {sup for sup, kind in actions.items() if kind == "walk_away"}
            sends = {sup: d["message"] for sup, d in decisions.items() if not d["message"].get("action")}
            if not sends or last_round:
                break
            last_round = "accept" in actions.values()  # one thread is ready: the others get one more round
            rounds += 1

            def send(item):
                sup, message = item
                try:
                    return sup, message, s.client.send_message(s.sid, sup, message)
                except ArenaError as e:
                    return sup, message, e

            for sup, message, reply in pool.map(send, sends.items()):
                if isinstance(reply, ArenaError):
                    s.steps.append({"note": f"round {rounds} to {sup}", "error": str(reply)})
                    dropped.add(sup)
                    continue
                s.threads[sup] += [{**message, "from": "buyer"}, fetch_documents(s, reply)]
                s.steps.append(
                    {
                        "note": f"round {rounds} to {sup}",
                        "sent": [x["terms"] for x in message.get("term_sheets") or []],
                        "status": reply.get("status"),
                        "their_sheets": [{"id": i, "terms": t, "c": c} for i, t, c, _ in s.sheets(sup)],
                        "claim_results": reply.get("claim_results"),
                    }
                )
    if live_threads(s.threads):
        move = closing_move(s.case, s.threads)
        out = s.client.send_message(s.sid, move["supplier_id"], move["message"])
        result = out.get("result", out)
        s.steps.append({"note": "close", "action": move["message"]["action"], "supplier": move["supplier_id"]})
    else:
        result = s.result()
    state = client.session(s.sid)
    return s.summary(
        "h3-par",
        result,
        supplier=result.get("supplier_id"),
        thread_status={sup: (t["status"], t["closed"]) for sup, t in state["threads"].items()},
        rounds=rounds,
    )


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("probes", nargs="+", choices=["h1a", "h1b", "h2-trade", "h2-push", "h2-shift", "h3-seq", "h3-par"])
    ap.add_argument("--repeat", type=int, default=1, help="how often to run each probe (suppliers vary)")
    ap.add_argument("--out", help="write the summaries to this JSON file")
    args = ap.parse_args()
    load_env()
    client = ArenaClient()
    complete = package = None
    if any(p.startswith("h3") for p in args.probes):
        import os

        complete, package = llm_from_env(), DataPackage(os.environ.get("ARENA_DATA", "data/package"))
        package.lookup("")
    jobs = {
        "h1a": lambda: h1(client, stale=False),
        "h1b": lambda: h1(client, stale=True),
        "h2-trade": lambda: h2(client, "trade"),
        "h2-push": lambda: h2(client, "push"),
        "h2-shift": lambda: h2(client, "shift"),
        "h3-seq": lambda: h3_seq(client, complete, package),
        "h3-par": lambda: h3_par(client, complete, package),
    }
    todo = [p for p in args.probes for _ in range(args.repeat)]

    def run(probe):
        try:
            return jobs[probe]()
        except Exception as e:  # one failed probe must not lose the others
            return {"probe": probe, "error": f"{type(e).__name__}: {e}"}

    with ThreadPoolExecutor(max_workers=min(len(todo), 8)) as pool:
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
