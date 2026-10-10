"""`uv run python -m sellm.lab <command>` - or `scripts/lab <command>` (background runs, status).

Testing strategies (no arena calls, no quota):
    play <case> [--agent A] [--knobs K]   one negotiation, every e-mail printed (P01, D02, X01-007, ...)
    compare <agent> <agent> ...           agents side by side on the train and test scenarios
    search [--minutes M]                  random Calculator variants, the best kept, scored on unseen tests
    stress [--agent A] [--knobs K]        everything the final may bring: crashes, 422s, broken must-haves
    status                                the newest run: progress, and whether a lab run is going

Building the lab:
    calibrate                    rebuild sellm/lab/twins.json from runs/ (after new sessions were pulled)
    backtest [--fit] [--write]   replay our real sessions into the twins; --fit tunes them, --write reports
    validate [--llm]             the same agent in lab and arena: naive (free); --llm the kit LLM (costs)
    twins | scenarios            list the twins / a sample of generated scenarios
    ui [--port 8765]             a local web UI to start, watch, tune, extend and export runs

Agents (A): naive, calc (the rule-based Calculator), llm (the kit's LLM agent: costs LLM calls), or
any 'module:Class' with decide(case, threads). Knobs (K): a JSON object, or a run's best.json
(rank 1, or path#3 for rank 3). Runs write runs/lab/<time>-<command>[-label]/ with report.md,
best.json, progress.log. More in sellm/lab/README.md.
"""

import argparse
import json
import logging
import os
import statistics
import subprocess
import sys
import time
from pathlib import Path

from arena_kit.cli import load_env
from arena_kit.data import DataPackage

from . import twins

RUNS = Path("runs/lab")


def package():
    pkg = DataPackage(os.environ.get("ARENA_DATA", "data/package"))
    pkg.lookup("")
    return pkg


def champion_knobs():
    """The knobs of our agent as it stands (sellm/agent.py, group A's file)."""
    import sellm.agent

    return dict(getattr(sellm.agent, "KNOBS", {}))


def parse_knobs(text):
    """A JSON object; 'champion' (our agent's knobs) optionally '+{json}' on top; or
    path/to/best.json[#rank] from an earlier run."""
    if not text:
        return {}
    text = text.strip()
    if text.startswith("champion"):
        extra = text[len("champion") :].lstrip("+").strip()
        return {**champion_knobs(), **(json.loads(extra) if extra else {})}
    if text.startswith("{"):
        return json.loads(text)
    path, _, rank = text.partition("#")
    best = json.loads(Path(path).read_text(encoding="utf-8"))
    return best[int(rank or 1) - 1]["knobs"] or {}


def opts_of(a):
    return {
        "clock": not a.no_clock,
        "mode": a.mode,
        "wave_cap_s": None if a.no_clock or a.wave_cap <= 0 else a.wave_cap,
        "think_s": None if a.think < 0 else a.think,
        "vary": not a.fixed_twins,
        "reader": a.reader,
        "supplier": a.supplier,
        "no_cache": a.no_cache,
    }


def find_scenario(name, pkg):
    for s in twins.load():
        if s.name == name:
            return s
    from . import invent

    if name.startswith("X") and "-" in name:
        seed, index = int(name[1:].split("-")[0]), int(name.split("-")[1])
        for s in invent.generate(index + 1, pkg, seed=seed):
            if s.name == name:
                return s
    raise SystemExit(f"no scenario {name}: a twin ('twins' lists them) or a generated name ('scenarios')")


