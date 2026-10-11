# ruff: noqa  (analysis script of the Sat 21:15 review session: read-only against the arena, run from the repo root with the env of .env; see experiments/PRACTICE-ARMS.md)
"""Score table per case: kit LLM baseline (15:27), negotiator v1.1 (20:32), a1 (21:06 batch), and any later windows given as name=START-END epoch seconds."""

import sys, datetime
from arena_kit.client import ArenaClient

c = ArenaClient()
rows = c.sessions("practice")


def ts(h, m, s=0, day=10):
    return datetime.datetime(2026, 10, day, h, m, s).timestamp()


WIN = {
    "kit-llm": (ts(15, 27), ts(15, 32)),
    "v1.1": (ts(20, 32), ts(20, 34, 59)),
    "v1.1b": (ts(21, 3), ts(21, 4, 30)),
    "a1": (ts(21, 6, 30), ts(21, 8, 0)),
}
for a in sys.argv[1:]:
    name, rng = a.split("=")
    h1, h2 = rng.split("-")
    f = lambda x: ts(*map(int, x.split(":")))
    WIN[name] = (f(h1), f(h2))
cases = sorted({r["case_id"] for r in rows if r["case_id"].startswith("case:P")})
names = list(WIN)
print(f"{'case':8}" + "".join(f"{n:>10}" for n in names))
tot = {n: [] for n in names}
for cid in cases:
    line = f"{cid[5:]:8}"
    for n in names:
        lo, hi = WIN[n]
        got = [r for r in rows if r["case_id"] == cid and lo <= r["created_at"] <= hi]
        if got:
            sc = got[-1]["score"]
            line += (
                f"{(sc if sc is not None else float('nan')):>10.3f}"
                if got[-1]["status"] == "ended"
                else f"{'open':>10}"
            )
            if got[-1]["status"] == "ended" and sc is not None:
                tot[n].append(sc)
        else:
            line += f"{'-':>10}"
    print(line)
print(
    f"{'mean':8}"
    + "".join(f"{(100 * sum(v) / len(v) if v else float('nan')):>10.1f}" for v in tot.values())
    + "   (mean over cases played in that window)"
)
print(f"{'n':8}" + "".join(f"{len(v):>10}" for v in tot.values()))
