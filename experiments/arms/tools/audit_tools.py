# ruff: noqa  (analysis script of the Sat 21:15 review session: read-only against the arena, run from the repo root with the env of .env; see experiments/PRACTICE-ARMS.md)
"""Read-only audit: which tools does the negotiator really read for each practice case's opening?"""
import glob, json, os, sys, logging
os.environ.setdefault("ARENA_DATA", "data/package")
from arena_kit.data import DataPackage
from sellm.agent import make_agent
from sellm.negotiator import Thread
from sellm import calculator

pkg = DataPackage(os.environ["ARENA_DATA"]); pkg.lookup("")
latest = {}
for f in sorted(glob.glob("runs/practice/*/*.json")):
    r = json.load(open(f)); latest[r["case"]["case_id"]] = r   # newest per case
for cid, r in sorted(latest.items()):
    case = r["case"]
    threads = {s: t["messages"][:1] for s, t in r["threads"].items()}
    ag = make_agent(pkg)
    print("="*100)
    print(cid, case["type"], case["buyer"].get("category_goal"), "parts", case["parts"], "negotiable", case["negotiable"])
    for sid, ev in threads.items():
        v = Thread(case, sid, ev)
        d = ag.intel(case, v)
        eco = (d.get("economics") or {})
        con = d.get("contract") or {}
        sig = [(s["kind"], s["strength"]) for s in d.get("signals", [])]
        parts = d.get("parts") or {}
        p0 = next(iter(parts.values()), {}) if parts else {}
        print(f"  {sid}: dossier coverage={d.get('coverage')} cash={eco.get('cash_pressure')} cost_of_money={eco.get('cost_of_money')} archetype={eco.get('archetype')}")
        print(f"     signals={sig}")
        print(f"     contract: payment_days={con.get('payment_days')} valid_to={con.get('valid_to')} notice={con.get('notice_days')}; floor_estimate={ (p0.get('floor_estimate') or {}).get('value') } should_cost={ (p0.get('should_cost') or {}).get('unit_cost') }; citable={len(d.get('citable') or [])}")
        print(f"     negotiator.should_cost()={ag.should_cost(case, sid)}  rate()={ag.rate(case, v)}  cash()={ag.cash(case, v)}")
        try:
            aim = ag.aim(case, v, ag.opening_structure(case, v))
            print(f"     aim target={aim['target']:.3f} source={aim['source']} full={aim['full_cost']:.2f}")
        except Exception as e:
            print("     aim failed", repr(e))
        try:
            dec = ag.decide(case, threads, focus=sid)
            m = dec["message"]
            sheets = [s["terms"] for s in m.get("term_sheets", [])]
            opening = ev[0]["term_sheets"][0]["terms"]
            print(f"     OPENING {opening}")
            for s in sheets:
                keys = ("unit_price","payment_days","contract_months","volume_per_year","lead_time_days","effective_date","index_clause")
                print("     FIRST ASK", {k: s.get(k) for k in keys if k in s})
        except Exception as e:
            print("     decide failed", repr(e))
