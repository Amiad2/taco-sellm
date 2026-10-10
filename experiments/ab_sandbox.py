# ruff: noqa: E501
"""Play agent variants several times against the real supplier bots and compare them.

The lab cannot judge wording, and identical runs on the arena differ, so a variant is judged by
its mean over several sessions. Default: the sandbox (`case:D01`, `case:D02`), which is free. A
practice case costs quota: this script refuses one unless `--practice` is given.

    uv run python experiments/ab_sandbox.py --case D01 --arms calc nego-template nego-llm --repeat 4
    uv run python experiments/ab_sandbox.py --case D02 --arms calc --repeat 3

Arms: calc (the plain Calculator with sellm/agent.py CALC_KNOBS), nego-template / nego-llm (the
negotiator with text from code / from the LLM), sellm (whatever `make_agent` returns for the arena).

Every case is played with one loop per thread (each thread answers as soon as its own reply is in),
the thread is re-read before every accept and after a silence, because a timeout replaces the offer
ID. Sessions are labelled in runs/labels.json; `scripts/pull-runs` then saves them in full.
"""

import argparse
import inspect
import json
import math
import os
import statistics
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from arena_kit.cli import load_env, pull_first  # noqa: E402
from arena_kit.client import ArenaClient, ArenaError  # noqa: E402
from arena_kit.data import DataPackage  # noqa: E402
from arena_kit.play import ENDED, closing_move, fetch_documents, latest, live_threads  # noqa: E402

LABELS = ROOT / "runs" / "labels.json"
SILENCE_S = 50  # re-read a thread we have not heard from for this long: it may have timed out
MAX_CASE_S = 540  # give up negotiating after this and close on what stands


def build(arm, package):
    """A fresh agent for one case."""
    if arm == "sellm":
        from sellm.agent import make_agent

        return (
            make_agent(package, writer="llm")
            if "writer" in inspect.signature(make_agent).parameters
            else make_agent(package)
        )
    from sellm.agent import CALC_KNOBS, KNOBS

    if arm == "calc":
        from sellm.lab.strategies import Calculator

        return Calculator(package, **CALC_KNOBS)
    from sellm.negotiator import Negotiator

    extra = {}
    name, _, options = arm.partition("+")  # e.g. nego-template+open_below=0.08+rounds_to_floor=4
    for option in filter(None, options.split("+")):
        key, _, value = option.partition("=")
        try:
            extra[key] = json.loads(value) if value else True
        except ValueError:
            extra[key] = value  # a plain word, e.g. levers=theirs
    return Negotiator(package, writer={"nego-template": "template", "nego-llm": "llm"}[name], **{**KNOBS, **extra})


class Table:
    """What `fetch_documents` needs: the session's attachments."""

    def __init__(self, client, sid):
        self.client, self.sid = client, sid

    def attachment(self, attachment_id):
        return self.client.attachment(self.sid, attachment_id)


