"""Playbook per group of cases vs one merged playbook, scored on scenarios the search never saw.

`python -m sellm.lab.pb_groups --by type --minutes 3`: for every group (case type, or goal, or
archetype of the first supplier) a knob search on the group's generated training scenarios, then every
group book, the merged book and the champion on the group's held-out scenarios.
"""

import argparse
import json
import statistics
import time

from arena_kit.cli import load_env
from arena_kit.data import DataPackage

from . import tournament as T
from .playbooks import AGENT, ROOT, opts


def group_of(s, by):
    if by == "type":
        return s.case.get("type")
    if by == "goal":
        return s.case["buyer"].get("category_goal")
    return sorted({p.archetype for p in s.personas.values()})[0]


def main(argv=None):
    load_env(ROOT / ".env")
    ap = argparse.ArgumentParser()
    ap.add_argument("--by", default="type", choices=["type", "goal", "archetype"])
    ap.add_argument("--minutes", type=float, default=3)
    ap.add_argument("--merged-minutes", type=float, default=10)
    ap.add_argument("--train", type=int, default=400)
    ap.add_argument("--test", type=int, default=200)
    ap.add_argument("--llm", action="store_true", help="the test phase with LLM suppliers")
    a = ap.parse_args(argv)
    pkg = DataPackage(ROOT / "data" / "package")
    pkg.lookup("")
    train, test = T.build_pools(a.train, 7, a.test, pkg)
    out = ROOT / "runs" / "lab" / "playbooks" / f"{time.strftime('%Y%m%d-%H%M')}-groups-{a.by}"
    out.mkdir(parents=True, exist_ok=True)
    groups = sorted({group_of(s, a.by) for s in train} - {None})
    books = {}
    for g in ["ALL", *groups]:
        tr = train if g == "ALL" else [s for s in train if group_of(s, a.by) == g]
        te = test if g == "ALL" else [s for s in test if group_of(s, a.by) == g]
        if len(tr) < 12 or not te:
            print(f"{g}: {len(tr)} train / {len(te)} test scenarios: skipped", flush=True)
            continue
        run = T.Run(out / g, opts(False), tr, te, workers=8, log=lambda *_: None)
        try:
            rows = T.search(run, minutes=a.merged_minutes if g == "ALL" else a.minutes, start=48, seeds=2,
                            test_top=3, test_seeds=2, baselines=(), around=None, agent=AGENT)  # fmt: skip
        finally:
            run.close()
        stats = T.summarise([r for r in rows if r["pool"] == "train"], min_scenarios=len(tr) // 2)
        top = max(stats.values(), key=lambda x: x["mean"])
        books[g] = top["knobs"]
        print(
            f"{g}: {len(tr)} train, {len(te)} test; book (train {100 * top['mean']:.1f}) {json.dumps(top['knobs'])}",
            flush=True,
        )
    (out / "books.json").write_text(json.dumps(books, indent=1))
    # held-out comparison: each scenario of the test pool, with its group's book, the merged book, the champion
    o = opts(a.llm)
    run = T.Run(out / "final", o, [], test, workers=24 if a.llm else 8, log=lambda *_: None)
    try:
        jobs, who = [], {}
        for s in test:
            g = group_of(s, a.by)
            for label, k in (
                ("champion", {}),
                ("merged", books.get("ALL", {})),
                ("group", books.get(g, books.get("ALL", {}))),
            ):
                for j in range(3):
                    jobs.append((AGENT, k, s.name, 900 + j))
                    who[(json.dumps(k, sort_keys=True), s.name, 900 + j, label)] = g
        rows = run.play(jobs)
    finally:
        run.close()
    lab = {}
    for r in rows:
        k = json.dumps(r["knobs"], sort_keys=True)
        for label, bk in (
            ("champion", {}),
            ("merged", books.get("ALL", {})),
            (
                "group",
                books.get(group_of(next(s for s in test if s.name == r["scenario"]), a.by), books.get("ALL", {})),
            ),
        ):
            if k == json.dumps(bk, sort_keys=True):
                lab.setdefault(label, {}).setdefault(
                    group_of(next(s for s in test if s.name == r["scenario"]), a.by), []
                ).append(r["score"])
    lines = [
        f"held-out test ({'LLM' if a.llm else 'engine'} suppliers), by {a.by}",
        f"{'group':14s} " + " ".join(f"{lb:>9}" for lb in ("champion", "merged", "group")),
    ]
    for g in groups:
        lines.append(
            f"{g:14s} "
            + " ".join(
                f"{statistics.mean(lab[lb][g]):9.3f}" if g in lab.get(lb, {}) else f"{'-':>9}"
                for lb in ("champion", "merged", "group")
            )
        )
    allv = {lb: [x for v in lab[lb].values() for x in v] for lb in lab}
    lines.append(
        f"{'ALL':14s} " + " ".join(f"{statistics.mean(allv[lb]):9.3f}" for lb in ("champion", "merged", "group"))
    )
    text = "\n".join(lines)
    (out / "report.txt").write_text(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
