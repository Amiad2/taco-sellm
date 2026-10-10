# ruff: noqa: E501  (prompt text)
"""Offline test: can the model tell a supplier's persona without our dossier?

For a supplier we hold no data on the agent has only the case text and what the supplier writes.
This script asks the model four yes/no questions per practice supplier - from the briefing and the
opening e-mail alone (v1), and with the supplier's next two e-mails added (v2) - and compares the
answers with what the dossier says (sellm/personas.py). The confidence is the probability of the
answer letter, read from the token probabilities. No arena session is opened.

    uv run python experiments/persona_reader.py        # about 100 short LLM calls
Results: experiments/results/2026-10-11-persona-reader.json, summary in experiments/PERSONA-READER.md.
"""

import glob
import json
import math
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

QUESTIONS = {
    "short_of_cash": "Is this supplier short of cash, so that being paid faster would be worth a lower price to it?",
    "fixed_list_price": "Is this supplier's price bound to a fixed list price or already close to its floor, so that it has little room to move on price?",
    "wants_volume": "Is this supplier hungry for volume or work, so that a bigger or longer commitment would be worth a lower price to it?",
    "approval_ladder": "Is the person writing part of a larger organisation where bigger price moves need the approval of someone else?",
}
SYSTEM = "You read e-mails from a supplier in a price negotiation and judge the supplier, not the buyer. Use only what the text shows. Answer with one letter only: A = yes, B = no."


def truth(dossier):
    from sellm.personas import traits

    personas = [p for p, _ in traits(dossier)]
    strength = {s.get("kind"): s.get("strength") or 0 for s in dossier.get("signals") or []}
    return {
        "short_of_cash": "short_of_cash" in personas,
        "fixed_list_price": "fixed_list_price" in personas,
        "wants_volume": strength.get("wants_volume", 0) >= 2,
        "approval_ladder": strength.get("approval_ladder", 0) >= 1,
    }


def ask(text, question):
    from sellm import llm

    answer, _, first, _ = llm.chat_tools(SYSTEM, f"{text}\n\nQuestion: {question}", None, {}, timeout_s=30.0)
    mass = {"A": 0.0, "B": 0.0}
    for t in first:
        letter = (t.get("token") or "").strip()[:1].upper()
        if letter in mass:
            mass[letter] += math.exp(t.get("logprob", -99.0))
    total = mass["A"] + mass["B"]
    return (mass["A"] / total) if total > 0 else (1.0 if answer.strip().upper().startswith("A") else 0.0)


def main():
    from arena_kit.cli import load_env

    load_env()
    os.environ.setdefault("SELLM_MODEL", "gpt-6-sol")
    from sellm.intel import dossier

    jobs, rows = [], []
    for case_dir in sorted(glob.glob(str(ROOT / "runs" / "practice" / "P*"))):
        files = [f for f in sorted(glob.glob(case_dir + "/*.json"))]
        records = [json.loads(Path(f).read_text(encoding="utf-8")) for f in files]
        records = [r for r in records if "past_target + fast_pay (no LLM)" in (r.get("label") or "")] or records
        rec = records[-1]
        case = rec["case"]
        for sid, thread in rec["threads"].items():
            theirs = [
                m for m in thread["messages"] if m.get("from") != "buyer" and m.get("body") and not m.get("action")
            ]
            head = f"Case: {case.get('title', '')}\n{case.get('briefing', '')}\n\nThe supplier's opening e-mail:\n---\n{theirs[0]['body'][:2500]}\n---"
            later = "".join(f"\n\nA later e-mail from the supplier:\n---\n{m['body'][:1800]}\n---" for m in theirs[1:3])
            want = truth(
                dossier(sid, case.get("parts") or [], case, {s: t["messages"][:1] for s, t in rec["threads"].items()})
            )
            for version, text in (("v1 opening only", head), ("v2 with its next two e-mails", head + later)):
                for key, question in QUESTIONS.items():
                    jobs.append((case["case_id"], sid, version, key, want[key], text, question))
    with ThreadPoolExecutor(max_workers=8) as pool:
        probs = list(pool.map(lambda j: ask(j[5], j[6]), jobs))
    for (case_id, sid, version, key, want, _, _), p in zip(jobs, probs, strict=True):
        rows.append(
            {
                "case": case_id,
                "supplier": sid,
                "version": version,
                "question": key,
                "dossier": want,
                "p_yes": round(p, 4),
            }
        )
    out = ROOT / "experiments" / "results" / "2026-10-11-persona-reader.json"
    out.write_text(json.dumps(rows, indent=1), encoding="utf-8")
    for version in ("v1 opening only", "v2 with its next two e-mails"):
        print(f"\n{version}")
        print(f"{'question':18s} {'right':>7s} {'wrong':>6s} {'wrong and sure (0.8+)':>22s} {'yes in dossier':>15s}")
        for key in QUESTIONS:
            sel = [r for r in rows if r["version"] == version and r["question"] == key]
            right = sum(1 for r in sel if (r["p_yes"] >= 0.5) == r["dossier"])
            sure = sum(1 for r in sel if (r["p_yes"] >= 0.5) != r["dossier"] and max(r["p_yes"], 1 - r["p_yes"]) >= 0.8)
            print(
                f"{key:18s} {right:>4d}/{len(sel):<2d} {len(sel) - right:>6d} {sure:>22d} {sum(1 for r in sel if r['dossier']):>15d}"
            )
        sel = [r for r in rows if r["version"] == version]
        right = sum(1 for r in sel if (r["p_yes"] >= 0.5) == r["dossier"])
        print(f"{'all':18s} {right:>4d}/{len(sel):<2d}")
    print("\nper supplier (v2): question dossier/model p(yes)")
    for sid in sorted({r["supplier"] for r in rows}):
        sel = [r for r in rows if r["supplier"] == sid and r["version"].startswith("v2")]
        print(
            f"  {sel[0]['case'][5:]} {sid[4:]}: "
            + "  ".join(f"{r['question']} {'Y' if r['dossier'] else 'n'}/{r['p_yes']:.2f}" for r in sel)
        )


if __name__ == "__main__":
    main()
