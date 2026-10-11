# ruff: noqa: E501  (long sentences and messages)
"""python -m sellm2 <command>

  play P01 [--label TEXT]                     one practice (or sandbox D01/D02) case
  run --set practice|sandbox [--cases P01 P05 | all] [--repeat N] [--parallel 8] [--label TEXT]
  final [--waves 5] [--parallel 10] [--dry-run]   the Live Final (keep it running before wave 1)
  replay [--label TEXT] [--cases P01 ...] [--knobs JSON]   offline: where sellm2 differs from a recorded run
  brief SUPPLIER [--parts part:...]           what sellm2 knows about a supplier
  stress [--n 120] [--seeds 2]                the lab's stress test (no arena, no quota)

Logs go to runs/logs/<time>-sellm2-<command>.log and .jsonl (one row per case). Before every run on the
hosted arena the team's latest commits are pulled (scripts/pull-first); the final only reports.
"""

import argparse
import json
import logging
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def setup_logging(name):
    path = ROOT / "runs" / "logs" / f"{time.strftime('%Y%m%d-%H%M%S')}-sellm2-{name}.log"
    path.parent.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s %(levelname).1s %(threadName)s %(message)s", "%H:%M:%S")
    fh, sh = logging.FileHandler(path, encoding="utf-8"), logging.StreamHandler()
    fh.setFormatter(fmt)
    sh.setFormatter(fmt)
    sh.setLevel(logging.WARNING)
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers[:] = [fh, sh]
    return path


def pull_first(final=False):
    """scripts/pull-first; on new commits start this command again on the new code (as a module)."""
    url = os.environ.get("ARENA_URL", "")
    script = ROOT / "scripts" / "pull-first"
    if not script.is_file() or "127.0.0.1" in url or "localhost" in url:
        return
    code = subprocess.run(["bash", str(script), *(["--check-only"] if final else [])], check=False).returncode
    if code == 3:
        os.execve(sys.executable, [sys.executable, "-m", "sellm2", *sys.argv[1:]], {**os.environ, "ARENA_NO_PULL": "1"})
    if code == 1:
        raise SystemExit("not started: get in sync with the team first (message above)")


def package(path):
    from arena_kit.data import DataPackage

    if not path or not Path(path).is_dir():
        logging.getLogger("sellm2").warning("no data package at %s: playing without data", path)
        return None
    pkg = DataPackage(path)
    pkg.lookup("")  # build the ID index once, before the cases share it
    return pkg


def agent_maker(pkg, knobs=None):
    from .agent import make_agent

    return lambda: make_agent(pkg, **(knobs or {}))


def warm_up(pkg):
    """Build the shared indexes before the first case (a wave's first moves must not wait on it)."""
    if pkg is None:
        return
    from .knowledge import source

    src = source(pkg)
    for attr in ("by_kind", "series", "drivers", "cost_owner", "price_units", "forecast_shared", "letter_kind", "released"):
        getattr(src, attr)


def commit():
    return os.popen(f"git -C {ROOT} rev-parse --short HEAD 2>/dev/null").read().strip()


def branch():
    return os.popen(f"git -C {ROOT} rev-parse --abbrev-ref HEAD 2>/dev/null").read().strip()


