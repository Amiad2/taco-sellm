# ruff: noqa: E501  (prompt text)
"""The LLM reads the supplier before the first ask and says which terms it would give price for.

Code cannot read a letter. It knows what every option costs us (`sellm/calculator.py`), but not
which option is worth more to this supplier than it costs us - the trade the brief tells us to find.
In P02 that was the copper index clause: ten sessions on a fixed price ended at the supplier's cost
floor, the clause scored 0.725 against 0.531 (experiments/P02-ARGUMENTS.md). The dossier's rules
(`sellm/personas.py`) cover what we thought of in advance; this module is for what we did not.

One call per supplier, before our first e-mail (`plan`). The model gets the case, the options of
every negotiable field, the supplier's opening e-mail and what the dossier holds on it (letters,
notes, quote remarks, news, signals). It answers with at most two `wants` - a field, the option the
supplier would value, and the sentence of our material it rests on - and never with a number.

Code keeps the rest:
- a want is dropped unless its field and option exist in the case and its evidence is a passage of
  the material the model was given (no evidence, no trade);
- every offer built from a want is priced by code (`sellm/endgame.py`), never by the model;
- no answer within the time limit, or anything malformed: no plan, the agent plays as without one.

    uv run python -m sellm.planner P02 P01        the plan for played cases, from their saved openings
"""

import json
import re

from . import llm

SYSTEM = """You prepare a purchasing negotiation for the buyer, Hollerau Pumpenwerke. You read what we hold on ONE supplier and say which contract terms THIS supplier would give price for, so that code can put the right offer on the table. You never propose prices or figures: code prices every offer.

How suppliers in this world decide (the organiser's rules):
- A supplier never sells below its cost on a plain price, and it gives nothing without a move from the buyer.
- Some terms are worth more to a supplier than they cost the buyer. Being paid faster helps a supplier that is short of cash. A longer contract, a binding volume or an index clause on a raw material is security: with it the supplier no longer has to price that risk into the unit price. A later start date, a longer lead time or a relaxed quality term can free it from a cost.
- What weighs for a supplier is in its own letters, notes, quote remarks and news. Its stated reason for a price shows what it worries about. Some notes are noise; a general remark is no evidence.

Task: name at most TWO terms this supplier would value, strongest first. Only name a term if a passage of the material shows that the supplier itself cares about it; if nothing does, return no wants. For each, quote that passage word for word.

Answer with JSON only:
{"reason": "<its stated reason for its price, in a few words>",
 "wants": [{"field": "<one of the negotiable fields>", "option": "<the letter of the option it would value>", "evidence": "<a passage copied word for word from the material>", "because": "<one short sentence>"}],
 "note": "<one sentence: the trade to offer>"}"""

GOALS = {
    "stabilise": "strategic supply: a healthy supplier counts, squeezing it below a sustainable margin costs the buyer",
    "secure_supply": "bottleneck: supply security first, squeezing the supplier costs the buyer",
    "leverage": "competition: the lowest total cost",
    "routine": "low effort: the lowest total cost",
    "quality_first": "quality problem: quality terms and price",
}


def _show(value):
    if value is None:
        return "none"
    if isinstance(value, dict):
        return f"clause on {value.get('series')} (material share {round(100 * value.get('material_share', 0))} %, deadband {value.get('deadband_pct')} %)"
    return str(value)


def options(case, quoted):
    """{field: [(letter, value)]} for every negotiable field but the price; `quoted`: the supplier's own terms."""
    out = {}
    for field in case.get("negotiable", []):
        if field == "unit_price":
            continue
        values = list(case.get("term_options", {}).get(field) or [])
        if field in quoted and quoted[field] not in values:
            values.append(quoted[field])
        out[field] = [(chr(65 + i), v) for i, v in enumerate(values)]
    return out


