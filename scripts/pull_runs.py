# ruff: noqa: E501  (long f-strings that build markdown table rows)
"""Pull every session the team has played (practice and sandbox) from the arena into runs/.

The arena keeps all sessions of our key, whoever played them. This script saves each ended session
in full - case file, every e-mail both ways, attachment texts, the supplier's reasons (trace), the
back office, the result and its cost breakdown - plus an offline analysis of where the deal lost
against C_best, and rebuilds the index runs/README.md. It reads only our own cases and sessions.

    scripts/pull-runs                          # fetch sessions not yet in runs/
    scripts/pull-runs --label "kit-llm gpt-x"  # ... and label the new ones (which agent played)
    scripts/pull-runs --force                  # fetch everything again
"""

import argparse
import itertools
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from arena_kit.cli import load_env, pull_first  # noqa: E402
from arena_kit.client import ArenaClient, ArenaError  # noqa: E402
from arena_kit.cost import RELATIONSHIP_GOALS, must_haves_ok, total_cost  # noqa: E402
from arena_kit.docs import quote_terms, read_document  # noqa: E402

RUNS = ROOT / "runs"
LABELS = RUNS / "labels.json"
SETS = ("practice", "sandbox")
TZ = ZoneInfo("Europe/Berlin")
MAX_COMBOS = 50_000
BREAKDOWN = (
    "price",
    "uncovered_need",
    "fallback_risk",
    "payment_terms",
    "freight",
    "late_delivery",
    "quality",
    "tooling",
    "index_clause",
    "index_risk",
    "relationship",
)


def when(created_at):
    return datetime.fromtimestamp(float(created_at), TZ)


def eur(x):
    return "-" if x is None else f"{x:,.0f}"


def short(value):
    """A term value for a table cell."""
    if isinstance(value, dict):
        return f"{value.get('series')} {round(100 * value.get('material_share', 0))}% db{value.get('deadband_pct')}"
    return "none" if value is None else str(value)


def terms_line(case, terms):
    """The negotiable fields of a term sheet in one line, price first."""
    order = ["unit_price"] + [f for f in case["negotiable"] if f != "unit_price"]
    return ", ".join(f"{f}={short(terms.get(f))}" for f in order if f in terms)


def fetch(client, row, case, label):
    """One session in full, with attachment texts and the back office."""
    sid = row["session_id"]
    state = client.session(sid)
    threads = {}
    for supplier in state.get("threads", {}):
        thread = client.thread(sid, supplier)
        for message in thread.get("messages", []):
            for att in message.get("attachments") or []:
                if att.get("attachment_id"):
                    try:
                        att["text"] = read_document(att["name"], client.attachment(sid, att["attachment_id"]))
                    except Exception as e:  # a document we cannot read must not lose the session
                        att["text_error"] = str(e)
                att.pop("content_b64", None)
        threads[supplier] = thread
    try:
        backoffice = client.backoffice(sid)
    except ArenaError as e:
        backoffice = [{"error": str(e)}]
    replay = state.get("replay_url")
    record = {
        "session_id": sid,
        "case_id": row["case_id"],
        "set": state.get("set"),
        "created_at": when(row["created_at"]).isoformat(timespec="seconds"),
        "label": label,
        "replay": os.environ["ARENA_URL"].rstrip("/") + replay if replay else None,
        "case": case,
        "state": state,
        "threads": threads,
        "backoffice": backoffice,
    }
    record["analysis"] = analyse(record)
    return record


def standard_of(thread):
    """The supplier's standard terms from its latest quote PDF (what closes when a field is left out)."""
    for message in reversed(thread.get("messages", [])):
        for att in message.get("attachments") or []:
            if att.get("name", "").startswith("quote") and att.get("text"):
                return quote_terms(att["text"]).get("standard", {})
    return {}