def cmd_play(a):
    from .table import LocalTable, play_lab
    from .tournament import make_agent

    pkg = package()
    s = find_scenario(a.case.split(":")[-1], pkg)
    o = opts_of(a)
    from .tournament import brain_for, reader_for

    table = LocalTable(
        s, pkg.facts, seed=a.seed, clock=o["clock"], wave_cap_s=o["wave_cap_s"], think_s=o["think_s"],
        vary=o["vary"] and s.kind == "twin", reader=reader_for(o), supplier=o["supplier"], brain=brain_for(o),
        package=pkg,
    )  # fmt: skip
    r = play_lab(table, make_agent(a.agent, parse_knobs(a.knobs), pkg), mode=o["mode"])
    c = s.case
    print(f"== {s.name} ({s.kind}) {c['type']} / {c['buyer']['category_goal']}: {c['title']}")
    print(f"   negotiable {c['negotiable']}; must-haves {c['buyer']['must_haves']}; tags {s.tags}")
    print(f"   C_open {s.c_open:,.0f}  C_best {s.c_best:,.0f}  alternative {s.c_alt and round(s.c_alt)}")
    for sid, p in table.personas.items():
        print(f"   {sid} {p.name}: {p.archetype}, hidden floor {p.full_cost:.2f}, opening {p.opening}")
    for sid, t in table.threads.items():
        print(f"\n--- thread {sid}")
        for m in t.history:
            who = "US      " if m.get("from") == "buyer" else f"SUPPLIER {m.get('status')}"
            sheets = "  |  ".join(json.dumps(x.get("terms", x)) for x in m.get("term_sheets") or [])
            action = f" ACTION {m['action']}" if m.get("action") else ""
            print(f"[{m.get('_at', 0):5.0f} s] {who}{action}  {sheets}")
            body = (m.get("body") or "").strip().replace("\n\n", "\n")
            if body:
                print("    " + body.replace("\n", "\n    ")[:1500])
            if m.get("claim_results"):
                print(f"    claims: {[x['result'] for x in m['claim_results']]}")
            for att in m.get("attachments") or []:
                print(f"    attached: {att['name']}")
    keep = ("end_reason", "deal", "supplier_id", "terms", "c_open", "c_deal", "c_best", "c_alt", "score",
            "rounds", "seconds", "timeouts", "rejected", "llm_calls", "llm_fail")  # fmt: skip
    print("\n" + json.dumps({k: r.get(k) for k in keep}, indent=1, default=str))
    if r.get("cost_breakdown"):
        print("cost breakdown:", {k: round(v) for k, v in r["cost_breakdown"].items() if v})


def run_dir(cmd, label):
    return RUNS / f"{time.strftime('%Y%m%d-%H%M%S')}-{cmd}{'-' + label if label else ''}"


def cmd_tournament(a):
    from . import tournament as t

    pkg = package()
    out = run_dir(a.cmd, a.label)
    o = opts_of(a)
    print(f"run folder: {out}  (progress: {out / 'progress.log'})", flush=True)
    train, test = t.build_pools(a.invented, a.invent_seed, a.test, pkg)
    workers = a.workers or (24 if a.supplier == "llm" else None)  # LLM suppliers wait on the network
    run = t.Run(out, o, train, test, workers)
    t0 = time.time()
    try:
        if a.cmd == "compare":
            knobs = {"calc": parse_knobs(a.knobs)} if a.knobs else {}  # knobs are the Calculator's
            rows = t.compare(run, a.agents, a.seeds, knobs)
            title = f"Lab compare {out.name}: {' vs '.join(a.agents)}"
        else:
            base = parse_knobs(a.around) if a.around else None
            rows = t.search(run, a.minutes, a.start, a.seeds, a.seed, around=base)
            title = f"Lab search {out.name}: {a.minutes:g} min, {a.start} random variants to start"
        text = t.write(run, rows, title)
        text += f"\nRun: `python -m sellm.lab {' '.join(sys.argv[1:])}`, {time.time() - t0:.0f} s, options {o}.\n"
        (out / "report.md").write_text(text, encoding="utf-8")
        run.log(f"report: {out / 'report.md'}")
        print(text)
    finally:
        run.close()