def material(case, opening, dossier):
    """What the model reads, as text. Everything in it may be quoted as evidence."""
    d = dossier or {}
    lines = [f"ITS OPENING E-MAIL:\n{(opening or {}).get('body') or '(none)'}", ""]
    if d.get("profile_text"):
        lines += ["OUR PROFILE OF IT:", d["profile_text"], ""]
    signals = [f"- {s.get('kind')}: {s.get('excerpt')}" for s in d.get("signals") or [] if s.get("excerpt")]
    if signals:
        lines += ["SIGNALS OUR DATA TEAM FOUND:", *signals, ""]
    docs = [
        f'- {x.get("date")} {x.get("kind")} "{x.get("subject")}" ({x.get("author")}): {(x.get("text") or "").strip()}'
        for x in d.get("documents") or []
    ]
    if docs:
        lines += ["LETTERS, E-MAILS AND NOTES:", *docs[-10:], ""]
    remarks = [f"- quote of {q.get('date')}: {q.get('remarks')}" for q in d.get("own_quotes") or [] if q.get("remarks")]
    if remarks:
        lines += ["REMARKS ON ITS QUOTES:", *remarks, ""]
    news = [f"- {n.get('date')} {n.get('headline')}: {n.get('body')}" for n in d.get("news") or []]
    if news:
        lines += ["NEWS ABOUT IT:", *news[-6:], ""]
    eco = d.get("economics") or {}
    if eco:
        lines += [
            f"MONEY: cash pressure {eco.get('cash_pressure')}; cost of money {eco.get('cost_of_money')} ({eco.get('cost_of_money_basis')}); we are {eco.get('our_share_of_turnover_pct')} % of its turnover.",
            "",
        ]
    return "\n".join(lines)[:9000]


def brief(case, opening, dossier, quoted):
    b = case["buyer"]
    lines = [
        f"CASE: {case.get('title', '')} ({case.get('type')}; goal {b.get('category_goal')} = {GOALS.get(b.get('category_goal'), '')}).",
        (case.get("briefing") or "")[:700],
        "",
        "NEGOTIABLE TERMS AND THEIR OPTIONS (the supplier's own quote is marked):",
    ]
    for field, values in options(case, quoted).items():
        shown = ", ".join(
            f"{letter} = {_show(v)}{' (its quote)' if quoted.get(field) == v else ''}" for letter, v in values
        )
        lines.append(f"- {field}: {shown}")
    lines += ["- unit_price: priced by code, not your task", "", material(case, opening, dossier)]
    return "\n".join(lines)


def _norm(text):
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


def check(answer, case, quoted, text):
    """The model's answer as a plan code may use: every want has a real field, a real option and
    evidence that stands in the material. Returns {"reason", "note", "wants": [...], "dropped": [...]}."""
    opts, flat = options(case, quoted), _norm(text)
    wants, dropped = [], []
    for w in (answer.get("wants") or [])[:2]:
        if not isinstance(w, dict):
            continue
        field, letter = w.get("field"), str(w.get("option") or "").strip().upper()[:1]
        value = next((v for k, v in opts.get(field, []) if k == letter), "?")
        evidence = _norm(w.get("evidence"))
        grounded = len(evidence) >= 12 and (
            evidence in flat or all(part in flat for part in re.split(r" \.\.\. | … ", evidence) if len(part) >= 12)
        )
        if field not in opts or value == "?":
            dropped.append({**w, "why": "no such field or option"})
        elif not grounded:
            dropped.append({**w, "why": "evidence is not in the material"})
        elif field in quoted and quoted[field] == value:
            dropped.append({**w, "why": "that is what it quotes already"})
        else:
            wants.append(
                {
                    "field": field,
                    "value": value,
                    "evidence": str(w.get("evidence"))[:300],
                    "because": str(w.get("because") or "")[:200],
                }
            )
    return {
        "reason": str(answer.get("reason") or "")[:120],
        "note": str(answer.get("note") or "")[:300],
        "wants": wants,
        "dropped": dropped,
    }


