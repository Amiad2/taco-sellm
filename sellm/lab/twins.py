# ruff: noqa: E501  (quotes from the traces)
"""Twins of the suppliers we have played: case file, opening, standard terms and wording from our
real sessions in `runs/`, floor calibrated to the case's known C_best, the rest from evidence.

`EVIDENCE` holds what we read about each supplier, with where it comes from. Unknown dynamics keep
the defaults measured on sandbox D01 (`Persona`). Build once with `python -m sellm.lab calibrate`
(writes `sellm/lab/twins.json`); `load()` reads that file.
"""

import json
from pathlib import Path

from arena_kit.cost import closing_terms

from .persona import Persona, calibrate
from .table import Scenario

ROOT = Path(__file__).resolve().parents[2]
CACHE = Path(__file__).with_name("twins.json")

# rate: its cost of money, read from the price gap between its alternative sheets where it sent
# some; premiums in EUR per unit (see Persona). Quotes are from the traces in runs/.
EVIDENCE = {
    "sup:70110": dict(
        rate=0.08,
        style="family",
        traits=["family"],
        notes="P01 family foundry. Alt sheet: April start at 139.70 vs January 136.20, equal in value. "
        "'the 14-day payment term is essential for us to offer our best price'. Full cost 129.91 by "
        "calibration vs 129.95 implied by the arena's relationship charge on our deal.",
    ),
    "sup:70510": dict(
        rate=0.066,
        cap=0.015,
        notes="P02 group (Nordmark AG). Alt sheets: 60 days cost 2.05 more than 30 days (rate 6.6 %). "
        "'extending the payment terms would necessitate a higher unit price'.",
    ),
    "sup:70530": dict(
        rate=0.08,
        mirror=0.2,
        premiums={"contract_months": 3.4},
        traits=["price_frozen"],
        notes="P03 group. 'Our management has frozen all price reductions until December. We can talk "
        "about the terms instead - payment, volume or contract length.' 36 months took 438.21 to 431.47.",
    ),
    "sup:70620": dict(
        rate=0.08, style="family", traits=["family"], notes="P04 family bearing dealer, final offer at our 3rd message."
    ),
    "sup:70210": dict(
        rate=0.25,
        premiums={"lead_time_days": 0.12},
        style="casual",
        traits=["cash_short", "job_shop"],
        notes="P05 founder job shop, 22 staff. 'the 14-day payment works for us and helps keep things moving in the shop'.",
    ),
    "sup:70240": dict(
        rate=0.35,
        premiums={"lead_time_days": 0.12},
        style="casual",
        hard_limits={"lead_time_days": [">=", 42]},
        traits=["cash_short", "job_shop"],
        notes="P05 Czech job shop. 16 days faster payment = 0.50 (rate ~35 %). '35 days is too tight "
        "right now'; asked for 35 days instead of its 52 it quoted 34.00 against its 31.50 opening. "
        "Withdrew after a late message.",
    ),
    "sup:70250": dict(
        rate=0.25,
        premiums={"lead_time_days": 0.12},
        style="casual",
        traits=["cash_short", "job_shop"],
        notes="P05 founder job shop, equity 19.6 %. 'the 14-day payment is good for us'.",
    ),
    "sup:70610": dict(
        rate=0.08, style="family", traits=["family"], notes="P07 family fastener dealer; moved on contract length."
    ),
    "sup:70710": dict(
        rate=0.064,
        premiums={"fixed_price": 0.12},
        traits=["hedged"],
        notes="P08 steel service centre. 30 days payment = 0.03. 'we are unable to offer a fixed price for "
        "a 36-month contract'; 'AS-14404 is covered at fixed prices until March; falls there do not reach our cost'.",
    ),
    "sup:70410": dict(
        rate=0.08,
        premiums={"lead_time_days": 0.15},
        traits=["capacity_tight"],
        notes="P10 seal maker, capacity squeeze. Alt sheet: 42 days lead time 33.80 vs 54 days 32.00 (0.15 per day).",
    ),
    "sup:70140": dict(
        rate=0.08,
        ppm_real=2376,
        premiums={"ppm_commitment": 1.39},
        traits=["cash_short"],
        notes="P11 Polish foundry, scorecard 2,376 ppm. Alt sheet: 300 ppm/500 EUR chargeback 49.00 vs "
        "1,500 ppm/150 EUR 46.50. 'Faster payment would help us more than anything' (payment is fixed here).",
    ),
    "sup:70740": dict(
        rate=0.08,
        premiums={"fixed_price": 0.12},
        style="family",
        traits=["family", "hedged"],
        notes="P18 family bar stockist. 'We cannot offer a fixed price for a 24-month term, as the indexation is necessary'.",
    ),
    "sup:DEMO-F1": dict(
        rate=0.093,
        style="family",
        traits=["family"],
        notes="D01 family foundry. Alt sheet: 60 days 51.90 vs 30 days 51.50. Mirror 0.6-0.85, first counter "
        "fixed, final offer at our 6th message (experiments/RESULTS.md).",
    ),
    "sup:DEMO-J1": dict(
        rate=0.2, premiums={"lead_time_days": 0.1}, style="casual", traits=["job_shop"], notes="D02 German job shop."
    ),
    "sup:DEMO-C1": dict(
        rate=0.12,
        premiums={"lead_time_days": 0.1},
        notes="D02 Polish machining company, quoted EXW and 45 days; asked for DAP and 42 days it went up "
        "from 16.00 to 16.70. Withdrew when left at final_offer for a minute.",
    ),
}


