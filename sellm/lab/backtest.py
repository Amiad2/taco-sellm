"""How close are the twins to the real suppliers? Replay every buyer e-mail of our real sessions
(`runs/`) into the twin of its case and compare the twin's reply with the real one.

Per reply: the value of the supplier's offer to the supplier itself (so a different structure does
not count as an error), as a share of its opening value; the status (open, final_offer, agreed,
walked_away); and the claim results the twin's checker gives against the arena's. `fit` tunes the
dynamics (first step, mirror, concession limit and its decay, patience) per twin on these replays,
starting from the parameters that fit all sessions together.
"""

import copy
import json
import random
import statistics
from pathlib import Path

from . import twins
from .bot import SupplierThread
from .table import Session
from .twins import ROOT

GRID = {
    "first_step": [0.03, 0.1, 0.2, 0.35, 0.5, 0.65, 0.8],
    "mirror": [0.3, 0.5, 0.7, 0.85],
    "cap": [0.002, 0.003, 0.004, 0.006, 0.008, 0.012, 0.02],
    "cap_decay": [0.6, 0.8, 1.0],
    "patience": [3, 4, 5, 6, 7],
    "claim_w": [0.0, 0.1, 0.2, 0.35, 0.5],
}
STATUS_WEIGHT = 1.0  # a wrong status counts like 1 % of the opening value off
PLAUSIBLE = 1.15  # a family member explains the replies within 15 % of the best fit's loss
PROBE_WEIGHT = 10.0  # D01: 0.05 off in the closed-loop probe scores weighs like 0.5 % off per reply


