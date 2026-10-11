# ruff: noqa: E501  (long lines in a research script)
"""Structure and argument experiments on omars_branch (Sun 11 Oct, ledger: experiments/LEDGER.md).

    uv run python -m experiments.structure_args replay E1 E2           # offline: which recorded cases change
    uv run python -m experiments.structure_args arena E1 --cases P08   # one practice session per case (quota)

The agent is `sellm.agent.make_agent` (what `--agent sellm` plays) plus the variant's knobs. `replay`
walks every state of the sessions that today's agent played (practice suppliers answer identical
messages identically, so a variant that sends the same e-mails in a case scores the same there) and
prints the first move that differs. `arena` plays a case once, writes a row to
experiments/results/2026-10-11-structure-args.json, labels the session in runs/labels.json and adds a
line to experiments/LEDGER.md; run scripts/pull-runs afterwards (on main).
"""

import argparse
import fcntl
import glob
import importlib.util
import json
import os
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "experiments" / "results" / "2026-10-11-structure-args.json"
LABELS = ROOT / "runs" / "labels.json"
LEDGER = ROOT / "experiments" / "LEDGER.md"
# the sessions of today's agent (behaviour of @7a49c38 = omars_branch@a5b363c), one per practice case
REFERENCE = "@7a49c38"

VARIANTS = {
    "E1": {"contract": "horizon"},  # where C does not care, commit for the horizon, not longer
    "E2": {"idx_recent": 2.0},  # a cost-driver index that fell >= 2 % from its peak of the last 12 months
    "E12": {"contract": "horizon", "idx_recent": 2.0},
    # E2 with the hedge guard (commit after c8c0eb5): no material index fall to a supplier whose
    # dossier says its material is covered at fixed prices. Same knobs, new code
    "E2g": {"idx_recent": 2.0},
    # E2g + no on-time-delivery record to a supplier whose dossier has no delivery or quality problem
    "E3": {"idx_recent": 2.0, "gate": True},
    # the candidate (KNOBS since f473d97 already has idx_recent) + the larger of the yearly and the peak fall
    "E4": {"idx_window": "max"},
    # the candidate + a fact of a used topic, else one question, in a round that has no new fact
    "E5": {"refill": True},
}


def make(package, **knobs):
    from sellm.agent import make_agent

    return make_agent(package, **knobs)


def e4(package):
    """For `python -m sellm.runner --agent experiments.structure_args:e4` (RFQ cases through the final runner)."""
    return make(package, **VARIANTS["E4"])


def reference_sessions():
    out = {}
    for path in sorted(glob.glob(str(ROOT / "runs" / "practice" / "*" / "*.json"))):
        record = json.loads(Path(path).read_text(encoding="utf-8"))
        if REFERENCE in (record.get("label") or ""):
            out[record["case_id"]] = record  # the latest one per case
    return out


def states(record):
    """(supplier, threads) before each of our e-mails, the other threads as they stood then."""
    threads = {s: t["messages"] for s, t in record["threads"].items()}
    for sid, events in threads.items():
        for i, message in enumerate(events):
            if message.get("from") != "buyer" and not message.get("action"):
                others = {s: e[:1] for s, e in threads.items() if s != sid}
                yield sid, {**others, sid: events[: i + 1]}


def summary(decision):
    msg = decision["message"]
    if msg.get("action"):
        return f"{msg['action']['type']}"
    sheets = [s["terms"] for s in msg.get("term_sheets") or []]
    return (
        " | ".join(
            ", ".join(f"{k}={v if not isinstance(v, dict) else v.get('deadband_pct')}" for k, v in sorted(t.items()))
            for t in sheets
        )
        + f" || {msg.get('body', '')[:0]}"
    )


