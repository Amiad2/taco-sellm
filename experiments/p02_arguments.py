# ruff: noqa: E501  (sentences)
"""Which argument moves a supplier that has stopped at its limit? One practice session per variant.

P02 (Nordmark) ends at EUR 371.66 with 90 days whatever we ask (ten sessions, experiments/P02-ARGUMENTS.md):
price history and forecast are "taken into account", then it says "below this price we would need
facts, not just a lower number". Each variant here adds one kind of argument that was never sent to
it, on top of what `--agent sellm` plays - the prices, the steps and the close stay the agent's.

    uv run python experiments/p02_arguments.py --variants clause5 market --case P02
    uv run python experiments/p02_arguments.py --list

A variant is a plan for `Probe`: `structure` (fields of the first ask), `hold` (stay on that
structure), `script` ({number of our e-mail: {"before" | "after": [sentences], "replace": bool}})
and `when` ([(pattern in its last e-mail, [sentences])], said once). Sentences with a data ID follow
the wording the arena verified: one figure next to its IDs, nothing else in that sentence.
Rows: experiments/results/2026-10-11-p02-arguments.json. Sessions: runs/, labels `ARG <variant>`.
"""

import argparse
import importlib.util
import json
import math
import os
import re
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from arena_kit.cost import complete_offer  # noqa: E402
from sellm.agent import KNOBS  # noqa: E402
from sellm.endgame import Persistent  # noqa: E402

OUT = ROOT / "experiments" / "results" / "2026-10-11-p02-arguments.json"
LABELS = ROOT / "runs" / "labels.json"


def clause(deadband):
    def pick(case):
        for option in case.get("term_options", {}).get("index_clause") or []:
            if option and option.get("deadband_pct") == deadband:
                return {"index_clause": option}
        return {}

    return pick