def _sessions():
    """The richest session per case: the kit LLM agent's if there is one."""
    best = {}
    for f in sorted(ROOT.glob("runs/*/*/*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        if not (d.get("state") or {}).get("result", {}).get("c_best"):
            continue
        rank = 2 if d.get("label", "").startswith("kit llm") else 1
        if rank > best.get(d["case_id"], (0, None))[0]:
            best[d["case_id"]] = (rank, d)
    return {k: v[1] for k, v in sorted(best.items())}


def _drivers(package, parts):
    if package is None:
        return []
    rows = package.query(
        f"select distinct series_id from cost_drivers where part_id in ({','.join('?' * len(parts))})", tuple(parts)
    )
    return [r["series_id"] for r in rows]


def build(package=None):
    """Scenarios from runs/, calibrated. Slow (a few seconds per case); cache with `save`."""
    out = []
    for case_id, d in _sessions().items():
        case, result = d["case"], d["state"]["result"]
        personas = {}
        for sid, opening in d["analysis"]["openings"].items():
            first = d["threads"][sid]["messages"][0]
            pdf = {k: v for k, v in opening["standard_terms"].items() if v != "none"}
            stated = opening["terms"]
            standard = closing_terms(case, {k: v for k, v in stated.items() if k != "unit_price"}, pdf)
            standard.pop("unit_price", None)
            ev = dict(EVIDENCE.get(sid, {}))
            ev.pop("notes", None)
            personas[sid] = Persona(
                supplier_id=sid,
                name=(first.get("from_name") or "").split(", ", 1)[-1] or sid,
                opening=stated,
                standard=standard,
                pdf_standard=pdf,
                sender=first.get("from", ""),
                sender_name=first.get("from_name", ""),
                opening_body=first.get("body"),
                notes=EVIDENCE.get(sid, {}).get("notes", ""),
                **ev,
            )
        reached = calibrate(case, personas, result["c_best"])
        out.append(
            Scenario(
                case=case,
                personas=personas,
                c_open=result["c_open"],
                c_best=result["c_best"],
                kind="twin",
                name=case_id.split(":", 1)[1],
                notes=f"C_best {result['c_best']:,.0f}, model {reached:,.0f}",
                drivers=_drivers(package, case["parts"]),
            )
        )
    return out


def save(scenarios, path=CACHE):
    rows = [
        {
            "name": s.name,
            "kind": s.kind,
            "case": s.case,
            "c_open": s.c_open,
            "c_best": s.c_best,
            "notes": s.notes,
            "drivers": s.drivers,
            "personas": {k: p.to_dict() for k, p in s.personas.items()},
        }
        for s in scenarios
    ]
    path.write_text(json.dumps(rows, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def load(path=CACHE):
    rows = json.loads(Path(path).read_text(encoding="utf-8"))
    return [
        Scenario(
            case=r["case"],
            personas={k: Persona.from_dict(p) for k, p in r["personas"].items()},
            c_open=r["c_open"],
            c_best=r["c_best"],
            kind=r["kind"],
            name=r["name"],
            notes=r["notes"],
            drivers=r["drivers"],
        )
        for r in rows
    ]