def analyse(record):
    """Offline: what each lever was worth at the deal, and how the gap to C_best splits into
    structure (terms other than price) and price. Uses the kit's cost function without a supplier
    estimate, so the relationship term is taken from the arena's breakdown, not recomputed."""
    case, result = record["case"], record["state"].get("result") or {}
    out = {"openings": {}}
    for supplier, thread in record["threads"].items():
        first = next((m for m in thread.get("messages", []) if m.get("from") != "buyer"), None)
        sheets = (first or {}).get("term_sheets") or []
        if sheets:
            std = standard_of(thread)
            out["openings"][supplier] = {
                "terms": sheets[0]["terms"],
                "standard_terms": std,
                "c": total_cost(case, sheets[0]["terms"], std),
                "must_haves_ok": must_haves_ok(case, sheets[0]["terms"], std),
            }
    if not result.get("deal") or not result.get("terms"):
        return out
    deal = result["terms"]
    relationship = (result.get("cost_breakdown") or {}).get("relationship", 0.0)
    c_offline = total_cost(case, deal)
    out["c_deal_offline_without_relationship"] = c_offline
    out["relationship_charged_by_arena"] = relationship
    options = {
        f: case.get("term_options", {}).get(f)
        for f in case["negotiable"]
        if f != "unit_price" and case.get("term_options", {}).get(f)
    }
    out["levers"] = {
        f: [
            {
                "value": o,
                "c": total_cost(case, {**deal, f: o}),
                "delta_vs_deal": round(total_cost(case, {**deal, f: o}) - c_offline, 2),
                "must_haves_ok": must_haves_ok(case, {**deal, f: o}),
                "chosen": o == deal.get(f),
            }
            for o in opts
        ]
        for f, opts in options.items()
    }
    combos = 1
    for opts in options.values():
        combos *= len(opts)
    if not options or combos > MAX_COMBOS:
        return out
    best = None
    for values in itertools.product(*options.values()):
        sheet = {**deal, **dict(zip(options, values, strict=True))}
        if must_haves_ok(case, sheet):
            c = total_cost(case, sheet)
            if best is None or c < best[0]:
                best = (c, sheet)
    if best is None:
        return out
    c_best_structure, sheet = best
    out["best_structure_at_deal_price"] = {
        "terms": {f: sheet[f] for f in case["negotiable"]},
        "c": c_best_structure,
    }
    c_deal, c_best = result.get("c_deal"), result.get("c_best")
    out["gap_to_c_best"] = round(c_deal - c_best, 2)
    out["gap_structure"] = round(c_offline - c_best_structure, 2)  # same price, better other terms
    out["gap_rest"] = round(out["gap_to_c_best"] - out["gap_structure"], 2)  # price and relationship
    # C is linear in the price when the relationship term is left out: the price that would reach
    # C_best with the best structure. In stabilise and secure_supply cases the real one is higher.
    p = deal["unit_price"]
    slope = total_cost(case, {**sheet, "unit_price": p + 1}) - c_best_structure
    if slope > 0:
        out["price_for_c_best_with_best_structure"] = round(p - (c_best_structure - c_best) / slope, 2)
        out["price_note"] = (
            "relationship term not included: the real price at C_best is higher"
            if case["buyer"].get("category_goal") in RELATIONSHIP_GOALS
            else "no relationship term in this category goal"
        )
    return out


