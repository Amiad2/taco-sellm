"""How close are the twins to the real suppliers? Replay every buyer e-mail of our real sessions
(`runs/`) into the twin of its case and compare the twin's reply with the real one.

Per reply: the value of the supplier's offer to the supplier itself (so a different structure does
not count as an error), as a share of its opening value; the status (open, final_offer, agreed,
walked_away); and the claim results the twin's checker gives against the arena's. `fit` tunes the
dynamics (first step, mirror, concession limit and its decay, patience) per twin on these replays,
starting from the parameters that fit all sessions together.
"""

import copy
import itertools
import json
import random
import statistics

from .bot import SupplierThread
from .table import Session
from .twins import ROOT

GRID = {
    "first_step": [0.03, 0.1, 0.2, 0.35, 0.5, 0.65, 0.8],
    "mirror": [0.3, 0.5, 0.7, 0.85],
    "cap": [0.004, 0.007, 0.01, 0.015, 0.025],
    "cap_decay": [0.6, 0.8, 1.0],
    "patience": [3, 4, 5, 6, 7],
}
STATUS_WEIGHT = 1.0  # a wrong status counts like 1 % of the opening value off


def real_sessions(name):
    out = []
    for f in sorted(ROOT.glob(f"runs/*/{name}/*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        if (d.get("state") or {}).get("result"):
            out.append(d)
    return out


def replay(scenario, session, facts, params=None):
    """Rows, one per real supplier reply to a buyer e-mail."""
    case, rows = scenario.case, []
    shared = Session(scenario, facts)
    for sid, thread in session["threads"].items():
        persona = copy.copy(scenario.personas[sid])
        for k, v in (params or {}).items():
            setattr(persona, k, v)
        persona.alternatives = False  # the ask is what is compared; skip the slow variant search
        bot = SupplierThread(persona, case, random.Random(0), shared)
        bot.opening()
        msgs = thread["messages"]
        for i, m in enumerate(msgs):
            if m.get("from") != "buyer" or m.get("action"):
                continue
            real = next((x for x in msgs[i + 1 :] if x.get("from") != "buyer"), None)
            if real is None or bot.closed:
                break
            mine = bot.respond(
                {"body": m.get("body", ""), "refs": m.get("refs") or [], "term_sheets": m.get("term_sheets") or []}
            )
            a0 = bot.a0
            real_sheets = real.get("term_sheets") or []
            row = {
                "case": scenario.name,
                "session": session["session_id"],
                "label": session.get("label", ""),
                "supplier": sid,
                "round": bot.round,
                "real_status": real.get("status"),
                "twin_status": mine["status"],
                "real_claims": [c["result"] for c in real.get("claim_results") or []],
                "twin_claims": [c["result"] for c in mine.get("claim_results") or []],
            }
            if real_sheets and mine.get("term_sheets"):
                rv = persona.value(case, real_sheets[0]["terms"])
                tv = persona.value(case, mine["term_sheets"][0]["terms"])
                row.update(
                    real_price=real_sheets[0]["terms"].get("unit_price"),
                    twin_price=mine["term_sheets"][0]["terms"].get("unit_price"),
                    err_pct=100 * (tv - rv) / a0,
                )
            rows.append(row)
    return rows


def loss(rows):
    errs = [abs(r["err_pct"]) for r in rows if "err_pct" in r]
    status = [r["real_status"] != r["twin_status"] for r in rows]
    if not rows:
        return 0.0
    return (statistics.mean(errs) if errs else 0.0) + STATUS_WEIGHT * statistics.mean(status)


def evaluate(scenarios, facts, params_for=lambda s: None):
    rows = []
    for s in scenarios:
        for session in real_sessions(s.name):
            rows += replay(s, session, facts, params_for(s))
    return rows


def fit(scenarios, facts, log=print):
    """Global grid search, then per twin a search one grid step around the global best."""
    keys = list(GRID)
    sessions = {s.name: real_sessions(s.name) for s in scenarios}

    def total(params, subset):
        rows = []
        for s in subset:
            for session in sessions[s.name]:
                rows += replay(s, session, facts, params)
        return loss(rows), rows

    best = None
    for combo in itertools.product(*(GRID[k] for k in keys)):
        params = dict(zip(keys, combo, strict=True))
        value, _ = total(params, scenarios)
        if best is None or value < best[0]:
            best = (value, params)
    log(f"global best {best[1]} loss {best[0]:.3f}")
    per = {}
    for s in scenarios:
        if not sessions[s.name]:
            per[s.name] = dict(best[1])
            continue
        near = {}
        for k in keys:
            i = GRID[k].index(best[1][k])
            near[k] = GRID[k][max(0, i - 1) : i + 2]
        local = None
        for combo in itertools.product(*(near[k] for k in keys)):
            params = dict(zip(keys, combo, strict=True))
            value, _ = total(params, [s])
            if local is None or value < local[0] - 1e-9:
                local = (value, params)
        per[s.name] = local[1]
        log(f"{s.name}: {local[1]} loss {local[0]:.3f} ({len(sessions[s.name])} sessions)")
    return best[1], per


def report(rows):
    """Markdown: error per case, status agreement, claim agreement."""
    out = [
        "| Case | Replies | Mean abs error (% of opening value) | Status agrees | Claims agree |",
        "|---|---|---|---|---|",
    ]
    by = {}
    for r in rows:
        by.setdefault(r["case"], []).append(r)
    for case, rs in sorted(by.items()):
        errs = [abs(r["err_pct"]) for r in rs if "err_pct" in r]
        st = sum(r["real_status"] == r["twin_status"] for r in rs)
        pairs = [(a, b) for r in rs for a, b in zip(r["real_claims"], r["twin_claims"], strict=False)]
        cl = f"{sum(a == b for a, b in pairs)}/{len(pairs)}" if pairs else "-"
        out.append(f"| {case} | {len(rs)} | {statistics.mean(errs) if errs else 0:.2f} | {st}/{len(rs)} | {cl} |")
    errs = [abs(r["err_pct"]) for r in rows if "err_pct" in r]
    st = sum(r["real_status"] == r["twin_status"] for r in rows)
    out.append(f"| **all** | {len(rows)} | **{statistics.mean(errs):.2f}** | {st}/{len(rows)} | |")
    return "\n".join(out)