def cmd_challenge(a):
    """One change against the champion, paired on the unseen test pool: adopt it or not."""
    from . import tournament as t

    pkg = package()
    challenger = parse_knobs(a.knobs if a.knobs.startswith(("champion", "{", "runs")) else "champion+" + a.knobs)
    champ = champion_knobs()
    delta = {k: v for k, v in challenger.items() if champ.get(k) != v}
    out = run_dir("challenge", a.label or "-".join(f"{k}-{v}" for k, v in delta.items())[:60])
    print(f"run folder: {out}\nchallenger = champion + {delta}", flush=True)
    o = opts_of(a)
    workers = a.workers or (24 if a.supplier == "llm" else None)
    train, test = t.build_pools(0, a.invent_seed, a.test, pkg)
    run = t.Run(out, o, [], train + test if a.all_twins else test, workers)
    try:
        jobs = [(name, k, s.name, seed) for name, k in (("calc", champ), ("calc", challenger))
                for s in run.test for seed in range(a.seeds)]  # fmt: skip
        rows = run.play(jobs)
        d, se, n = t.paired(rows, t._key("calc", challenger), t._key("calc", champ))
        verdict = (
            "ADOPT: clearly better"
            if d > 2 * se
            else "REJECT: clearly worse"
            if d < -2 * se
            else "TIE: not distinguishable"
        )
        stats = t.summarise(rows)
        lines = [f"# Challenge {out.name}", "", f"Challenger = champion (sellm/agent.py KNOBS) + `{json.dumps(delta)}`",
                 f"Options {o}; {n} test scenarios x {a.seeds} seeds.", "",
                 f"**{verdict}**: {100 * d:+.1f} ± {100 * se:.1f} points (paired)", "",
                 "| | Test | Twins | Case files | Invented | Worst 10 % | Crash | 422 | Broken | Worse | No deal |",
                 "|---|---|---|---|---|---|---|---|---|---|---|"]  # fmt: skip
        for label, k in (("champion", champ), ("challenger", challenger)):
            s = stats[t._key("calc", k)]
            lines.append(
                f"| {label} | {100 * s['test']:.1f} | {100 * s['twins']:.1f} | {100 * s['data']:.1f} | "
                f"{100 * s['invented']:.1f} | {100 * s['worst10']:.1f} | {s['crashes']} | {s['rejected']} | "
                f"{s['broken']} | {s['worse']} | {s['no_deal']} |"
            )
        lines += ["", "By case type (champion / challenger): " + ", ".join(
            f"{k} {100 * stats[t._key('calc', champ)]['by']['type'].get(k, 0):.0f}/"
            f"{100 * stats[t._key('calc', challenger)]['by']['type'].get(k, 0):.0f}"
            for k in sorted(stats[t._key("calc", champ)]["by"]["type"]))]  # fmt: skip
        text = "\n".join(lines) + "\n"
        (out / "report.md").write_text(text, encoding="utf-8")
        (out / "best.json").write_text(
            json.dumps([{"knobs": challenger, "delta": delta, "diff": d, "se": se}], indent=1)
        )
        print(text)
    finally:
        run.close()


def cmd_stress(a):
    from . import stress

    pkg = package()
    out = run_dir("stress", a.label or a.agent.replace(":", "-").replace(".", "-"))
    print(f"run folder: {out}", flush=True)
    knobs = parse_knobs(a.knobs)
    workers = a.workers or (24 if a.supplier == "llm" else None)  # LLM suppliers wait on the network
    rows = stress.run(out, a.agent, knobs, pkg, a.n, a.per_edge, a.seeds, workers=workers, opts=opts_of(a))
    text, verdict = stress.report(rows, a.agent, knobs)
    (out / "report.md").write_text(text, encoding="utf-8")
    print(text)
    print(f"report: {out / 'report.md'}")
    if verdict != "PASS":
        raise SystemExit(1)


def cmd_status(a):
    procs = subprocess.run(["pgrep", "-af", r"sellm\.lab (search|compare|stress)"], capture_output=True, text=True)
    lines = [x for x in procs.stdout.splitlines() if "pgrep" not in x]
    print("running:" if lines else "no lab run is going")
    for x in lines:
        print("  ", x[:160])
    runs = sorted(p for p in RUNS.glob("*/") if any(p.rglob("progress.log")))
    if not runs:
        print("no runs yet")
        return
    last = runs[-1]
    print(f"newest run: {last}")
    for log in sorted(last.rglob("progress.log")):
        print(f"--- {log}")
        print("".join(log.read_text(encoding="utf-8").splitlines(keepends=True)[-a.lines :]), end="")
    if (last / "report.md").exists():
        print(f"report: {last / 'report.md'}")


