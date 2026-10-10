# ruff: noqa  (analysis script of the Sat 21:15 review session: read-only against the arena, run from the repo root with the env of .env; see experiments/PRACTICE-ARMS.md)
import glob, json, os, sys
sys.path.insert(0, ".")
from arena_kit.data import DataPackage
from sellm import variants
os.environ["SELLM_TRACE"] = "/tmp/_dry_trace.jsonl"
pkg = DataPackage(os.environ["ARENA_DATA"]); pkg.lookup("")
latest = {}
for f in sorted(glob.glob("/Users/jonathandemir/projects/tacto-challenge/taco-sellm/runs/practice/*/*.json")):
    r = json.load(open(f)); latest[r["case"]["case_id"]] = r
names = sys.argv[1:] or ["a1", "bank", "signals"]
def fa(sheets):
    return [{k: s.get(k) for k in ("unit_price","payment_days","contract_months","effective_date") if k in s} for s in sheets]
for cid, r in sorted(latest.items()):
    case = r["case"]
    threads = {s: t["messages"][:1] for s, t in r["threads"].items()}
    print("=== ", cid)
    outs = {}
    for n in names:
        ag = getattr(variants, n)(pkg)
        res = {}
        for sid in threads:
            d = ag.decide(case, threads, focus=sid)
            m = d["message"]
            res[sid] = (fa([t["terms"] for t in m.get("term_sheets", [])]), (m.get("body") or "")[:400])
        outs[n] = res
    for sid in threads:
        base = outs[names[0]][sid]
        for n in names:
            sheets, body = outs[n][sid]
            tag = "" if n == names[0] else ("  [same as %s]" % names[0] if (sheets, body) == base else "  [DIFFERENT]")
            print(f"  {sid} {n:8} {sheets}{tag}")
            if n != names[0] and body != base[1]:
                extra = [x for x in body.replace("\n"," ").split(". ") if x not in base[1].replace("\n"," ")]
                print("        body differs:", " | ".join(extra)[:260])