def transcript(record):
    """The session as a readable page."""
    case, state, a = record["case"], record["state"], record["analysis"]
    result, buyer = state.get("result") or {}, record["case"]["buyer"]
    out = [f"# {record['case_id']} - {case.get('title', '')}", ""]
    out += [
        f"- **Session** `{record['session_id']}` ({record['set']}), {record['created_at']}",
        f"- **Agent** {record['label'] or 'unlabelled'}",
        f"- **Replay** {record['replay']}",
        f"- **Type / goal** {case.get('type')} / {buyer.get('category_goal')}",
        f"- **Suppliers** {', '.join(case['suppliers'])} · **parts** {', '.join(case.get('parts', []))}",
        f"- **Negotiable** {', '.join(case['negotiable'])}",
        f"- **Must-haves** {json.dumps(buyer.get('must_haves', []))}",
        f"- **Ended** {state.get('end_reason')} after {state.get('rounds')} rounds",
        "",
        "## Result",
        "",
    ]
    score = result.get("score")
    out.append(f"**Score {score:.3f}**" if score is not None else "**No score**")
    out.append("")
    out.append("| C_open | C_deal | C_best | C_alt | Deal | Must-haves ok |")
    out.append("|---|---|---|---|---|---|")
    out.append(
        f"| {eur(result.get('c_open'))} | {eur(result.get('c_deal'))} | {eur(result.get('c_best'))} "
        f"| {eur(result.get('c_alt'))} | {result.get('deal')} | {result.get('must_haves_ok')} |"
    )
    if result.get("terms"):
        out += ["", f"Closed with `{result.get('supplier_id')}` on: `{json.dumps(result['terms'], ensure_ascii=False)}`"]
    if result.get("cost_breakdown"):
        out += ["", "| Part of C | EUR |", "|---|---|"]
        out += [f"| {k} | {eur(result['cost_breakdown'].get(k))} |" for k in BREAKDOWN]
    out += ["", "## Where the deal lost (offline analysis)", ""]
    if "gap_to_c_best" in a:
        out += [
            f"- Gap to C_best: **{eur(a['gap_to_c_best'])}**. Better non-price terms at the deal's price could "
            f"have saved up to **{eur(a['gap_structure'])}** (if the supplier accepted them); the rest, "
            f"**{eur(a['gap_rest'])}**, is price and relationship. A negative rest means the supplier would "
            f"not give all of those terms at this price.",
            f"- Best other terms at the deal price: `{json.dumps(a['best_structure_at_deal_price']['terms'], ensure_ascii=False)}` "
            f"-> C {eur(a['best_structure_at_deal_price']['c'])}",
        ]
        if "price_for_c_best_with_best_structure" in a:
            out.append(
                f"- Price that reaches C_best with those terms: **{a['price_for_c_best_with_best_structure']}** "
                f"({a['price_note']})."
            )
        out.append(f"- Relationship charged by the arena: {eur(a.get('relationship_charged_by_arena'))}.")
    else:
        out.append("- No deal, or no options to compare.")
    for field, rows in (a.get("levers") or {}).items():
        out += ["", f"Lever `{field}` (other deal terms unchanged):", "", "| Value | C | vs deal | Must-haves |", "|---|---|---|---|"]
        for r in rows:
            mark = " **(deal)**" if r["chosen"] else ""
            out.append(f"| {short(r['value'])}{mark} | {eur(r['c'])} | {r['delta_vs_deal']:+,.0f} | {'ok' if r['must_haves_ok'] else 'BROKEN'} |")
    out += ["", "## Openings", "", "| Supplier | Opening terms | C | Standard terms (quote PDF) |", "|---|---|---|---|"]
    for supplier, o in a["openings"].items():
        out.append(f"| {supplier} | {terms_line(case, o['terms'])} | {eur(o['c'])} | `{json.dumps(o['standard_terms'], ensure_ascii=False)}` |")
    reasons = {}
    for t in result.get("trace") or []:
        if t.get("reasons"):
            reasons.setdefault((t["actor"], t["round"]), []).extend(t["reasons"])
    for supplier, thread in record["threads"].items():
        out += ["", f"## Thread {supplier}", "", f"Status `{thread.get('status')}`, closed: `{thread.get('closed')}`, timeouts: {len(thread.get('timeouts') or [])}"]
        rounds = 0
        for m in thread.get("messages", []):
            mine = m.get("from") == "buyer"
            rounds += mine
            head = f"### {'Buyer (us)' if mine else m.get('from_name') or m.get('from')} - round {rounds}"
            out += ["", head, ""]
            if m.get("action"):
                out.append(f"Action: `{json.dumps(m['action'])}`")
            if m.get("status"):
                out.append(f"Status: `{m['status']}`")
            for sheet in m.get("term_sheets") or []:
                tid = f" `{sheet['term_sheet_id']}`" if sheet.get("term_sheet_id") else ""
                c = total_cost(case, sheet["terms"], a["openings"].get(supplier, {}).get("standard_terms"))
                out.append(f"- Term sheet{tid}: {terms_line(case, sheet['terms'])} -> C {eur(c)}")
            if m.get("claim_results"):
                out.append(f"- Claim results: `{json.dumps(m['claim_results'])}`")
            if m.get("refs"):
                out.append(f"- Refs: {', '.join(m['refs'])}")
            if m.get("missing_fields"):
                out.append(f"- Missing fields (close on standard terms): {', '.join(m['missing_fields'])}")
            if m.get("signals"):
                out.append(f"- Signals: `{json.dumps(m['signals'])}`")
            if m.get("subject"):
                out.append(f"- Subject: {m['subject']}")
            if m.get("body"):
                out += ["", "```text", m["body"].strip(), "```"]
            if not mine and reasons.get((supplier, rounds)):
                out += ["", "Supplier's reasons (trace):"] + [f"- {r}" for r in reasons[(supplier, rounds)]]
            for att in m.get("attachments") or []:
                out += ["", f"Attachment `{att.get('name')}`:", "", "```text", (att.get("text") or att.get("text_error") or "").strip()[:4000], "```"]
        for late in thread.get("timeouts") or []:
            out += ["", f"Timeout: `{json.dumps(late, ensure_ascii=False)[:600]}`"]
    lines = [b for b in record["backoffice"] if b.get("text")]
    if lines:
        out += ["", "## Back office", ""]
        out += [f"- round {b.get('round')} · {b.get('supplier_id')} · {b.get('from')} -> {b.get('to')}: {b['text']}" for b in lines]
    return "\n".join(out) + "\n"