VOLUME = [
    "You asked which volume we can commit to: the 6,110 units a year of this contract are a binding volume, not a forecast.",
    "We can add a fixed monthly call-off schedule and a rolling twelve-month forecast, so that you can plan your capacity.",
]
CLAUSE = "With the index clause the price follows copper beyond the deadband, so the copper risk no longer has to be priced in up front."
COMMITTEE = "We know from our annual reviews that a price change of this size goes to your pricing committee; please put our proposal before it - we are glad to wait for its next meeting."
VARIANTS = {
    # the letter passes copper on: an index clause on copper takes that risk off the supplier
    "clause5": dict(structure=clause(5), hold=True),
    "clause0": dict(structure=clause(0), hold=True),
    # facts about its market and its cost that are not among the part's cost drivers
    "market": dict(
        script={
            0: {
                "after": [
                    "The index PPI-C2711 changed +1.6 % from 2025-08 to 2026-08 (idx:PPI-C2711@2025-08, idx:PPI-C2711@2026-08).",
                    "That is the producer price index for electric motors: across the market, motor prices moved far less than the increase you ask for.",
                ]
            },
            1: {
                "after": [
                    "The index PPI-D351 changed -3.7 % from 2025-08 to 2026-08 (idx:PPI-D351@2025-08, idx:PPI-D351@2026-08).",
                    "That is the producer price of electricity, which is part of your conversion cost.",
                ]
            },
        }
    ),
    # the other motor we buy from it, the contract's delivery target, copper since the last price agreement
    "sister": dict(
        script={
            0: {
                "after": [
                    "We ordered your 4 kW motor at EUR 233.06 per unit in 2024-09 and at EUR 239.21 per unit in 2026-09 (po:4500011408-10, po:4500014464-10)."
                ]
            },
            1: {
                "after": [
                    "Our forecast fc:350010@2026-09 expects 8,490 units a year, a change of +7.6 %.",
                    "That is your 4 kW motor: our volume with Nordmark grows on both motors.",
                ]
            },
            2: {"after": ["Our framework agreement sets an on-time delivery target of 95 %."]},
            3: {
                "replace": True,
                "after": [
                    "The index CU-NOTATION changed +34.4 % from 2025-11 to 2026-09 (idx:CU-NOTATION@2025-11, idx:CU-NOTATION@2026-09).",
                    "That is the copper move since our current price was agreed, and it is smaller than the twelve-month figure in your offer.",
                ],
            },
        }
    ),
    # its own question, answered: "A binding higher volume would help us ... Which volume can you commit to?"
    "volume": dict(when=[(r"which volume can you commit", VOLUME)]),
    # the dossier's approval ladder: price changes above 2 % go to its pricing committee
    "committee": dict(
        script={0: {"before": [COMMITTEE]}},
        when=[
            (
                r"needs approval from our management",
                ["Please take this step to your management; we will wait for the decision."],
            )
        ],
    ),
    "control": dict(),
    # P18's supplier lowers its price 0.10 for every 30 days it is paid sooner (its own two-sheet answers); the dossier
    # reads it as relaxed about cash, so we ask 90 days
    "pay30": dict(structure={"payment_days": 30}, knobs=dict(plan="llm")),
    "pay14": dict(structure={"payment_days": 14}, knobs=dict(plan="llm")),
    # two facts in the first e-mail: suppliers that walk a ladder say final_offer after about four messages
    "agent-two": dict(knobs=dict(plan="llm", first_facts=2)),
    "agent-three": dict(knobs=dict(plan="llm", first_facts=3)),
    # Amiad's rule for a capacity-tight supplier, on this agent: the first ask no lower than 93 % of its opening
    "agent-nolow": dict(knobs=dict(plan="llm", no_lowball=0.93)),
    # the rules as built in: every fallen cost-driver index, one per e-mail (idx_many); the larger fall of an index
    # the supplier blames (idx_blamed, needs the planner)
    "agent-idx": dict(knobs=dict(plan="llm", idx_blamed=True, idx_many=3)),
    # a second cost-driver index that fell from its peak (the supplier's quote says it rose 12.3 % in twelve
    # months and is 38 % of its cost), in the second e-mail instead of the fact the supplier dismissed there
    "idx2": dict(
        script={
            1: {
                "replace": True,
                "after": [
                    "The index PPI-C2431 changed -2.3 % from 2026-06 to 2026-08 (idx:PPI-C2431@2026-06, idx:PPI-C2431@2026-08)."
                ],
            }
        }
    ),
    # eleven suppliers "offered to walk us through their calculation (hourly rates and material) if that helps to
    # settle prices" (call notes; P04, P08, P18 among them) - nobody ever asked
    "openbook": dict(
        script={
            0: {
                "after": [
                    "You offered to walk us through your calculation: could you send us your cost breakdown for this part (material, conversion, overhead)? That would help us to settle on a price that is fair for both sides."
                ]
            }
        }
    ),
    # P18 (leverage, two approved sources of the same bar): what the other source charges, instead of our own
    # order history with this one, which it dismissed
    "rival": dict(
        script={
            1: {
                "replace": True,
                "after": [
                    "We ordered the same part from our second source at EUR 5.45 per unit in 2026-08 and at EUR 5.45 per unit in 2026-09 (po:4500014305-10, po:4500014455-10)."
                ],
            }
        }
    ),
    # the clause again, at the price where our total cost is lowest (relationship term with its full cost
    # 367.56 as the arena charged it in two deals): asked at once, or after its own lower offer
    "clause5-direct": dict(
        structure=clause(5), hold=True, first_price=361.35, floor=361.35, script={0: {"after": [CLAUSE]}}
    ),
    # the rule as built into sellm/endgame.py (`clause_offer`): fixed-price ask and the clause at our price, two sheets
    "agent-clause": dict(knobs=dict(clause_offer=True)),
    "clause5-raise": dict(structure=clause(5), hold=True, floor=361.35, script={0: {"after": [CLAUSE]}}),
}
FAIR = "We do not want a price that leaves you below a sustainable margin: a healthy supplier matters more to us than the last euro."


