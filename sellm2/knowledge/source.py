# ruff: noqa: E501  (long sentences and messages)
"""Read-only access to the data package, shared by every case played at once.

One lock around every query (the package is one SQLite connection, shared across threads), no
200-row cap, and the Sunday release's rows (they sit in the package's ID index, not in SQLite).
Nothing here raises: a failed lookup is an empty answer and a warning in the log.
"""

import logging
import re
import threading
from functools import cached_property

log = logging.getLogger("sellm2")
LOCK = threading.RLock()
LIMIT = 1_000_000
HEADER = re.compile(r"^\S[^\n]* - \d{4}-\d{2}-\d{2} - ")  # "kind - date - author"


class Source:
    def __init__(self, package):
        self.pkg = package
        self.facts = getattr(package, "facts", None) or {}

    # -- plain access ----------------------------------------------------------------------------
    def q(self, sql, params=()):
        if self.pkg is None:
            return []
        try:
            with LOCK:
                return self.pkg.query(sql, params, limit=LIMIT)
        except Exception as e:  # a table or column less in a later release: an answer less, said so
            log.warning("sellm2 data: query failed (%s: %s) - %s", type(e).__name__, e, sql[:70])
            return []

    def one(self, sql, params=()):
        rows = self.q(sql, params)
        return rows[0] if rows else None

    def fact(self, ref):
        return self.facts.get(ref)

    def text(self, ref):
        """A document's text without its title and its 'kind - date - author' line."""
        if self.pkg is None:
            return ""
        try:
            with LOCK:
                raw = self.pkg.document(ref)
        except Exception:
            return ""
        lines = (raw or "").strip().splitlines()
        if lines and lines[0].startswith("# "):
            lines = lines[1:]
        while lines and not lines[0].strip():
            lines = lines[1:]
        if lines and HEADER.match(lines[0]):
            lines = lines[1:]
        return "\n".join(lines).strip()

    # -- indexes built once ----------------------------------------------------------------------
    @cached_property
    def by_kind(self):
        out = {}
        for ref, fact in self.facts.items():
            if isinstance(fact, dict):
                out.setdefault(ref.split(":", 1)[0], []).append((ref, fact))
        return out

    @cached_property
    def series(self):
        """{series: [(month, value, ref)]} sorted by month."""
        out = {}
        for ref, f in self.by_kind.get("idx", []):
            if f.get("month") and f.get("value") is not None:
                out.setdefault(f["series"], []).append((f["month"], float(f["value"]), ref))
        return {s: sorted(rows) for s, rows in out.items()}

    @cached_property
    def data_last(self):
        """The last month of any index series: the end of the data."""
        return max((rows[-1][0] for rows in self.series.values() if rows), default="")

    @cached_property
    def released(self):
        """Rows the Sunday release adds: {ref: row} with a 'table' key."""
        if self.pkg is None:
            return {}
        try:
            with LOCK:
                ids = self.pkg._ids
            return {ref: row for ref, row in ids.items() if row.get("root")}
        except Exception:
            return {}

    def released_rows(self, table, sid):
        out = []
        for ref, row in sorted(self.released.items()):
            if row.get("table") != table:
                continue
            fact = self.facts.get(ref) or {}
            owner = row.get("supplier_id") or fact.get("supplier") or None
            if owner == sid:
                out.append({**fact, **row, "id": ref, "supplier_id": owner})
        return out

    @cached_property
    def drivers(self):
        """{part: [(series, weight)]} heaviest first."""
        out = {}
        for r in self.q("SELECT part_id, series_id, weight FROM cost_drivers ORDER BY weight DESC, series_id"):
            out.setdefault(r["part_id"], []).append((r["series_id"], float(r.get("weight") or 0.0)))
        return out

    @cached_property
    def cost_owner(self):
        return {r["id"]: r.get("supplier_id") for r in self.q("SELECT id, supplier_id FROM should_cost")}

    @cached_property
    def price_units(self):
        return {r["id"]: r.get("price_unit") or 1 for r in self.q("SELECT id, price_unit FROM parts")}

    @cached_property
    def forecast_shared(self):
        return {r["id"]: bool(r.get("shared_with_suppliers")) for r in self.q("SELECT id, shared_with_suppliers FROM forecasts")}

    @cached_property
    def letter_kind(self):
        return {r["id"]: r.get("kind") for r in self.q("SELECT id, kind FROM documents")}


_SOURCES = {}


def source(package):
    """One Source per package object (cached, thread-safe)."""
    with LOCK:
        hit = _SOURCES.get(id(package))
        if hit is None or hit.pkg is not package:
            hit = _SOURCES[id(package)] = Source(package)
        return hit
