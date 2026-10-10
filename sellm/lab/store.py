"""Scenarios to and from JSON, so they are generated once and loaded by every worker."""

import gzip
import json
from pathlib import Path

from .persona import Persona
from .table import Scenario


def to_row(s):
    return {
        "name": s.name,
        "kind": s.kind,
        "case": s.case,
        "c_open": s.c_open,
        "c_best": s.c_best,
        "notes": s.notes,
        "drivers": s.drivers,
        "tags": s.tags,
        "personas": {k: p.to_dict() for k, p in s.personas.items()},
    }


def from_row(r):
    return Scenario(
        case=r["case"],
        personas={k: Persona.from_dict(p) for k, p in r["personas"].items()},
        c_open=r["c_open"],
        c_best=r["c_best"],
        kind=r["kind"],
        name=r["name"],
        notes=r.get("notes", ""),
        drivers=r.get("drivers", []),
        tags=r.get("tags", []),
    )


def save(scenarios, path):
    path = Path(path)
    text = json.dumps([to_row(s) for s in scenarios], indent=None if path.suffix == ".gz" else 1, ensure_ascii=False)
    if path.suffix == ".gz":
        with gzip.open(path, "wt", encoding="utf-8") as f:
            f.write(text)
    else:
        path.write_text(text + "\n", encoding="utf-8")


def load(path):
    path = Path(path)
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8") as f:
            rows = json.load(f)
    else:
        rows = json.loads(path.read_text(encoding="utf-8"))
    return [from_row(r) for r in rows]
