"""Cross-test of the per-twin playbooks: every twin's best knobs on every twin (engine or LLM suppliers).
The diagonal says how much tuning gains; the off-diagonal how much of it is specific to that supplier."""

import json
import statistics
import sys

from arena_kit.cli import load_env

from .playbooks import AGENT, ROOT, opts, scenarios
from .tournament import Run

NAMES = ["P01", "P02", "P03", "P04", "P05", "P07", "P08", "P10", "P11", "P18", "D01", "D02"]


def load_best(prefix="engine"):
    out = {}
    for n in NAMES:
        p = ROOT / "runs" / "lab" / "playbooks" / f"{prefix}-{n}" / "best.json"
        out[n] = json.loads(p.read_text())[0]["knobs"] if p.is_file() else {}
    return out


def main(llm=False, seeds=4):
    load_env(ROOT / ".env")
    sc = scenarios()
    best = load_best()
    books = {"champion": {}, **{f"pb-{n}": k for n, k in best.items()}}
    out = ROOT / "runs" / "lab" / "playbooks" / ("matrix-llm" if llm else "matrix-engine")
    run = Run(out, opts(llm), sc, [], workers=24 if llm else 8)
    try:
        jobs = [(AGENT, k, s.name, 500 + j) for k in books.values() for s in sc for j in range(seeds)]
        rows = run.play(jobs)
    finally:
        run.close()
    key = {json.dumps(k, sort_keys=True): n for n, k in books.items()}
    tab = {}
    for r in rows:
        tab.setdefault((key[json.dumps(r["knobs"], sort_keys=True)], r["scenario"]), []).append(r["score"])
    lines = ["book \\ twin  " + " ".join(f"{n:>5}" for n in NAMES) + "   mean"]
    for b in books:
        vals = [statistics.mean(tab[(b, n)]) for n in NAMES]
        lines.append(f"{b:12s} " + " ".join(f"{v:5.2f}" for v in vals) + f"  {statistics.mean(vals):.3f}")
    diag = statistics.mean(statistics.mean(tab[(f"pb-{n}", n)]) for n in NAMES)
    lines.append(f"diagonal (own book on own twin) {diag:.3f}; llm_fail {sum(r.get('llm_fail', 0) for r in rows)}; "
                 f"crash {sum(1 for r in rows if r.get('crash'))}")  # fmt: skip
    text = "\n".join(lines)
    (out / "matrix.txt").write_text(text + "\n")
    print(text)


if __name__ == "__main__":
    main(llm="--llm" in sys.argv, seeds=int(next((a.split("=")[1] for a in sys.argv if a.startswith("--seeds=")), 4)))
