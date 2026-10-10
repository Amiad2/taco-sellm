"""Read-only access to the data package for the dossiers: SQL rows plus the Sunday release's rows."""

import hashlib
import json
import re
from functools import cached_property

LIMIT = 1_000_000  # DataPackage.query returns 200 rows unless told otherwise
HEADER = re.compile(r"^\S[^\n]* - \d{4}-\d{2}-\d{2} - ")


def number(ref):
    """'part:310010' -> '310010'."""
    return ref.split(":", 1)[1] if isinstance(ref, str) and ":" in ref else ref


def body(text):
    """A correspondence file without its title and its 'kind - date - author' line."""
    lines = (text or "").strip().splitlines()
    if lines and lines[0].startswith("# "):
        lines = lines[1:]
    while lines and not lines[0].strip():
        lines = lines[1:]
    if lines and HEADER.match(lines[0]):
        lines = lines[1:]
    return "\n".join(lines).strip()


def split_ids(value):
    return [p.strip() for p in re.split(r"[;,]", value or "") if p.strip()]


class Source:
    """The package, read once: SQL, facts, index series and the rows the Sunday release adds."""

    def __init__(self, pkg):
        self.pkg = pkg
        self.facts = pkg.facts
        self.series = {}
        for ref, fact in self.facts.items():
            if ref.startswith("idx:") and isinstance(fact, dict) and fact.get("month"):
                self.series.setdefault(fact["series"], {})[fact["month"]] = (fact["value"], ref)
        # rows of release-sunday/data/*.csv: in the ID index, not in the SQLite file
        self.release_rows = {ref: row for ref, row in pkg._ids.items() if row.get("root")}

    def q(self, sql, params=()):
        return self.pkg.query(sql, params, limit=LIMIT)

    def one(self, sql, params=()):
        rows = self.q(sql, params)
        return rows[0] if rows else None

    @cached_property
    def facts_sha256(self):
        return hashlib.sha256(json.dumps(self.facts, sort_keys=True).encode()).hexdigest()

    @cached_property
    def version(self):
        path = self.pkg.root / "datapackage.json"
        try:
            return json.loads(path.read_text(encoding="utf-8")).get("version") or "unknown"
        except (OSError, ValueError):
            return "unknown"

    # -- suppliers and parts ------------------------------------------------------------------------
    def detailed_ids(self):
        return [r["id"] for r in self.q("SELECT id FROM suppliers WHERE detail = 'full' ORDER BY id")]

    def supplier(self, sid):
        return self.one(
            "SELECT s.*, i.legal_form, i.founded, i.owner_type, i.group_parent, i.staff, i.turnover_eur, "
            "i.turnover_band, i.equity_ratio_pct, i.credit_index, i.credit_index_12m_ago, i.vda63_grade, "
            "i.certifications FROM suppliers s LEFT JOIN supplier_intel i ON i.supplier_id = s.id WHERE s.id = ?",
            (sid,),
        )

    def sourcing(self, sid):
        return self.q("SELECT * FROM sourcing WHERE supplier_id = ? ORDER BY part_id", (sid,))

    def sourcing_row(self, sid, pid):
        return self.one("SELECT * FROM sourcing WHERE supplier_id = ? AND part_id = ?", (sid, pid))

    def part(self, pid):
        return self.one("SELECT * FROM parts WHERE id = ?", (pid,))

    def current_price(self, sid, pid):
        return self.one(
            "SELECT * FROM price_conditions WHERE supplier_id = ? AND part_id = ? "
            "ORDER BY (valid_to IS NULL) DESC, valid_from DESC LIMIT 1",
            (sid, pid),
        )

    def history(self, sid, pid):
        return self.q(
            "SELECT * FROM negotiation_history WHERE supplier_id = ? AND part_id = ? ORDER BY date, event_id",
            (sid, pid),
        )

    def should_cost(self, pid):
        return self.q("SELECT * FROM should_cost WHERE part_id = ? ORDER BY id", (pid,))

    def drivers(self, pid):
        return self.q("SELECT * FROM cost_drivers WHERE part_id = ? ORDER BY weight DESC, series_id", (pid,))

    def forecast(self, pid):
        refs = sorted(r for r in self.facts if r.startswith(f"fc:{number(pid)}@"))
        if not refs:
            return None, None
        ref = refs[-1]
        return ref, self.one("SELECT * FROM forecasts WHERE id = ?", (ref,))

    def other_sources(self, sid, pid):
        return self.q(
            "SELECT so.*, s.name FROM sourcing so JOIN suppliers s ON s.id = so.supplier_id "
            "WHERE so.part_id = ? AND so.supplier_id != ? ORDER BY so.supplier_id",
            (pid, sid),
        )

    def rival_quotes(self, sid, pid):
        return self.q(
            "SELECT q.*, s.name FROM quotes q LEFT JOIN suppliers s ON s.id = q.supplier_id "
            "WHERE q.part_id = ? AND q.supplier_id != ? ORDER BY q.supplier_id, q.quote_date, q.id",
            (pid, sid),
        )

    def own_quotes(self, sid):
        return self.q("SELECT * FROM quotes WHERE supplier_id = ? ORDER BY quote_date, id", (sid,))

    # -- the relationship ---------------------------------------------------------------------------
    def contract(self, sid):
        return self.one("SELECT * FROM contracts WHERE supplier_id = ? ORDER BY valid_to DESC, id LIMIT 1", (sid,))

    def index_clauses(self, contract_id):
        return self.q(
            "SELECT * FROM contract_clauses WHERE contract_id = ? AND type = 'index' ORDER BY id", (contract_id,)
        )

    def scorecards(self, sid):
        return self.q("SELECT * FROM scorecards WHERE supplier_id = ? ORDER BY quarter DESC", (sid,))

    def complaints(self, sid, start, end):
        return self.q(
            "SELECT * FROM quality_notifications WHERE supplier_id = ? AND qn_date BETWEEN ? AND ? "
            "ORDER BY qn_date, id",
            (sid, start, end),
        )

    def spend(self, sid):
        return self.q(
            "SELECT fiscal_year, sum(spend_eur) AS spend FROM spend_cube WHERE supplier_id = ? GROUP BY fiscal_year "
            "ORDER BY fiscal_year",
            (sid,),
        )

    def payments(self, sid):
        return self.one(
            "SELECT count(*) AS n, avg(julianday(paid_date) - julianday(due_date)) AS late, "
            "avg(discount_taken) AS discount FROM invoices WHERE supplier_id = ?",
            (sid,),
        )

    # -- texts --------------------------------------------------------------------------------------
    def _released(self, table, sid):
        out = []
        for ref, row in sorted(self.release_rows.items()):
            if row.get("table") != table:
                continue
            fact = self.facts.get(ref) or {}
            owner = row.get("supplier_id") or fact.get("supplier") or None
            if owner == sid:
                out.append({**fact, **row, "supplier_id": owner})
        return out

    def documents(self, sid):
        rows = self.q("SELECT * FROM documents WHERE supplier_id = ? ORDER BY date, id", (sid,))
        rows += self._released("documents", sid)
        for row in rows:
            try:
                row["text"] = body(self.pkg.document(row["id"]))
            except (FileNotFoundError, OSError):
                row["text"] = ""
        return rows

    def news(self, sid):
        return self.q("SELECT * FROM news WHERE supplier_id = ? ORDER BY date, id", (sid,)) + self._released(
            "news", sid
        )

    def market_news(self):
        rows = self.q("SELECT * FROM news WHERE supplier_id IS NULL OR supplier_id = '' ORDER BY date, id")
        return rows + self._released("news", None)