class Probe(Persistent):
    """`--agent sellm` with a plan for what the e-mails argue; it computes no price itself."""

    def __init__(self, package=None, plan=None, **knobs):
        self.p = plan or {}
        super().__init__(package, **{**KNOBS, **(self.p.get("knobs") or {}), **knobs})

    def first(self, case, v):
        s = super().opening_structure(case, v)
        fix = self.p.get("structure")
        fix = fix(case) if callable(fix) else (fix or {})
        want = {**s, **{f: x for f, x in fix.items() if f in s}}
        if want != s and v.valid({**want, "unit_price": 1.0}):
            self._memo[(case.get("case_id"), v.sid, "s0")] = want
            return want
        return s

    def opening_structure(self, case, v):
        return self.first(case, v)

    def structure(self, case, v, s0):
        return s0 if self.p.get("hold") else super().structure(case, v, s0)

    def below(self, case, v):
        """Its standing offer is on our structure and under the price we do not want to go below."""
        floor = self.p.get("floor")
        terms = v.filled(v.standing[1]) if v.standing[0] else {}
        if not floor or terms.get("unit_price") is None or v.status != "open" or v.left <= 1:
            return False
        s = self.opening_structure(case, v)
        asked = sum(1 for a in v.asks if a.get("unit_price") == floor)
        return (
            {f: x for f, x in terms.items() if f != "unit_price"} == s
            and terms["unit_price"] < floor - 0.005
            and asked < 2
        )

    def ready(self, case, v, rival=math.inf):
        return False if self.below(case, v) else super().ready(case, v, rival)

    def plan(self, case, v, rival=math.inf):
        plan = super().plan(case, v, rival)
        first = self.p.get("first_price")
        if first and not v.asks:
            return {**plan, "sheet": complete_offer(case, {**plan["structure"], "unit_price": first})}
        if self.below(case, v):
            sheet = complete_offer(case, {**plan["structure"], "unit_price": self.p["floor"]})
            return {**plan, "sheet": sheet, "capped": False, "enough": False}
        return plan

    def ask(self, case, v, views, live, rival=math.inf):
        raise_it = self.below(case, v)
        draft = super().ask(case, v, views, live, rival)
        if draft.get("kind") != "ask":
            return draft
        if raise_it:
            return {**draft, "arguments": [FAIR]}
        step = (self.p.get("script") or {}).get(draft.get("n", len(v.asks))) or {}
        arguments = [] if step.get("replace") else list(draft.get("arguments") or [])
        arguments = [*step.get("before", []), *arguments, *step.get("after", [])]
        said = " ".join(m.get("body") or "" for m in v.ours)
        for pattern, sentences in self.p.get("when") or []:
            if re.search(pattern, v.last.get("body") or "", re.I) and sentences[0] not in said:
                arguments += sentences
        return {**draft, "arguments": arguments}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--variants", nargs="+", default=[])
    ap.add_argument("--case", default="P02")
    ap.add_argument("--list", action="store_true")
    ap.add_argument(
        "--dry", help="a saved session (JSON): print the e-mails each variant would send over it, no session"
    )
    args = ap.parse_args()
    if args.list:
        for name, plan in VARIANTS.items():
            print(
                name, json.dumps({k: (x if not callable(x) else "clause") for k, x in plan.items()}, default=str)[:300]
            )
        return
    from arena_kit.cli import load_env, pull_first

    load_env()
    from arena_kit.data import DataPackage

    package = DataPackage(os.environ.get("ARENA_DATA", "data/package"))
    package.lookup("")
    if args.dry:
        record = json.loads(Path(args.dry).read_text(encoding="utf-8"))
        case = record["case"]
        sid = case["suppliers"][0]
        messages = record["threads"][sid]["messages"]
        for name in args.variants:
            agent = Probe(package, plan=VARIANTS[name])
            print(f"=== {name}")
            for i, m in enumerate(messages):
                if m.get("from") == "buyer" or m.get("status") != "open":
                    continue
                decision = agent.decide(case, {sid: messages[: i + 1]})["message"]
                print([s["terms"] for s in decision.get("term_sheets") or []])
                print(decision.get("body"), "\n")
        return
    pull_first()  # never play on outdated code
    from arena_kit.client import ArenaClient

    spec = importlib.util.spec_from_file_location("ab_sandbox", ROOT / "experiments" / "ab_sandbox.py")
    ab = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ab)

    def git(*a):
        return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True).stdout.strip()

    commit = f"{git('branch', '--show-current')}@{git('rev-parse', '--short', 'HEAD')}"
    case_id = f"case:{args.case.split(':')[-1]}"
    lock = threading.Lock()

    def play(name):
        row = ab.play_case(ArenaClient(), case_id, Probe(package, plan=VARIANTS[name]))
        row.update(variant=name, label=f"ARG {name} {commit}")
        with lock:
            rows = json.loads(OUT.read_text(encoding="utf-8")) if OUT.is_file() else []
            rows.append(row)
            OUT.parent.mkdir(parents=True, exist_ok=True)
            OUT.write_text(json.dumps(rows, indent=1, default=str), encoding="utf-8")
            labels = json.loads(LABELS.read_text(encoding="utf-8")) if LABELS.is_file() else {}
            labels[row["session_id"]] = f"{args.case} ARG {name} {commit}"
            LABELS.write_text(json.dumps(labels, indent=1, sort_keys=True) + "\n", encoding="utf-8")
            for t in (row.get("threads") or {}).values():
                ours = [p[0] if p else None for p in t["our_prices"]]
                print(
                    f"{name:10s} score {row.get('score'):.3f} {row.get('end_reason')} {row.get('terms')} | theirs {t['their_prices']} ours {ours} claims {t['claims']} | {row['session_id']} {row.get('notes') or ''}",
                    flush=True,
                )
        return row

    with ThreadPoolExecutor(max_workers=max(1, len(args.variants))) as pool:
        list(pool.map(play, args.variants))


if __name__ == "__main__":
    main()
