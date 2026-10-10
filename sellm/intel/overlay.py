"""The case overlay: what a case and its opening e-mails add to a dossier; for a stranger it is the dossier."""

import copy
import json
import re
from functools import lru_cache

from arena_kit.docs import quote_terms, standard_terms

from . import assemble, derive, render, signals
from .build import DOSSIERS, citable_hook
from .extract import number
from .schema import STANDARD_TERMS_KEYS, empty_dossier, empty_part

CASE_DATE = "case"  # sorts after every ISO date: the case's texts are the newest evidence
VALIDITY = re.compile(r"Validity:\s*(\d+)\s*days", re.I)
LEGAL_FORM = re.compile(r"\s+(GmbH.*|e\.K\.|KG|AG|s\.r\.o\.|a\.s\.|Kft\.|Sp\. z o\.o\.|Co\., Ltd\.|Ltd\.?)$")


@lru_cache(maxsize=256)
def _stored(sid):
    path = DOSSIERS / f"{number(sid)}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def stored(sid):
    d = _stored(sid)
    return copy.deepcopy(d) if d else None


def alias(src, sid):
    """A blocked vendor record whose company lives on under a detailed record with the same name."""
    if src is None:
        return sid, None
    row = src.supplier(sid)
    if not row or not row.get("blocked"):
        return sid, None
    stem = LEGAL_FORM.sub("", row.get("name") or "").strip()
    for other in src.q("SELECT id, name FROM suppliers WHERE detail = 'full' AND blocked = 0 ORDER BY id"):
        if stem and LEGAL_FORM.sub("", other["name"]).strip() == stem:
            return other["id"], f"{sid} is the old, blocked record of {other['id']}"
    return sid, None


def case_facts(case):
    facts = (case or {}).get("facts") or {}
    if isinstance(facts, list):
        facts = {
            f["id"]: {k: v for k, v in f.items() if k != "id"} for f in facts if isinstance(f, dict) and f.get("id")
        }
    return facts if isinstance(facts, dict) else {}


def thread(opening, sid):
    """This supplier's messages, from a threads dict (list or {"messages": [...]}) or a plain list."""
    if isinstance(opening, dict):
        opening = opening.get(sid)
    if isinstance(opening, dict):
        opening = opening.get("messages")
    return [m for m in opening if isinstance(m, dict)] if isinstance(opening, list) else []


def first_supplier_message(messages):
    return next((m for m in messages if m.get("from") != "buyer" and m.get("from_name") != "buyer"), None)


def contact(msg):
    role, _, company = (msg.get("from_name") or "").partition(",")
    lines = [line.strip() for line in (msg.get("body") or "").splitlines()]
    name = None
    for i, line in enumerate(lines):
        if role and line.startswith(role.strip() + ","):
            name = next((x for x in reversed(lines[:i]) if x), None)
    return {"name": name, "role": role.strip() or None, "company": company.strip() or None, "address": msg.get("from")}


def quote_text(msg):
    return next(
        (a.get("text") for a in msg.get("attachments") or [] if (a.get("name") or "").startswith("quote")), None
    )


def stated_drivers(body, series):
    out = []
    for m in signals.DRIVER_CLAIM.finditer(body or ""):
        stated = float(m["chg"]) * (-1 if m["dir"].lower() == "fell" else 1)
        true, ids = derive.window(series.get(m["series"], {}), 12)
        out.append(
            {
                "series": m["series"],
                "direction": m["dir"].lower(),
                "stated_change_pct": stated,
                "cost_share_pct": float(m["share"]),
                "true_change_12m_pct": true,
                "ids_12m": ids,
                "matches": None if true is None else abs(stated - true) <= 0.5,
            }
        )
    return out


def _series(src, facts):
    series = {s: dict(points) for s, points in (src.series if src else {}).items()}
    for ref, f in facts.items():
        if ref.startswith("idx:") and isinstance(f, dict) and f.get("series") and f.get("month"):
            series.setdefault(f["series"], {})[f["month"]] = (f.get("value"), ref)
    return series