def replay(variants):
    from arena_kit.data import DataPackage

    package = DataPackage(os.environ.get("ARENA_DATA", "data/package"))
    refs = reference_sessions()
    for name in variants:
        knobs = VARIANTS[name]
        print(f"== {name} {knobs}")
        for cid, record in sorted(refs.items()):
            case = record["case"]
            base, var = make(package), make(package, **knobs)
            diff = None
            for sid, threads in states(record):
                a = base.decide(case, threads, sid if len(threads) > 1 else None)
                b = var.decide(case, threads, sid if len(threads) > 1 else None)
                if a["message"] != b["message"]:
                    diff = (sid, len([m for m in threads[sid] if m.get("from") == "buyer"]), a, b)
                    break
            if diff is None:
                print(f"  {cid}: same moves as the recorded session (score {record['state']['result']['score']:.3f})")
                continue
            sid, n, a, b = diff
            print(f"  {cid}: differs at our message {n + 1} to {sid}")
            print(f"     base: {summary(a)}")
            print(f"     var:  {summary(b)}")
            ba, bb = a["message"].get("body") or "", b["message"].get("body") or ""
            if ba != bb:
                print(f"     base body: {ba[:400]!r}")
                print(f"     var  body: {bb[:400]!r}")


def arena(name, cases):
    from arena_kit.cli import load_env, pull_first

    load_env()
    pull_first()  # never play on outdated code
    import subprocess

    from arena_kit.client import ArenaClient
    from arena_kit.data import DataPackage

    commit = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=ROOT
    ).stdout.strip()
    branch = subprocess.run(
        ["git", "branch", "--show-current"], capture_output=True, text=True, cwd=ROOT
    ).stdout.strip()
    dirty = subprocess.run(
        ["git", "status", "--porcelain", "sellm", "arena_kit"], capture_output=True, text=True, cwd=ROOT
    ).stdout.strip()
    spec = importlib.util.spec_from_file_location("ab_sandbox", ROOT / "experiments" / "ab_sandbox.py")
    ab = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ab)
    package = DataPackage(os.environ.get("ARENA_DATA", "data/package"))
    package.lookup("")
    client = ArenaClient()
    knobs = VARIANTS[name]
    rows = json.loads(OUT.read_text(encoding="utf-8")) if OUT.is_file() else []
    for case in cases:
        case_id = f"case:{case.split(':')[-1]}"
        row = ab.play_case(client, case_id, make(package, **knobs))
        version = f"{branch}@{commit}" + ("+dirty" if dirty else "")
        row.update(label=name, knobs=knobs, version=version)
        lock = open(ROOT / ".git" / "structure-args.lock", "w")  # runs of this script in parallel write the same files
        fcntl.flock(lock, fcntl.LOCK_EX)
        rows = json.loads(OUT.read_text(encoding="utf-8")) if OUT.is_file() else []
        rows.append(row)
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(rows, indent=1, default=str), encoding="utf-8")
        labels = json.loads(LABELS.read_text(encoding="utf-8")) if LABELS.is_file() else {}
        labels[row["session_id"]] = f"OMAR {name} {json.dumps(knobs, sort_keys=True)} sellm.agent {version}"
        LABELS.write_text(json.dumps(labels, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        score = row.get("score")
        free = case_id in ("case:D01", "case:D02")
        with LEDGER.open("a", encoding="utf-8") as f:
            f.write(
                f"| {datetime.now().strftime('%a %H:%M')} | {name} | {case_id.split(':')[-1]} | {'0 (sandbox)' if free else 1} "
                f"| {score if score is None else round(score, 3)} | {row.get('end_reason')} | {version} | {row['session_id']} |\n"
            )
        threads = []
        for sid, t in (row.get("threads") or {}).items():
            ours = [p[0] if p else None for p in t["our_prices"]]
            threads.append(f"{sid.split(':')[-1]} theirs {t['their_prices']} ours {ours} {t['status']}")
        fcntl.flock(lock, fcntl.LOCK_UN)
        lock.close()
        head = f"{case} {name} score {score if score is None else round(score, 3)} {row.get('end_reason')}"
        print(f"{head} | {'; '.join(threads)} | {row['session_id']} {row.get('notes') or ''}", flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("replay")
    r.add_argument("variants", nargs="+", choices=sorted(VARIANTS))
    a = sub.add_parser("arena")
    a.add_argument("variant", choices=sorted(VARIANTS))
    a.add_argument("--cases", nargs="+", required=True)
    args = ap.parse_args()
    if args.cmd == "replay":
        replay(args.variants)
    else:
        arena(args.variant, args.cases)


if __name__ == "__main__":
    main()
