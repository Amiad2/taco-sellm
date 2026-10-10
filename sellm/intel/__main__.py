"""uv run python -m sellm.intel build | check | show <id> | signals-report | verify"""

import argparse
import filecmp
import json
import os
import sys
import tempfile
import time
from pathlib import Path

from arena_kit.cli import load_env
from arena_kit.data import DataPackage

from . import build, signals


def main(argv=None):
    load_env()
    ap = argparse.ArgumentParser(prog="python -m sellm.intel", description=__doc__)
    ap.add_argument("--data", default=os.environ.get("ARENA_DATA", "data/package"), help="data package folder")
    ap.add_argument("--out", default=str(build.DOSSIERS), help="dossier folder")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("build", help="build all dossiers into --out")
    sub.add_parser("check", help="rebuild in a temp folder and compare byte by byte with --out")
    show = sub.add_parser("show", help="print a supplier's profile, signals and economics")
    show.add_argument("supplier_id")
    rep = sub.add_parser("signals-report", help="markdown list of every signal, for a human check")
    rep.add_argument("--to", help="write to this file instead of stdout")
    sub.add_parser("verify", help="run the automated checks V1-V10 (docs/PLAN.md section 10)")
    args = ap.parse_args(argv)

    if args.cmd == "verify":
        from .verify import run

        return run(args.data, args.out)
    if args.cmd == "show":
        sid = args.supplier_id if args.supplier_id.startswith("sup:") else f"sup:{args.supplier_id}"
        path = Path(args.out) / f"{sid.split(':', 1)[1]}.json"
        d = (
            json.loads(path.read_text(encoding="utf-8"))
            if path.is_file()
            else build.build_one(build.Source(DataPackage(args.data)), sid)
        )
        print(d["profile_text"], "\n")
        for s in d["signals"]:
            print(f'- {s["kind"]} {s["strength"]}: {", ".join(s["evidence"])}\n    "{s["excerpt"]}"')
        print("\n" + json.dumps(d["economics"], indent=1, ensure_ascii=False))
        return 0
    t0 = time.perf_counter()
    dossiers = build.build_all(DataPackage(args.data))
    if args.cmd == "signals-report":
        text = signals.report(dossiers.values())
        if args.to:
            Path(args.to).write_text(text, encoding="utf-8")
        else:
            print(text)
        return 0
    if args.cmd == "build":
        files = build.write_all(dossiers, args.out)
        print(f"built {len(dossiers)} dossiers + index.json into {args.out} in {time.perf_counter() - t0:.2f} s")
        return 0 if len(files) == len(dossiers) + 1 else 1
    with tempfile.TemporaryDirectory() as tmp:
        build.write_all(dossiers, tmp)
        fresh = sorted(p.name for p in Path(tmp).glob("*.json"))
        have = sorted(p.name for p in Path(args.out).glob("*.json"))
        _, mismatch, errors = filecmp.cmpfiles(tmp, args.out, fresh, shallow=False)
        missing, extra = sorted(set(fresh) - set(have)), sorted(set(have) - set(fresh))
        if mismatch or errors or missing or extra:
            print(f"differs: changed {mismatch}, missing {missing + errors}, extra {extra}")
            return 1
    print(f"identical: {len(fresh)} files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
