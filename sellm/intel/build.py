"""Build every detailed supplier's dossier and write them to sellm/dossiers/ (docs/PLAN.md section 10)."""

from pathlib import Path

from . import assemble, render, signals
from .extract import Source, number
from .schema import SCHEMA_VERSION
from .serialize import write

DOSSIERS = Path(__file__).resolve().parent.parent / "dossiers"


def citable_hook():
    """Group C's sellm.claims.citable_for, once it exists; until then the dossiers carry no citable facts."""
    try:
        from sellm.claims import citable_for
    except ImportError:
        return None
    return citable_for


def build_one(src, sid):
    d = assemble.build_supplier(src, sid)
    signals.apply(d)
    hook = citable_hook()
    if hook:
        try:
            d["citable"] = hook(src.pkg, sid, sorted(d["parts"]))
        except Exception as e:  # group C's code must not stop the build
            d["warnings"].append(f"citable_for failed: {type(e).__name__}: {e}")
    d["profile_text"] = render.profile(d)
    return d


def build_all(pkg):
    src = Source(pkg)
    return {sid: build_one(src, sid) for sid in src.detailed_ids()}


def index(dossiers):
    first = next(iter(dossiers.values()), None)
    return {
        "schema_version": SCHEMA_VERSION,
        "built_from": first["built_from"] if first else None,
        "suppliers": {
            sid: {
                "name": d["identity"]["name"],
                "file": f"{number(sid)}.json",
                "coverage": d["coverage"],
                "parts": sorted(d["parts"]),
                "signals": [s["kind"] for s in d["signals"]],
            }
            for sid, d in sorted(dossiers.items())
        },
    }


def write_all(dossiers, out=DOSSIERS):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    wanted = {f"{number(sid)}.json" for sid in dossiers} | {"index.json"}
    for stale in out.glob("*.json"):
        if stale.name not in wanted:
            stale.unlink()
    for sid, d in dossiers.items():
        write(out / f"{number(sid)}.json", d)
    write(out / "index.json", index(dossiers))
    return sorted(wanted)
