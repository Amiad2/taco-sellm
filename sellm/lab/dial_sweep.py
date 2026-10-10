# ruff: noqa: E501
"""Dial sweeps on one twin: every dial alone at each level (all others at their defaults), then the
best levels combined. Paired seeds: every level is played on the same twin family members.

    python -m sellm.lab.dial_sweep P02 [--llm] [--seeds 8] [--phase one|combo|both]
"""

import argparse
import itertools
import json
import statistics
import time

from arena_kit.cli import load_env

from .playbooks import ROOT, opts, scenarios
from .tournament import Run

AGENT = "sellm.lab.dials:DialNegotiator"
LEVELS = {
    "pay_days": [30, 60, 90],
    "idx": ["none", "db0", "db3", "db5"],
    "open_below": [0.02, 0.06, 0.10, 0.15],
    "pace": [0.3, 0.5, 0.8, 1.0],
    "horizon": [3, 4, 5, 6],
    "keep_below": [0.0, 0.006, 0.02],
    "floor_share": [0.88, 0.92, 0.96, 0.98],
    "n_args": [0, 1, 2, 3],
    "arg_first": [0, 1],
    "arg_order": ["history", "delivery", "notice", "forecast", "quality"],
    "tone": ["warm", "firm", "empathy", "split", "volume"],
    "menu": [0],
}


def play(run, books, names, seeds):
    jobs = [(AGENT, k, n, 700 + j) for k in books for n in names for j in range(seeds)]
    rows = run.play(jobs)
    out = {}
    for r in rows:
        out.setdefault(json.dumps(r["knobs"], sort_keys=True), {})[(r["scenario"], r["seed"])] = r["score"]
    return out, rows


def stats(cell, base):
    keys = sorted(set(cell) & set(base))
    d = [cell[k] - base[k] for k in keys]
    m = statistics.mean(cell[k] for k in keys)
    se = statistics.stdev(d) / len(d) ** 0.5 if len(d) > 1 else 0.0
    return m, statistics.mean(d), se


def main():
    load_env(ROOT / ".env")
    ap = argparse.ArgumentParser()
    ap.add_argument("case")
    ap.add_argument("--llm", action="store_true")
    ap.add_argument("--seeds", type=int, default=8)
    ap.add_argument("--phase", default="both", choices=["one", "combo", "both"])
    ap.add_argument("--top", type=int, default=4, help="dials whose best level goes into the combinations")
    a = ap.parse_args()
    sc = scenarios([a.case])
    out = (
        ROOT
        / "runs"
        / "lab"
        / "playbooks"
        / f"{time.strftime('%Y%m%d-%H%M')}-dials-{a.case}-{'llm' if a.llm else 'engine'}"
    )
    run = Run(out, opts(a.llm), sc, [], workers=24 if a.llm else 8, log=lambda *_: None)
    lines = []
    try:
        names = [a.case]
        base_books = [{}]
        books = base_books + [{d: v} for d, vs in LEVELS.items() for v in vs]
        cells, rows = play(run, books, names, a.seeds)
        base = cells["{}"]
        lines.append(
            f"{a.case} one dial at a time ({'LLM' if a.llm else 'engine'} suppliers, {a.seeds} paired seeds); baseline {statistics.mean(base.values()):.3f}"
        )
        best = {}
        for d, vs in LEVELS.items():
            res = []
            for v in vs:
                m, delta, se = stats(cells[json.dumps({d: v}, sort_keys=True)], base)
                res.append((v, m, delta, se))
            lines.append(f"  {d:12s} " + "  ".join(f"{v}:{m:.3f}({delta:+.3f}±{se:.3f})" for v, m, delta, se in res))
            top = max(res, key=lambda r: r[1])
            if top[2] > 1.5 * top[3] and top[2] > 0.005:
                best[d] = (top[0], top[2])
        lines.append("  levels clearly above the baseline: " + json.dumps({d: v[0] for d, v in best.items()}))
        if a.phase != "one" and best:
            chosen = sorted(best, key=lambda d: -best[d][1])[: a.top]
            combos = []
            for r in range(1, len(chosen) + 1):
                for sub in itertools.combinations(chosen, r):
                    combos.append({d: best[d][0] for d in sub})
            cells2, rows2 = play(run, combos, names, a.seeds)
            lines.append("combinations of the best levels:")
            res = sorted(
                ((stats(cells2[json.dumps(c, sort_keys=True)], base), c) for c in combos), key=lambda x: -x[0][0]
            )
            for (m, delta, se), c in res[:8]:
                lines.append(f"  {m:.3f} ({delta:+.3f}±{se:.3f})  {json.dumps(c)}")
            (out / "best.json").write_text(
                json.dumps([{"mean": round(m, 4), "knobs": c} for (m, _, _), c in res[:8]], indent=1)
            )
        lines.append(
            f"llm_fail {sum(r.get('llm_fail', 0) for r in rows)}  crash {sum(1 for r in rows if r.get('crash'))}"
        )
    finally:
        run.close()
    text = "\n".join(lines)
    (out / "report.txt").write_text(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
