"""Supplier dossiers for the negotiator (docs/PLAN.md section 10): `dossier()` never raises."""

import os
from pathlib import Path

from .schema import SCHEMA_VERSION, empty_dossier

__all__ = ["SCHEMA_VERSION", "dossier"]

_SOURCES = {}


def _part_list(part_ids):
    if isinstance(part_ids, str):
        part_ids = [part_ids]
    if not isinstance(part_ids, list | tuple | set | frozenset):
        return []
    return list(dict.fromkeys(p for p in part_ids if isinstance(p, str) and p.startswith("part:")))


def _supplier_id(supplier_id):
    if isinstance(supplier_id, str) and supplier_id.strip():
        sid = supplier_id.strip()
        return sid if sid.startswith("sup:") else f"sup:{sid}"
    return "sup:unknown"


def _source(package):
    """The data package as a Source, read once per process; None when there is none."""
    from arena_kit.data import DataPackage

    from .extract import Source

    # the package object itself is the key (an id() could be reused once it is freed)
    key = "env" if package is None else package if isinstance(package, DataPackage) else str(Path(package).resolve())
    if key not in _SOURCES:
        try:
            if package is None:
                root = Path(os.environ.get("ARENA_DATA", "data/package"))
                pkg = DataPackage(root) if root.is_dir() else None
            else:
                pkg = package if isinstance(package, DataPackage) else DataPackage(package)
            _SOURCES[key] = Source(pkg) if pkg is not None else None
        except (OSError, ValueError, TypeError):
            _SOURCES[key] = None
    return _SOURCES[key]


def dossier(supplier_id, part_ids=(), case=None, opening=None, package=None):
    """What we know about `supplier_id` for `part_ids`, with what `case` and the opening e-mails in
    `opening` (the threads dict, or this supplier's messages) add. `package`: a DataPackage or its path;
    default $ARENA_DATA. Never raises; problems are listed in `warnings`."""
    sid, parts = _supplier_id(supplier_id), _part_list(part_ids)
    try:
        from .overlay import overlay

        src = _source(package)
        d = overlay(sid, parts, case, opening, src)
        if src is None:
            d["warnings"].append("no data package: stored dossiers and the case only")
        return d
    except Exception as e:
        d = empty_dossier(sid, parts)
        d["warnings"].append(f"dossier failed: {type(e).__name__}: {e}")
        return d
