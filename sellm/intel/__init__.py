"""Supplier dossiers for the negotiator (docs/PLAN.md section 10): `dossier()` never raises."""

from .schema import SCHEMA_VERSION, empty_dossier

__all__ = ["SCHEMA_VERSION", "dossier"]


def _part_list(part_ids):
    if isinstance(part_ids, str):
        return [part_ids]
    try:
        return [p for p in part_ids or () if isinstance(p, str)]
    except TypeError:
        return []


def dossier(supplier_id, part_ids=(), case=None, opening=None, package=None):
    """What we know about `supplier_id` for the parts of a case, with the case's own facts merged in."""
    sid = supplier_id if isinstance(supplier_id, str) and supplier_id else "sup:unknown"
    d = empty_dossier(sid, _part_list(part_ids))
    d["warnings"].append("stub: values arrive with the dossier builder")
    return d