def _apply_cost_facts(d, facts, sid):
    for ref, f in sorted(facts.items()):
        if not (ref.startswith("cost:") and isinstance(f, dict) and f.get("unit_cost") is not None):
            continue
        if f.get("supplier") not in (None, sid) or f.get("part") not in d["parts"]:
            continue
        part = d["parts"][f["part"]]
        sc = {
            "id": ref,
            "unit_cost": derive.r(f["unit_cost"], 2),
            "price_unit": int(f.get("price_unit") or part["price_unit"] or 1),
            "plant_specific": f.get("supplier") == sid,
            "cost_base": f.get("cost_base"),
            "confidence_pct": f.get("confidence_pct"),
            "material_eur": None,
            "conversion_eur": None,
            "overhead_eur": None,
        }
        if sc["plant_specific"] or not (part["should_cost"] or {}).get("plant_specific"):
            part["should_cost"] = sc
            part["floor_estimate"] = derive.floor_estimate(sc, d["identity"].get("country"), part["price_unit"])
            part["price_to_should_cost"] = derive.price_to_should_cost(part["current_price"], sc)


def _case_texts(d, case, facts, src):
    """Extra signal sources from the case: briefing, trigger document, documents and news among its facts."""
    sid, extra = d["supplier_id"], []
    if case.get("briefing"):
        extra.append((f"{case.get('case_id') or 'case'}#briefing", CASE_DATE, "", str(case["briefing"])))
    known = {x["id"] for x in d["documents"]}
    trigger = case.get("trigger_doc")
    if isinstance(trigger, str) and trigger not in known:
        text = None
        if src is not None:
            try:
                text = src.pkg.document(trigger)
            except (FileNotFoundError, OSError, ValueError):
                text = None
        fact = facts.get(trigger) or {}
        text = text or fact.get("text") or fact.get("body") or fact.get("title")
        if text and fact.get("supplier") in (None, sid):
            extra.append((trigger, CASE_DATE, fact.get("title") or "", text))
    for ref, f in sorted(facts.items()):
        if not isinstance(f, dict) or f.get("supplier") != sid:
            continue
        if ref.startswith("doc:") and ref not in known:
            d["documents"].append(
                {
                    "id": ref,
                    "date": f.get("date"),
                    "kind": f.get("type"),
                    "subject": f.get("title"),
                    "author": None,
                    "part_ids": [],
                    "asked_pct": f.get("asked_pct"),
                    "asked_price": f.get("asked_price"),
                    "effective_date": f.get("effective_date"),
                    "notice_days": f.get("days"),
                    "text": f.get("text") or f.get("body") or "",
                }
            )
        if ref.startswith("news:") and ref not in {n["id"] for n in d["news"]}:
            topic = f.get("topic")
            d["news"].append(
                {
                    "id": ref,
                    "date": f.get("date"),
                    "topic": topic,
                    "headline": f.get("headline") or f.get("title"),
                    "body": f.get("body") or f.get("text"),
                    "source": f.get("source"),
                    "noise": topic == "noise",
                }
            )
    d["documents"].sort(key=lambda x: (x["date"] or "", x["id"]))
    d["news"].sort(key=lambda x: (x["date"] or "", x["id"]))
    return extra


def _alternatives(d, case, opening, facts, sid, src):
    alt = (case.get("buyer") or {}).get("alternative") or {}
    extra = []
    if alt.get("kind") == "quote":
        fact = facts.get(alt.get("ref")) or (src.facts.get(alt.get("ref")) if src is not None else None) or {}
        owner = fact.get("supplier")
        if owner != sid:
            extra.append(
                {
                    "supplier_id": owner,
                    "kind": "buyer_alternative",
                    "quote_id": alt.get("ref"),
                    "unit_price": (alt.get("terms") or {}).get("unit_price") or fact.get("unit_price"),
                    "terms": alt.get("terms"),
                    "private": True,
                }
            )
    elif alt.get("kind") == "current_contract":
        extra.append(
            {
                "supplier_id": None,
                "kind": "current_contract",
                "unit_price": (alt.get("terms") or {}).get("unit_price"),
                "terms": alt.get("terms"),
                "private": True,
            }
        )
    for other in case.get("suppliers") or []:
        if other == sid:
            continue
        msg = first_supplier_message(thread(opening, other))
        sheets = (msg or {}).get("term_sheets") or []
        if sheets:
            extra.append(
                {
                    "supplier_id": other,
                    "kind": "rfq_rival",
                    "offer_id": sheets[0].get("term_sheet_id"),
                    "unit_price": (sheets[0].get("terms") or {}).get("unit_price"),
                    "private": True,
                }
            )
    for part in d["parts"].values():
        for x in extra:
            same = [a for a in part["alternatives"] if x.get("quote_id") and a.get("quote_id") == x["quote_id"]]
            if same:
                same[0].update(kind=x["kind"], terms=x.get("terms"))
            else:
                part["alternatives"].append(dict(x))