def real_sessions(name):
    out = []
    for f in sorted(f for d in ("practice", "sandbox") for f in ROOT.glob(f"runs/{d}/{name}/*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        if (d.get("state") or {}).get("result"):
            out.append(d)
    return out


def replay(scenario, session, facts, params=None):
    """Rows, one per real supplier reply to a buyer e-mail."""
    case, rows = scenario.case, []
    shared, bots = Session(scenario, facts), {}
    for sid in session["threads"]:  # every opening first: rivals' offers are citable from the start
        persona = copy.copy(scenario.personas[sid])
        for k, v in (params or {}).items():
            setattr(persona, k, v)
        persona.alternatives, persona.noise = False, 0.0  # compare the ask itself, deterministically
        bots[sid] = SupplierThread(persona, case, random.Random(0), shared)
        bots[sid].opening()
    for sid, thread in session["threads"].items():
        bot, persona = bots[sid], bots[sid].p
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


def fit(scenarios, facts, log=print, passes=3):
    """Coordinate descent: one parameter at a time over its grid, the others fixed. First on all
    sessions together, then per twin from that start (a twin without sessions keeps the global)."""
    sessions = {s.name: real_sessions(s.name) for s in scenarios}

    def total(params, subset):
        rows = []
        for s in subset:
            for session in sessions[s.name]:
                rows += replay(s, session, facts, params)
        value = loss(rows)
        if any(s.name == "D01" for s in subset):  # whole negotiations too: the sandbox step probes
            value += PROBE_WEIGHT * probe_loss(next(s for s in subset if s.name == "D01"), facts, params)
        return value

    def descend(start, subset):
        params, value = dict(start), total(start, subset)
        for _ in range(passes):
            changed = False
            for k, grid in GRID.items():
                for v in grid:
                    trial = {**params, k: v}
                    if (t := total(trial, subset)) < value - 1e-9:
                        params, value, changed = trial, t, True
            if not changed:
                break
        return params, value

    def plausible(params, value, subset):
        """Per parameter, the grid values that explain the replies almost as well (the family)."""
        out = {}
        for k, grid in GRID.items():
            ok = [v for v in grid if total({**params, k: v}, subset) <= value * PLAUSIBLE + 0.05]
            out[k] = ok or [params[k]]
        return out

    start = {k: grid[len(grid) // 2] for k, grid in GRID.items()}
    best, value = descend(start, scenarios)
    log(f"global {best} loss {value:.3f}")
    per, ranges = {}, {}
    for s in scenarios:
        if not sessions[s.name]:
            per[s.name], ranges[s.name] = dict(best), {k: list(v) for k, v in GRID.items()}
            continue
        per[s.name], v = descend(best, [s])
        ranges[s.name] = plausible(per[s.name], v, [s])
        log(f"{s.name}: {per[s.name]} loss {v:.3f} ({len(sessions[s.name])} sessions) family {ranges[s.name]}")
    return best, per, ranges


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


def write_report(scenarios, rows, path):
    """runs/lab/BACKTEST.md: accuracy, floors and fitted dynamics, for the team."""
    floors = "\n".join(
        f"| {s.name} | {s.case['type']} / {s.case['buyer']['category_goal']} | "
        + ", ".join(f"{k} {p.full_cost:.2f} (opening {p.opening['unit_price']:.2f})" for k, p in s.personas.items())
        + f" | {s.c_best:,.0f} |"
        for s in scenarios
    )
    keys = ("first_step", "mirror", "cap", "cap_decay", "patience", "claim_w")
    dyn = "\n".join(
        f"| {s.name} | "
        + " | ".join(str(getattr(next(iter(s.personas.values())), k)) for k in keys)
        + f" | {', '.join(sorted({k for p in s.personas.values() for k in p.claim_kinds})) or '-'} |"
        for s in scenarios
    )
    text = f"""# Lab backtest: how close the twins are to the real suppliers

Generated by `uv run python -m sellm.lab backtest --write` (after `--fit`). Every buyer e-mail of our
real sessions in `runs/` (practice and sandbox, {len(rows)} supplier replies) is replayed into the twin of its
case and the twin's reply is compared with the real one. Error: the value of the supplier's offer to
the supplier itself (so a different structure is not an error), as a share of its opening value.
Closed-loop checks (the same agent playing the twin and the arena) are in `runs/lab/VALIDATION.md`.

## Accuracy

{report(rows)}

## Floors (calibrated to C_best)

The floor is the full cost in value space: the cheapest package the twin accepts costs exactly the
case's C_best. On P01 this gives 129.91; the relationship charge the arena billed on our P01 deal
implies 129.95. Where a plant-specific should-cost exists the floors sit within 3-5 % of it (P02
363.96 vs 374.95, P03 397.46 vs 403.21, P10 25.64 vs 24.31), as close as the estimate itself.

| Case | Type / goal | Floor per supplier (value at its standard terms) | C_best |
|---|---|---|---|
{floors}

## Fitted dynamics

first_step: share of (opening - floor) in the first counter; mirror: share of our step it gives back;
cap: most it gives back for our step in its 2nd counter (share of its opening value), shrinking by
cap_decay per further counter; patience: our messages until final_offer (a tiny step counts twice);
claim_w: share of (ask - floor) a verified claim takes off, for the kinds of data the real supplier
said it "took into account". Coordinate descent on all sessions, then per case from there. Cases with
one session are fitted on 2-6 replies: plausible values, not measurements.

| Case | first_step | mirror | cap | cap_decay | patience | claim_w | data that moved it |
|---|---|---|---|---|---|---|---|
{dyn}
"""
    Path(path).write_text(text, encoding="utf-8")


class Stepper:
    """Jonathan's sandbox probe h2/h8/h10 (experiments/sandbox_probes.py) as an agent: fixed terms,
    open at `start`, raise by `step` per e-mail while staying 0.30 below the supplier, accept as soon
    as it stops saying `open` (at most 8 e-mails)."""

    def __init__(self, start, step, fixed, margin=0.3, max_messages=8):
        self.ask, self.step, self.fixed, self.margin, self.max = start, step, fixed, margin, max_messages
        self.sent = 0

    def decide(self, case, threads):
        from arena_kit.play import latest, standing

        sid = case["suppliers"][0]
        events = threads[sid]
        status = latest(events).get("status")
        sheet_id, terms = standing(events)
        if self.sent and (status != "open" or self.sent >= self.max):
            return {"supplier_id": sid, "message": {"action": {"type": "accept", "term_sheet_id": sheet_id}}}
        if self.sent:
            self.ask = round(max(self.ask, min(self.ask + self.step, terms["unit_price"] - self.margin)), 2)
        self.sent += 1
        sheet = {**self.fixed, "unit_price": self.ask}
        return {
            "supplier_id": sid,
            "message": {"body": "We can improve our proposal.", "term_sheets": [{"terms": sheet}]},
        }


# experiments/RESULTS.md section 3: D01, 30 days, 24 months, start February
PROBES = [
    ("open 50.00, steps 0.05", 50.0, 0.05, [0.676, 0.676, 0.676]),
    ("open 50.00, steps 0.15", 50.0, 0.15, [0.75, 0.80]),
    ("open 49.00, steps 0.15", 49.0, 0.15, [0.75, 0.82]),
    ("open 48.60, steps 0.30", 48.6, 0.30, [0.79, 0.86]),
    ("open 48.00, steps 0.40", 48.0, 0.40, [0.88, 0.90]),
]


def probe_loss(scenario, facts, params, seeds=6):
    """Mean absolute gap between lab and arena scores of the sandbox step probes, with `params`."""
    from .table import LocalTable, Scenario, play_lab

    personas = {}
    for sid, p in scenario.personas.items():
        q = copy.copy(p)
        for k, v in params.items():
            setattr(q, k, v)
        personas[sid] = q
    s = Scenario(scenario.case, personas, scenario.c_open, scenario.c_best, name=scenario.name)
    fixed = {"payment_days": 30, "contract_months": 24, "effective_date": "2027-02-01"}
    gaps = []
    for _, start, step, arena in PROBES:
        lab = [play_lab(LocalTable(s, facts, seed=k), Stepper(start, step, fixed))["score"] for k in range(seeds)]
        gaps.append(abs(statistics.mean(lab) - statistics.mean(arena)))
    return statistics.mean(gaps)


def probe_check(facts, seeds=40):
    """The sandbox probes replayed closed-loop on the D01 twin family: does the lab rank them as the
    arena did? Returns rows (label, arena range, lab mean, lab spread)."""
    from .table import LocalTable, play_lab

    s = next(x for x in twins.load() if x.name == "D01")
    fixed = {"payment_days": 30, "contract_months": 24, "effective_date": "2027-02-01"}
    rows = []
    for label, start, step, arena in PROBES:
        scores = [
            play_lab(LocalTable(s, facts, seed=k, vary=True), Stepper(start, step, fixed))["score"]
            for k in range(seeds)
        ]
        rows.append((label, arena, statistics.mean(scores), statistics.pstdev(scores)))
    return rows