def cmd_validate(a):
    from .table import LocalTable, play_lab
    from .tournament import make_agent

    pkg = package()
    real = {}
    for f in [*Path("runs").glob("practice/*/*.json"), *Path("runs").glob("sandbox/*/*.json")]:
        d = json.loads(f.read_text(encoding="utf-8"))
        lab = d.get("label", "")
        kind = "naive" if lab.startswith("kit naive") else "llm" if lab.startswith("kit llm") else None
        if kind and (d.get("state") or {}).get("result"):
            real.setdefault((kind, d["case_id"].split(":")[1]), []).append(d["state"]["result"]["score"])
    from .backtest import probe_check

    brain = None
    if a.supplier == "llm":
        from .llm_supplier import Brain

        brain = Brain()
    seeds = 40 if brain is None else 6
    print(f"Whole negotiations: the sandbox step probes (experiments/RESULTS.md), D01 family, {a.supplier} suppliers")
    print(f"| Probe | Arena | Lab ({seeds} family members) |\n|---|---|---|")
    for label, arena, mean, sd, fitted in probe_check(pkg.facts, seeds, brain=brain, package=pkg):
        mark = "" if fitted else " **(prediction)**"
        print(f"| {label}{mark} | {min(arena):.2f}-{max(arena):.2f} | {mean:.3f} ± {sd:.3f} |")
    print()
    kinds = ["naive"] + (["llm"] if a.llm else [])
    print("| Agent | Case | Arena | Lab |\n|---|---|---|---|")
    for kind in kinds:
        pairs = []
        for s in twins.load():
            arena = real.get((kind, s.name))
            if not arena:
                continue
            lab = [
                play_lab(
                    LocalTable(s, pkg.facts, seed=i, supplier=a.supplier, brain=brain, package=pkg),
                    make_agent(kind, {}, pkg),
                )["score"]
                for i in range(1 if kind == "llm" or brain is not None else 5)
            ]
            pairs.append((statistics.mean(arena), statistics.mean(lab)))
            print(f"| {kind} | {s.name} | {pairs[-1][0]:.3f} | {pairs[-1][1]:.3f} |")
        if pairs:
            diff = statistics.mean(abs(x - y) for x, y in pairs)
            mean_a, mean_l = statistics.mean(x for x, _ in pairs), statistics.mean(y for _, y in pairs)
            print(f"| {kind} | **mean** | {mean_a:.3f} | {mean_l:.3f} (mean abs diff per case {diff:.3f}) |")


def cmd_scenarios(a):
    from . import invent

    pkg = package()
    for s in invent.generate(a.n, pkg, seed=a.invent_seed):
        fields = ",".join(f for f in s.case["negotiable"] if f != "unit_price")
        arch = ",".join(p.archetype for p in s.personas.values())
        goal = s.case["buyer"]["category_goal"]
        print(f"{s.name} {s.kind:8} {s.case['type']:14} {goal:13} {fields:58} {arch:22} {s.tags}")