def plan(case, opening, dossier, quoted, timeout_s=25.0):
    """The checked plan, with "seconds"; raises llm.LLMError when there is no usable answer in time."""
    user = brief(case, opening, dossier, quoted)
    answer, took = llm.chat_json(SYSTEM, user, timeout_s=timeout_s)
    return {**check(answer, case, quoted, user), "seconds": round(took, 2)}


def direction(field, value, quoted):
    """What a want changes against the supplier's own quote: a clause or none, sooner/less or later/more."""
    if field == "index_clause":
        return "clause" if value else "none"
    its = quoted.get(field)
    try:
        return "lower" if value < its else "higher"
    except TypeError:
        return repr(value)


def voted(case, opening, dossier, quoted, votes=3, need=2, timeout_s=12.0):
    """{field: {"direction", "value", "evidence", "votes"}}: the wants named in at least `need` of
    `votes` calls made at once. The confidence is counted, not asked for. A plan is kept on disk
    per case, supplier and material (runs/logs/plans/), so a resumed or repeated session plays the
    same moves. Never raises: no usable answer in `timeout_s` is an empty plan."""
    import hashlib
    import os
    import time
    from concurrent.futures import ThreadPoolExecutor, wait
    from pathlib import Path

    user = brief(case, opening, dossier, quoted)
    name = hashlib.sha256((SYSTEM + user + llm.model()).encode()).hexdigest()[:16]
    sid = str((dossier or {}).get("supplier_id") or "supplier").split(":")[-1]
    folder = Path(os.environ.get("SELLM_PLANS") or Path(__file__).resolve().parents[1] / "runs" / "logs" / "plans")
    path = folder / f"{str(case.get('case_id')).split(':')[-1]}-{sid}-{name}.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))["wants"]
    except (OSError, ValueError, KeyError):
        pass
    t0 = time.monotonic()
    pool = ThreadPoolExecutor(max_workers=votes)
    futures = [pool.submit(llm.chat_json, SYSTEM, user, timeout_s) for _ in range(votes)]
    wait(futures, timeout=timeout_s)
    pool.shutdown(wait=False)
    plans = []
    for f in futures:
        if f.done() and not f.exception():
            plans.append(check(f.result()[0], case, quoted, user))
    count, out = {}, {}
    for p in plans:
        for w in p["wants"]:
            key = (w["field"], direction(w["field"], w["value"], quoted))
            count.setdefault(key, []).append(w)
    for (field, way), found in count.items():
        if len(found) >= need and field not in out:
            out[field] = {
                "direction": way,
                "value": found[0]["value"],
                "evidence": found[0]["evidence"],
                "votes": len(found),
            }
    record = {
        "case": case.get("case_id"),
        "supplier": sid,
        "answers": len(plans),
        "seconds": round(time.monotonic() - t0, 2),
        "wants": out,
        "plans": plans,
    }
    if plans:  # an outage is not a plan: ask again next time
        try:
            folder.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(record, indent=1, default=str), encoding="utf-8")
        except OSError:
            pass
    return out


def main(argv=None):
    import glob
    import os
    import sys

    from arena_kit.cli import load_env

    from .intel import dossier
    from .negotiator import Thread

    load_env()
    for name in sys.argv[1:] if argv is None else argv:
        files = sorted(glob.glob(f"runs/*/{name.split(':')[-1]}/*.json"))
        if not files:
            print(f"{name}: no saved session in runs/")
            continue
        record = json.loads(open(files[-1], encoding="utf-8").read())
        case = record["case"]
        openings = {s: t["messages"][:1] for s, t in record["threads"].items()}
        for sid, events in openings.items():
            view = Thread(case, sid, events)
            quoted = view.filled(view.opening["term_sheets"][0]["terms"])
            found = dossier(sid, case.get("parts") or [], case, openings)
            if os.environ.get("SELLM_PLAN_SHOW") == "brief":
                print(brief(case, events[0], found, quoted))
            try:
                print(
                    case["case_id"], sid, json.dumps(plan(case, events[0], found, quoted), ensure_ascii=False, indent=1)
                )
            except llm.LLMError as e:
                print(case["case_id"], sid, "no plan:", e)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
