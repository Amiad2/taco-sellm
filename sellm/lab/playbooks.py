"""Per-case playbooks: for each twin the knob set of the negotiator that scores best in the lab.

`python -m sellm.lab.playbooks base [--llm]` scores the champion (sellm.agent defaults) on every twin;
`... search P01 --minutes 10 [--llm]` searches the negotiator's knobs on one twin and its family.
"""

import argparse
import json
import random
import statistics
import time
from pathlib import Path

from arena_kit.cli import load_env
from arena_kit.data import DataPackage

from . import twins
from .spaces import NEGOTIATOR as BASE_SPACE
from .tournament import Run, mutate

AGENT = "sellm.agent:make_agent"
# the negotiator's knobs the playbooks may set (sellm/negotiator.py DEFAULTS)
NEGOTIATOR = {
    **BASE_SPACE,
    "horizon": [2, 3, 4, 5, 6],
    "pace": [0.3, 0.5, 0.7, 0.9, 1.0],
    "levers": ["ours", "theirs"],
    "dossier": [True, False],
}
ROOT = Path(__file__).resolve().parents[2]


def opts(llm, think=2.0):
    return dict(clock=True, wave_cap_s=480.0, think_s=think, vary=True, mode="parallel",
                supplier="llm" if llm else "engine", reader=None, no_cache=False)  # fmt: skip


def scenarios(names=None):
    tw = twins.load()
    return [s for s in tw if not names or s.name in names]


def score_table(rows):
    by = {}
    for r in rows:
        by.setdefault((r["scenario"], json.dumps(r["knobs"], sort_keys=True)), []).append(r["score"])
    return by


def main(argv=None):
    load_env(ROOT / ".env")
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["base", "search"])
    ap.add_argument("names", nargs="*")
    ap.add_argument("--llm", action="store_true")
    ap.add_argument("--seeds", type=int, default=6)
    ap.add_argument("--minutes", type=float, default=10)
    ap.add_argument("--knobs", default="{}")
    ap.add_argument("--out", default="")
    a = ap.parse_args(argv)
    sc = scenarios(a.names)
    out = a.out or str(ROOT / "runs" / "lab" / f"{time.strftime('%Y%m%d-%H%M')}-playbook-{a.cmd}")
    run = Run(out, opts(a.llm), sc, [], workers=8)
    try:
        if a.cmd == "base":
            knobs = json.loads(a.knobs)
            rows = run.play([(AGENT, knobs, s.name, k) for s in sc for k in range(a.seeds)])
            for (name, _), v in sorted(score_table(rows).items()):
                print(f"{name:6s} {statistics.mean(v):.3f}  (n={len(v)}, min {min(v):.2f})")
            print("mean", round(statistics.mean(r["score"] for r in rows), 3))
            print("llm_fail", sum(r.get("llm_fail", 0) for r in rows), "crash", sum(1 for r in rows if r.get("crash")))
        else:
            rng = random.Random(1)
            champ = json.loads(a.knobs)
            variants = [champ] + [mutate(rng, champ, NEGOTIATOR) for _ in range(60)]
            deadline = time.time() + 60 * a.minutes
            results = {}
            while time.time() < deadline and variants:
                rows = run.play([(AGENT, v, s.name, k) for v in variants for s in sc for k in range(a.seeds)], deadline)
                for (name, kj), v in score_table(rows).items():
                    results.setdefault(kj, []).extend(v)
                ranked = sorted(results.items(), key=lambda kv: -statistics.mean(kv[1]))
                print(f"best so far {statistics.mean(ranked[0][1]):.3f} {ranked[0][0]}", flush=True)
                top = [json.loads(k) for k, _ in ranked[:6]]
                variants = [mutate(rng, rng.choice(top), NEGOTIATOR) for _ in range(40)]
            ranked = sorted(results.items(), key=lambda kv: -statistics.mean(kv[1]))
            Path(out, "best.json").write_text(json.dumps(
                [{"mean": round(statistics.mean(v), 4), "n": len(v), "knobs": json.loads(k)} for k, v in ranked[:10]],
                indent=1))  # fmt: skip
            for k, v in ranked[:5]:
                print(f"{statistics.mean(v):.3f} n={len(v)} {k}")
    finally:
        run.close()


if __name__ == "__main__":
    main()