def main(argv=None):
    load_env()
    ap = argparse.ArgumentParser(prog="python -m sellm.lab", description=__doc__.split("\n\n")[0])
    ap.add_argument("-v", "--verbose", action="store_true")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def lab_opts(p):
        p.add_argument(
            "--mode", default="parallel", choices=["parallel", "sequential"],
            help="parallel: one loop per thread (what our runner must do); sequential: the kit's play()",
        )  # fmt: skip
        p.add_argument("--no-clock", action="store_true", help="no simulated time, timeouts or wave cap")
        p.add_argument("--wave-cap", type=float, default=480, help="seconds per case as in the final (0: none)")
        p.add_argument("--think", type=float, default=2.0, help="our seconds per move (-1: the real time taken)")
        p.add_argument("--fixed-twins", action="store_true", help="the fitted twins only, not their families")
        p.add_argument(
            "--reader", default="keywords", choices=["keywords", "llm"],
            help="how suppliers read our e-mails: keyword rules, or an LLM (LAB_READER_MODEL or LLM_MODEL; costs)",
        )  # fmt: skip
        p.add_argument(
            "--supplier", default="engine", choices=["engine", "llm"],
            help="engine: the calibrated rules (fast, free); llm: an LLM plays each supplier inside them (costs calls)",
        )  # fmt: skip
        p.add_argument("--no-cache", action="store_true", help="llm suppliers: no answers from runs/lab/llm-cache")
        p.add_argument("--invent-seed", type=int, default=1)
        p.add_argument("--workers", type=int, default=None)
        p.add_argument("--label", default="")

    sub.add_parser("calibrate")
    sub.add_parser("twins")
    b = sub.add_parser("backtest")
    b.add_argument("--fit", action="store_true")
    b.add_argument("--write", action="store_true", help="write runs/lab/BACKTEST.md")
    b.add_argument(
        "--supplier", default="engine", choices=["engine", "llm"], help="llm: the LLM suppliers (about 240 calls)"
    )
    p = sub.add_parser("play")
    p.add_argument("case")
    p.add_argument("--agent", default="calc")
    p.add_argument("--knobs", default="")
    p.add_argument("--seed", type=int, default=0)
    lab_opts(p)
    for name in ("compare", "search"):
        t = sub.add_parser(name)
        if name == "compare":
            t.add_argument("agents", nargs="+")
            t.add_argument("--knobs", default="", help="knobs for the 'calc' agent")
        else:
            t.add_argument("--minutes", type=float, default=10)
            t.add_argument("--start", type=int, default=64, help="random variants in the first round")
            t.add_argument("--seed", type=int, default=0)
            t.add_argument("--around", default="", help="'champion': start from our agent's knobs and their neighbours")
        t.add_argument("--invented", type=int, default=160, help="generated scenarios for training")
        t.add_argument("--test", type=int, default=80, help="generated scenarios for the test")
        t.add_argument("--seeds", type=int, default=2, help="runs per strategy and scenario")
        lab_opts(t)
    ch = sub.add_parser("challenge", help="a change against the champion: 'challenge {\"adaptive\": true}'")
    ch.add_argument("knobs", help="JSON added to the champion's knobs, or champion+{...}, or a best.json")
    ch.add_argument("--test", type=int, default=160, help="generated test scenarios (plus the held-out twins)")
    ch.add_argument("--seeds", type=int, default=2)
    ch.add_argument("--all-twins", action="store_true", help="also play all twins and the train pool's case files")
    lab_opts(ch)
    s = sub.add_parser("stress")
    s.add_argument("--agent", default="calc")
    s.add_argument("--knobs", default="")
    s.add_argument("--n", type=int, default=120, help="generated scenarios besides the edge cases")
    s.add_argument("--per-edge", type=int, default=6)
    s.add_argument("--seeds", type=int, default=2)
    lab_opts(s)
    st = sub.add_parser("status")
    st.add_argument("--lines", type=int, default=15)
    v = sub.add_parser("validate")
    v.add_argument("--llm", action="store_true", help="also the kit LLM agent: about 60 LLM calls")
    v.add_argument("--supplier", default="engine", choices=["engine", "llm"], help="llm: LLM suppliers (~200 calls)")
    u = sub.add_parser("ui")
    u.add_argument("--port", type=int, default=8765)
    u.add_argument("--no-browser", action="store_true")
    sc = sub.add_parser("scenarios")
    sc.add_argument("--n", type=int, default=30)
    sc.add_argument("--invent-seed", type=int, default=1)
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO if a.verbose else logging.WARNING, format="%(message)s")

    if a.cmd == "calibrate":
        scenarios = twins.build(package())
        twins.save(scenarios)
        for x in scenarios:
            print(x.name, x.notes, {k: round(p.full_cost, 2) for k, p in x.personas.items()})
        print(f"wrote {twins.CACHE}; run 'backtest --fit --write' next to refit the dynamics")
    elif a.cmd == "twins":
        for x in twins.load():
            floors = {k: round(p.full_cost, 2) for k, p in x.personas.items()}
            print(f"{x.name:5} {x.case['type']:15} {x.case['buyer']['category_goal']:14} floors {floors}  {x.notes}")
    elif a.cmd == "backtest":
        from . import backtest

        pkg, scenarios = package(), twins.load()
        if a.fit:
            _, per, ranges = backtest.fit(scenarios, pkg.facts)
            for x in scenarios:
                for p in x.personas.values():
                    for k, val in per[x.name].items():
                        setattr(p, k, val)
                    p.ranges = {**ranges[x.name], "noise": [0.05, 0.1, 0.2]}
            twins.save(scenarios)
            print(f"wrote {twins.CACHE}")
        if a.supplier == "llm":
            from .llm_supplier import Brain

            brain = Brain()
            rows = backtest.evaluate(scenarios, pkg.facts, brain=brain, package=pkg)
            print(f"LLM suppliers: {brain.calls} calls, {brain.cached} from the cache")
        else:
            rows = backtest.evaluate(scenarios, pkg.facts)
        print(backtest.report(rows))
        if a.write:
            backtest.write_report(scenarios, rows, "runs/lab/BACKTEST.md")
            print("wrote runs/lab/BACKTEST.md")
    elif a.cmd == "play":
        cmd_play(a)
    elif a.cmd in ("compare", "search"):
        cmd_tournament(a)
    elif a.cmd == "challenge":
        cmd_challenge(a)
    elif a.cmd == "stress":
        cmd_stress(a)
    elif a.cmd == "status":
        cmd_status(a)
    elif a.cmd == "validate":
        cmd_validate(a)
    elif a.cmd == "scenarios":
        cmd_scenarios(a)
    elif a.cmd == "ui":
        from .ui import serve

        serve(a.port, browser=not a.no_browser)


if __name__ == "__main__":
    main()