def index(records):
    """runs/README.md: what we know per case, then every session."""
    out = [
        "# runs - every session the team has played",
        "",
        "Generated by `scripts/pull-runs`; do not edit by hand. Each session has a `.md` (readable:",
        "all e-mails, the supplier's reasons, the cost breakdown, where the deal lost) and a `.json`",
        "(everything the arena returned, plus the case file and the analysis). Session logs of full",
        "runs are in `runs/logs/`.",
        "",
        "## Per case: the yardstick and our best",
        "",
        "`C_open` and `C_best` are fixed per case, so any term sheet can be scored offline:",
        "`score = (C_open - C) / (C_open - C_best)` with `arena_kit.total_cost`.",
        "",
        "| Case | Type / goal | C_open | C_best | C_alt | Best score | By | Sessions |",
        "|---|---|---|---|---|---|---|---|",
    ]
    by_case = {}
    for r in records:
        by_case.setdefault((r["set"], r["case_id"]), []).append(r)
    practice_best = []
    for (set_, case_id), rs in sorted(by_case.items()):
        res = [(r["state"].get("result") or {}) for r in rs]
        top = max(rs, key=lambda r: (r["state"].get("result") or {}).get("score") or 0)
        top_res = top["state"].get("result") or {}
        known = next((x for x in res if x.get("c_best") is not None), {})
        b = rs[0]["case"]["buyer"]
        out.append(
            f"| {case_id.split(':')[1]} ({set_}) | {rs[0]['case'].get('type')} / {b.get('category_goal')} "
            f"| {eur(known.get('c_open'))} | {eur(known.get('c_best'))} | {eur(known.get('c_alt'))} "
            f"| {top_res.get('score') or 0:.3f} | {top['label'] or '?'} | {len(rs)} |"
        )
        if set_ == "practice":
            practice_best.append(top_res.get("score") or 0)
    if practice_best:
        out += ["", f"Mean of our best per practice case played: {100 * sum(practice_best) / len(practice_best):.1f} ({len(practice_best)} cases)."]
    out += [
        "",
        "## Every session",
        "",
        "Gap = C_deal - C_best. Structure = the most that better non-price terms could have saved at",
        "the deal's price, if the supplier had accepted them. Rest = gap minus structure: what is left",
        "for price and the relationship term. A negative rest means the best non-price terms at this",
        "price would beat C_best, so the supplier would not give all of them at this price.",
        "",
        "| Case | When | Agent | Score | End | Rounds | Deal terms | Gap | Structure | Rest | Files |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in sorted(records, key=lambda r: (r["set"], r["case_id"], r["created_at"])):
        res, a = r["state"].get("result") or {}, r["analysis"]
        rel = Path(r["_path"]).relative_to(RUNS).as_posix()
        terms = terms_line(r["case"], res["terms"]) if res.get("terms") else "-"
        score = f"{res['score']:.3f}" if res.get("score") is not None else "-"
        out.append(
            f"| {r['case_id'].split(':')[1]} | {r['created_at'][5:16].replace('T', ' ')} | {r['label'] or '?'} | {score} "
            f"| {r['state'].get('end_reason')} | {r['state'].get('rounds')} | {terms} "
            f"| {eur(a.get('gap_to_c_best'))} | {eur(a.get('gap_structure'))} | {eur(a.get('gap_rest'))} "
            f"| [md]({rel}.md) · [json]({rel}.json) · [replay]({r['replay']}) |"
        )
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--label", help="which agent played the sessions that have no label yet")
    ap.add_argument("--force", action="store_true", help="fetch every session again")
    args = ap.parse_args()
    os.chdir(ROOT)
    load_env()
    pull_first()  # runs/ is shared: write on top of the team's latest state
    client = ArenaClient()
    labels = json.loads(LABELS.read_text(encoding="utf-8")) if LABELS.is_file() else {}
    records, new = [], 0
    for set_ in SETS:
        rows = client.sessions(set_)
        rows = rows if isinstance(rows, list) else rows.get("sessions", [])
        cases = {c["case_id"]: c for c in client.cases(set_)}
        for row in rows:
            sid = row["session_id"]
            stamp = when(row["created_at"]).strftime("%Y%m%d-%H%M%S")
            base = RUNS / set_ / row["case_id"].split(":")[1] / f"{stamp}-{sid}"
            path = base.with_name(base.name + ".json")
            if row.get("status") != "ended":
                print(f"skip {sid} ({row['case_id']}): still {row.get('status')}")
                continue
            if sid not in labels and args.label:
                labels[sid] = args.label
            if path.is_file() and not args.force:
                record = json.loads(path.read_text(encoding="utf-8"))
                if record.get("label") != labels.get(sid):
                    record["label"] = labels.get(sid)
            else:
                record = fetch(client, row, cases.get(row["case_id"]), labels.get(sid))
                new += 1
                print(f"pulled {row['case_id']} {sid} score={row.get('score')}")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(record, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
            base.with_name(base.name + ".md").write_text(transcript(record), encoding="utf-8")
            records.append({**record, "_path": str(base)})
    LABELS.write_text(json.dumps(labels, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    (RUNS / "README.md").write_text(index(records), encoding="utf-8")
    print(f"{new} new session(s), {len(records)} in runs/. Index: runs/README.md")


if __name__ == "__main__":
    main()
