"""Stress test: does an agent survive everything the final may bring?

It plays the agent on the twins, every edge case (`invent.EDGES`) and a set of generated scenarios,
with the clock and the 8-minute wave cap, one thread at a time and one loop per thread, and counts
what would cost points in the final:

  crash        an exception: the kit's runner loses the case
  422          a refused move (an invalid sheet, a stale offer ID): the kit's play() crashes on it
  broken       a deal that breaks a must-have: score 0
  worse        a deal worse than the opening: score 0
  below_alt    ended under what walking away would have scored (e.g. took a deal when the
               alternative was better, or walked when a deal beat the alternative)
  wave_cap     the case ran out of time: no deal
  timeouts     threads left more than 60 s

The verdict is FAIL if any crash, 422 or broken must-have occurred; the other counts are warnings
(a deal worse than the opening scores 0, like walking away without an alternative).
"""

import statistics

from . import invent, twins
from .tournament import Run, summarise

CHECKS = ("crashes", "rejected", "broken", "worse", "below_alt", "wave_cap", "timeouts")
HARD = ("crashes", "rejected", "broken")  # 'worse' scores 0 like no deal: a warning, not a failure


def pools(package, n=120, per_edge=6, seed=7):
    scen = (
        twins.load()
        + invent.edge_suite(package, per_edge=per_edge, seed=seed * 10)
        + invent.generate(n, package, seed=seed)
    )
    return scen


def run(out, agent, knobs, package, n=120, per_edge=6, seeds=2, seed=7, workers=None, log=print, opts=None):
    scen = pools(package, n, per_edge, seed)
    rows = []
    for mode in ("sequential", "parallel"):
        o = {**(opts or {}), "mode": mode}
        r = Run(f"{out}/{mode}", o, scen, [], workers, log)
        jobs = [(agent, knobs, s.name, k) for s in scen for k in range(seeds)]
        r.log(f"stress {agent} {knobs or ''} ({mode}): {len(jobs)} negotiations")
        part = r.play(jobs)
        for x in part:
            x["mode"] = mode
        rows += part
        r.close()
    return rows


def report(rows, agent, knobs):
    lines = [f"# Stress test: {agent} {knobs or ''}", ""]
    verdict = "PASS"
    for mode in ("sequential", "parallel"):
        rs = [r for r in rows if r.get("mode") == mode]
        if not rs:
            continue
        st = next(iter(summarise(rs).values()))
        bad = {k: st[k] for k in HARD if st[k]}
        if bad:
            verdict = "FAIL"
        lines += [
            f"## {mode} ({'the kit runner' if mode == 'sequential' else 'one loop per thread'}): "
            f"mean {100 * st['mean']:.1f} over {st['scenarios']} scenarios, {st['negotiations']} negotiations",
            "",
            "| Check | Count | Worst scenarios |",
            "|---|---|---|",
        ]
        for c in CHECKS:
            key = {"crashes": "crash", "rejected": "rejected", "broken": "broken", "worse": "worse",
                   "below_alt": "below_alt", "wave_cap": "wave_cap", "timeouts": "timeouts"}[c]  # fmt: skip
            hits = [r for r in rs if _hit(r, key)]
            names = sorted({f"{r['scenario']} ({', '.join(r['tags']) or r['kind']})" for r in hits})[:4]
            lines.append(f"| {c} | {st[c]} | {'; '.join(names) or '-'} |")
        lines.append("")
        for dim, name in (("tags", "edge case"), ("archetypes", "archetype"), ("type", "case type")):
            by = st["by"][dim]
            lines.append(
                f"By {name}: " + ", ".join(f"{k} {100 * v:.0f}" for k, v in sorted(by.items(), key=lambda x: x[1]))
            )
            lines.append("")
        crashes = [r for r in rs if "crash" in r]
        for r in crashes[:3]:
            lines += [f"Crash on {r['scenario']}: `{r['crash']}`", "", "```", r.get("trace", "")[-500:], "```", ""]
        secs = [r["wall_s"] for r in rs]
        lines.append(f"Our time per negotiation: median {statistics.median(secs):.2f} s, max {max(secs):.2f} s.")
        lines.append("")
    lines.insert(1, f"**{verdict}** (FAIL = any crash, refused move or broken must-have; the rest are warnings)")
    return "\n".join(lines) + "\n", verdict


def _hit(r, key):
    if key == "crash":
        return "crash" in r
    if key == "below_alt":
        return "crash" not in r and r["score"] < r.get("alt_score", 0) - 1e-9
    if key == "wave_cap":
        return r.get("end") == "wave_cap"
    if key in ("rejected", "timeouts"):
        return (r.get(key) or 0) > 0
    return bool(r.get(key))