def _apply_opening(d, msg, series):
    extra = []
    text = quote_text(msg) or ""
    std = standard_terms([msg])
    if std:
        st = d["standard_terms"]
        for k in STANDARD_TERMS_KEYS:
            if k in std and k != "source":
                st[k] = std[k]
        st["source"] = "quote_pdf"
    sections = quote_terms(text) if text else {}
    sheets = msg.get("term_sheets") or []
    validity = (msg.get("signals") or {}).get("validity_days")
    if validity is None and (m := VALIDITY.search(text)):
        validity = int(m.group(1))
    d["opening_offer"] = {
        "offer_id": sheets[0].get("term_sheet_id") if sheets else None,
        "terms": (sheets[0].get("terms") if sheets else None),
        "stated": sections.get("stated"),
        "standard": sections.get("standard"),
        "fixed": sections.get("fixed"),
        "validity_days": validity,
        "missing_fields": msg.get("missing_fields") or [],
    }
    d["contact"] = contact(msg)
    d["stated_drivers"] = stated_drivers(msg.get("body"), series)
    ref = d["opening_offer"]["offer_id"] or f"{d['supplier_id']}#opening"
    extra.append((ref, CASE_DATE, msg.get("subject") or "", msg.get("body") or ""))
    return extra


def overlay(sid, part_ids, case=None, opening=None, src=None):
    """The dossier of `sid` for `part_ids`, with what `case` and `opening` add. Each stage that fails only
    leaves a warning."""
    warnings = []
    sid, why = alias(src, sid) if src is not None else (sid, None)
    if why:
        warnings.append(why)
    d = stored(sid)
    if d is None:
        try:
            d = assemble.build_supplier(src, sid) if src is not None else empty_dossier(sid)
            if src is not None and d["coverage"] != "case_only":
                signals.apply(d)
        except Exception as e:
            warnings.append(f"build failed: {type(e).__name__}: {e}")
            d = empty_dossier(sid)
        if src is not None and src.supplier(sid) is None:
            d["coverage"] = "case_only"
    if part_ids:
        parts = {}
        for pid in part_ids:
            if pid in d["parts"]:
                parts[pid] = d["parts"][pid]
            elif src is not None:
                try:
                    parts[pid], w = assemble.build_part(src, sid, pid, d["identity"].get("country"))
                    warnings += w
                except Exception as e:
                    warnings.append(f"{pid}: {type(e).__name__}: {e}")
                    parts[pid] = empty_part()
            else:
                parts[pid] = empty_part()
        d["parts"] = parts
    case = case if isinstance(case, dict) else {}
    facts = case_facts(case)
    extra = []
    if case:
        d["built_from"]["case_id"] = case.get("case_id")
        d["case_facts"] = facts
        for stage in (
            lambda: _apply_cost_facts(d, facts, sid),
            lambda: extra.extend(_case_texts(d, case, facts, src)),
            lambda: _alternatives(d, case, opening, facts, sid, src),
        ):
            try:
                stage()
            except Exception as e:
                warnings.append(f"case overlay: {type(e).__name__}: {e}")
    msg = first_supplier_message(thread(opening, sid))
    if msg:
        try:
            extra.extend(_apply_opening(d, msg, _series(src, facts)))
        except Exception as e:
            warnings.append(f"opening e-mail: {type(e).__name__}: {e}")
    if extra or case:
        signals.apply(d, extra)
    hook = citable_hook()
    if hook and src is not None:
        try:
            d["citable"] = hook(src.pkg, sid, sorted(d["parts"]), case=case or None)
        except Exception as e:
            warnings.append(f"citable_for failed: {type(e).__name__}: {e}")
    d["profile_text"] = render.profile(d)
    d["warnings"] = d["warnings"] + warnings
    return d