def main(argv=None):
    from arena_kit.cli import load_env

    load_env(ROOT / ".env")
    ap = argparse.ArgumentParser(prog="python -m sellm2", description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    data = {"default": os.environ.get("ARENA_DATA", str(ROOT / "data" / "package"))}
    p = sub.add_parser("play")
    p.add_argument("case_id")
    p.add_argument("--label", default="")
    p.add_argument("--data", **data)
    p.add_argument("--knobs", default="{}")
    r = sub.add_parser("run")
    r.add_argument("--set", default="practice", choices=["practice", "sandbox"])
    r.add_argument("--cases", nargs="*", default=["all"])
    r.add_argument("--repeat", type=int, default=1)
    r.add_argument("--parallel", type=int, default=8)
    r.add_argument("--label", default="")
    r.add_argument("--data", **data)
    r.add_argument("--knobs", default="{}")
    f = sub.add_parser("final")
    f.add_argument("--waves", type=int, default=5)
    f.add_argument("--parallel", type=int, default=10)
    f.add_argument("--data", **data)
    f.add_argument("--dry-run", action="store_true")
    rp = sub.add_parser("replay")
    rp.add_argument("--label", default=None)
    rp.add_argument("--cases", nargs="*", default=None)
    rp.add_argument("--knobs", default="{}")
    rp.add_argument("--data", **data)
    b = sub.add_parser("brief")
    b.add_argument("supplier")
    b.add_argument("--parts", nargs="*", default=None)
    b.add_argument("--data", **data)
    st = sub.add_parser("stress")
    st.add_argument("--n", type=int, default=120)
    st.add_argument("--seeds", type=int, default=2)
    st.add_argument("--data", **data)
    a = ap.parse_args(argv)

    if a.cmd == "replay":
        from . import replay

        pkg = package(a.data)
        print(replay.report(replay.sessions(a.label, a.cases), agent_maker(pkg, json.loads(a.knobs))))
        return 0
    if a.cmd == "brief":
        from .knowledge import build

        pkg = package(a.data)
        sid = a.supplier if a.supplier.startswith("sup:") else f"sup:{a.supplier}"
        parts = a.parts or [r["part_id"] for r in pkg.query("select part_id from sourcing where supplier_id = ?", (sid,))]
        br = build(pkg, sid, parts)
        out = {k: v for k, v in br.__dict__.items() if k != "parts"}
        out["parts"] = {k: v.__dict__ for k, v in br.parts.items()}
        print(json.dumps(out, indent=1, default=str))
        return 0
    if a.cmd == "stress":
        return stress(a)

    from arena_kit.client import ArenaClient

    if a.cmd == "final":
        pull_first(final=True)
        log_path = setup_logging("final")
        pkg = package(a.data)
        warm_up(pkg)
        client = ArenaClient()
        logging.getLogger("sellm2").warning("sellm2 final: %s@%s, data %s, log %s", branch(), commit(), a.data, log_path)
        if a.dry_run:
            print(f"ready: {branch()}@{commit()}, data {'ok' if pkg else 'MISSING'}, log {log_path}")
            print("start with: nohup uv run python -m sellm2 final > runs/logs/final.out 2>&1 &")
            return 0
        from .runner import run_final

        rows = run_final(client, agent_maker(pkg), a.waves, a.parallel, on_row=row_writer(log_path))
        summarise(list(rows.values()), client)
        return 0

    pull_first(final=False)
    log_path = setup_logging(a.cmd)
    pkg = package(a.data)
    warm_up(pkg)
    client = ArenaClient()
    from .runner import case_list, label_sessions, run_cases

    knobs = json.loads(a.knobs)
    if a.cmd == "play":
        set_ = "sandbox" if a.case_id.split(":")[-1].startswith("D") else "practice"
        ids, parallel, repeat = case_list(client, set_, [a.case_id]), 1, 1
    else:
        ids, parallel, repeat = case_list(client, a.set, a.cases), a.parallel, a.repeat
    logging.getLogger("sellm2").warning("sellm2 %s: %s@%s, cases %s, knobs %s, log %s", a.cmd, branch(), commit(), ids, knobs, log_path)
    rows = run_cases(client, ids, agent_maker(pkg, knobs), parallel, repeat, on_row=row_writer(log_path))
    if a.label:
        label_sessions(rows, a.label)
    summarise(rows, client)
    return 0


def row_writer(log_path):
    lock = threading.Lock()

    def write(row):
        with lock, open(log_path.with_suffix(".jsonl"), "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, default=str) + "\n")

    return write


def summarise(rows, client):
    scores = [r["score"] or 0.0 for r in rows]
    for r in sorted(rows, key=lambda r: r["case_id"]):
        print(f"{r['case_id']:10} {r['score'] if r['score'] is None else round(r['score'], 3)!s:6} {r['end_reason']}  {r['session_id']}  {r['stats']}{'  CRASH ' + r['crash'] if r['crash'] else ''}")
    if scores:
        print(f"mean {100 * sum(scores) / len(scores):.1f} over {len(scores)} cases")
    if getattr(client, "practice_remaining", None) is not None:
        print(f"practice sessions left: {client.practice_remaining}")


def stress(a):
    """The lab's stress test with sellm2 (sellm.lab is the team's simulator; nothing of it changes)."""
    cmd = [sys.executable, "-m", "sellm.lab", "stress", "--agent", "sellm2.agent:make_agent", "--n", str(a.n),
           "--seeds", str(a.seeds), "--label", "sellm2"]  # fmt: skip
    return subprocess.run(cmd, cwd=ROOT, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