def play_case(client, case_id, agent, max_s=MAX_CASE_S):
    """One session, one loop per thread. Returns a row for the report."""
    opened = client.open_session(case_id)
    sid, case, threads = opened["session_id"], opened["case"], opened["threads"]
    table = Table(client, sid)
    for events in threads.values():
        for message in events:
            fetch_documents(table, message)
    lock, done = threading.Lock(), threading.Event()
    heard = dict.fromkeys(threads, time.monotonic())  # when each thread's last e-mail came in
    flying, notes, outcome = set(), [], {}
    takes_focus = "focus" in inspect.signature(agent.decide).parameters
    t_start = time.monotonic()

    def refresh(sup):
        """Add what the arena did to this thread without us: timeout follow-ups carry a new offer ID."""
        t = client.thread(sid, sup)
        seen = sum(1 for m in threads[sup] if m.get("_timeout"))
        for k, late in enumerate((t.get("timeouts") or [])[seen:], start=seen):
            sheets = (
                [{"term_sheet_id": late["offer_id"], "terms": late.get("terms") or {}}] if late.get("offer_id") else []
            )
            threads[sup].append(
                {"from": f"timeout@{sup}", "_timeout": True, "message_id": f"timeout:{sup}:{k}", "status": late.get("status") or "open",
                 "term_sheets": sheets, "body": late.get("text") or "", "missing_fields": late.get("missing_fields") or [], "attachments": []}
            )  # fmt: skip
            notes.append(f"{sup}: timeout, now {late.get('status')} {late.get('offer_id')}")
            heard[sup] = time.monotonic()
        if t.get("closed") and latest(threads[sup]).get("status") not in ENDED:
            threads[sup].append(
                {
                    "from": f"closed@{sup}",
                    "_timeout": True,
                    "message_id": f"closed:{sup}",
                    "status": "walked_away",
                    "term_sheets": [],
                    "body": "",
                    "attachments": [],
                }
            )
            notes.append(f"{sup}: thread closed ({t.get('closed')})")
        return t

    def close(decision):
        """An accept or a walk-away, with the thread re-read first. True when the case has ended."""
        target, action = decision["supplier_id"], decision["message"]["action"]
        if action["type"] == "accept":
            current = refresh(target).get("offer_id")
            if current != action.get("term_sheet_id"):
                notes.append(f"{target}: offer ID changed before the accept, deciding again")
                return False
        try:
            reply = client.send_message(sid, target, decision["message"])
        except ArenaError as e:
            notes.append(f"{target}: {action['type']} refused: {e}")
            if e.status in (409, 422):
                for s in threads:
                    refresh(s)
                return False
            raise
        outcome["result"] = reply.get("result", reply)
        done.set()
        return True

    def loop(sup):
        idle = 0
        while not done.is_set() and time.monotonic() - t_start < max_s:
            if latest(threads[sup]).get("status") in ENDED:
                return
            if time.monotonic() - heard[sup] > SILENCE_S:
                with lock:
                    refresh(sup)
                if latest(threads[sup]).get("status") in ENDED:
                    return
            with lock:
                if done.is_set():
                    return
                decision = agent.decide(case, threads, focus=sup) if takes_focus else agent.decide(case, threads)
                target, message = decision["supplier_id"], decision["message"]
                if message.get("action"):
                    # an accept is taken at once (a supplier left waiting at its final offer withdraws);
                    # a walk-away waits until no other thread's reply is still on its way
                    if message["action"]["type"] != "accept" and flying - {sup}:
                        decision = None
                    elif close(decision):
                        return
                    else:
                        decision = None
                elif target != sup:
                    decision = None  # nothing to send in this thread now
                else:
                    flying.add(sup)
            if decision is None:
                idle += 1
                time.sleep(2.0)
                continue
            idle = 0
            try:
                reply = client.send_message(sid, sup, message)
            except ArenaError as e:
                notes.append(f"{sup}: send refused: {e}")
                with lock:
                    flying.discard(sup)
                    if e.status in (409, 422):
                        state = client.session(sid)
                        if state.get("status") == "ended":
                            outcome["result"] = state.get("result") or {
                                "deal": False,
                                "end_reason": state.get("end_reason"),
                            }
                            done.set()
                            return
                        refresh(sup)
                        continue
                raise
            with lock:
                flying.discard(sup)
                heard[sup] = time.monotonic()
                if "result" in reply:
                    outcome["result"] = reply["result"]
                    done.set()
                    return
                threads[sup] += [{**message, "from": "buyer"}, fetch_documents(table, reply)]

    crash = None
    with ThreadPoolExecutor(max_workers=len(threads)) as pool:
        futures = [pool.submit(loop, sup) for sup in threads]
        for f in futures:
            try:
                f.result()
            except Exception as e:  # keep the row: a crash is a result
                crash = f"{type(e).__name__}: {e}"
                done.set()
    if "result" not in outcome:  # time is up or every loop ended: take what stands
        state = client.session(sid)
        if state.get("status") == "ended":
            outcome["result"] = state.get("result") or {"deal": False, "end_reason": state.get("end_reason")}
        else:
            for sup in threads:
                refresh(sup)
            if live_threads(threads):
                decision = closing_move(case, threads)
            else:
                decision = {"supplier_id": next(iter(threads)), "message": {"action": {"type": "walk_away"}}}
            notes.append(f"closing: {decision['message']['action']}")
            try:
                reply = client.send_message(sid, decision["supplier_id"], decision["message"])
                outcome["result"] = reply.get("result", reply)
            except ArenaError as e:
                notes.append(f"closing refused: {e}")
                outcome["result"] = (client.session(sid).get("result")) or {"deal": False}
    result = outcome["result"]
    state = client.session(sid)
    per_thread = {}
    for sup in threads:
        t = client.thread(sid, sup)
        mine = [m for m in threads[sup] if m.get("from") == "buyer"]
        theirs = [m for m in threads[sup] if m.get("from") != "buyer" and not m.get("_timeout")]
        first_final = next((i for i, m in enumerate(theirs) if m.get("status") == "final_offer"), None)
        per_thread[sup] = {
            "our_messages": len(mine),
            "timeouts": len(t.get("timeouts") or []),
            "status": t.get("status"),
            "closed": t.get("closed"),
            "final_offer_after_our_message": first_final,
            "their_prices": [(m.get("term_sheets") or [{}])[0].get("terms", {}).get("unit_price") for m in theirs],
            "our_prices": [[s["terms"].get("unit_price") for s in m.get("term_sheets") or []] for m in mine],
            "claims": [c.get("result") for m in theirs for c in m.get("claim_results") or []],
        }
    stats = getattr(agent, "stats", None) or {}
    return {
        "session_id": sid,
        "case_id": case_id,
        "deal": result.get("deal"),
        "score": result.get("score") or 0.0,
        "c_deal": result.get("c_deal"),
        "supplier": result.get("supplier_id"),
        "terms": result.get("terms"),
        "end_reason": state.get("end_reason"),
        "seconds": round(time.monotonic() - t_start),
        "threads": per_thread,
        "notes": notes,
        "crash": crash,
        "agent_stats": stats,
    }


def commit():
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=False
        )
        dirty = subprocess.run(
            ["git", "status", "--porcelain", "--", "sellm", "arena_kit"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        return out.stdout.strip() + ("+local" if dirty.stdout.strip() else "")
    except OSError:
        return "?"


def table_of(rows):
    lines = [
        "| Arm | Case | n | Mean score | SE | Scores | Final price | Our messages | final_offer after | Timeouts | 422/409 | LLM fallbacks | s |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    by = {}
    for r in rows:
        by.setdefault((r["arm"], r["case_id"]), []).append(r)
    for (arm, case_id), rs in sorted(by.items()):
        ok = [r for r in rs if "error" not in r]
        if not ok:
            lines.append(
                f"| {arm} | {case_id.split(':')[1]} | 0 | - | - | errors: {[r['error'][:60] for r in rs]} | | | | | | | |"
            )
            continue
        sc = [r["score"] for r in ok]
        se = statistics.stdev(sc) / math.sqrt(len(sc)) if len(sc) > 1 else float("nan")
        prices = [(r.get("terms") or {}).get("unit_price") for r in ok]
        msgs = [max(t["our_messages"] for t in r["threads"].values()) for r in ok]
        finals = [
            min(
                (
                    t["final_offer_after_our_message"]
                    for t in r["threads"].values()
                    if t["final_offer_after_our_message"] is not None
                ),
                default=None,
            )
            for r in ok
        ]
        touts = sum(t["timeouts"] for r in ok for t in r["threads"].values())
        refused = sum(1 for r in ok for n in r["notes"] if "refused" in n)
        falls = sum((r.get("agent_stats") or {}).get("fallbacks", 0) for r in ok)
        lines.append(
            f"| {arm} | {case_id.split(':')[1]} | {len(ok)} | {statistics.mean(sc):.3f} | {se:.3f} | {', '.join(f'{x:.3f}' for x in sc)} "
            f"| {prices} | {msgs} | {finals} | {touts} | {refused} | {falls} | {round(statistics.mean(r['seconds'] for r in ok))} |"
        )
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--case", required=True, help="D01, D02, or with --practice a practice case such as P07")
    ap.add_argument("--arms", nargs="+", default=["calc"])
    ap.add_argument("--repeat", type=int, default=3)
    ap.add_argument(
        "--workers", type=int, default=5, help="sessions at once (the key allows 10 open sessions for the whole team)"
    )
    ap.add_argument("--practice", action="store_true", help="allow a practice case: each session costs quota")
    ap.add_argument("--out", help="write the rows to this JSON file")
    args = ap.parse_args()
    load_env()
    pull_first()
    case_id = f"case:{args.case}"
    if not args.case.startswith("D") and not args.practice:
        raise SystemExit(f"{case_id} is a practice case and costs quota; add --practice if that is intended")
    client = ArenaClient()
    package = DataPackage(os.environ.get("ARENA_DATA", "data/package"))
    package.lookup("")
    jobs = [arm for arm in args.arms for _ in range(args.repeat)]
    version = commit()

    def one(arm):
        try:
            row = play_case(client, case_id, build(arm, package))
        except Exception as e:  # one failed session must not lose the others
            row = {"case_id": case_id, "error": f"{type(e).__name__}: {e}"}
        return {**row, "arm": arm, "commit": version}

    with ThreadPoolExecutor(max_workers=min(len(jobs), args.workers)) as pool:
        rows = list(pool.map(one, jobs))
    labels = json.loads(LABELS.read_text(encoding="utf-8")) if LABELS.is_file() else {}
    for r in rows:
        if r.get("session_id"):
            labels[r["session_id"]] = f"ab {r['arm']} @{version}"
    LABELS.write_text(json.dumps(labels, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(rows, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(table_of(rows))
    for r in rows:
        if r.get("crash") or r.get("error") or r.get("notes"):
            print(
                f"\n{r['arm']} {r.get('session_id', '')}: {r.get('error') or r.get('crash') or ''} "
                + " | ".join((r.get("notes") or [])[:8])
            )


if __name__ == "__main__":
    main()
