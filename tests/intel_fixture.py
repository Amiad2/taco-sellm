# ruff: noqa: E501
"""A small data package with the real package's columns and every trap the dossier builder must handle."""

import json
import sqlite3

TABLES = {
    "suppliers": "id, name, country, currency, payment_days, skonto_days, skonto_pct, incoterm, created, category, "
    "detail, blocked, contract_id, standard_lead_time_days, abc_class",
    "supplier_intel": "supplier_id, legal_form, founded, owner_type, group_parent, staff, filed_fy, turnover_eur, "
    "turnover_band, equity_ratio_pct, credit_index, credit_index_12m_ago, vda63_grade, certifications",
    "parts": "id, description, category, material_group, grade, net_weight_kg, uom, price_unit, planned_lead_time_days, "
    "pump_series, standard_price, status, abc_class",
    "sourcing": "part_id, supplier_id, status, quota_pct, approved_since, tooling_owner",
    "price_conditions": "part_id, supplier_id, valid_from, price, basis, event_id, valid_to, price_unit, currency",
    "negotiation_history": "event_id, date, supplier_id, part_id, type, asked_pct, settled_pct, note",
    "contracts": "id, supplier_id, type, valid_from, valid_to, payment_days, incoterm, notice_days, price_basis, file",
    "contract_clauses": "id, contract_id, clause, type, text, series, material_share, deadband_pct, days",
    "scorecards": "id, supplier_id, quarter, period_start, period_end, gr_lines, otd_pct, otd_confirmed_pct, "
    "received_qty, complaint_qty, ppm, qn_count, open_8d_overdue, score, class, colour",
    "quality_notifications": "id, supplier_id, part_id, gr_id, qn_date, defect, complaint_qty, returned_qty, "
    "supplier_caused, cost_recharged_eur, d3_date, d8_date",
    "forecasts": "id, part_id, snapshot_month, horizon_months, qty_next_12m, uom, shared_with_suppliers",
    "quotes": "id, rfq_id, supplier_id, part_id, quote_date, unit_price, price_unit, currency, lead_time_days, "
    "incoterm, payment_days, validity_days, tooling_eur, awarded, missing_fields, remarks",
    "spend_cube": "fiscal_year, supplier_id, category, spend_eur, invoice_count",
    "invoices": "id, supplier_id, po_line_id, gr_id, invoice_date, qty, amount_eur, due_date, paid_date, "
    "paid_amount_eur, discount_taken",
    "cost_drivers": "part_id, series_id, weight, source",
    "should_cost": "id, part_id, estimate_date, cost_base, supplier_id, unit_cost, price_unit, material_eur, "
    "conversion_eur, overhead_eur, confidence_pct, method",
    "news": "id, date, supplier_id, topic, headline, body, source",
    "documents": "id, date, kind, supplier_id, part_ids, subject, author, file, asked_pct, asked_price, "
    "effective_date, notice_days",
}

ROWS = {
    "suppliers": [
        ("sup:1", "Foundry One GmbH", "DE", "EUR", 30, None, None, "FCA", "1996-01-01", "castings", "full", 0, "ctr:1", 42, "A"),
        ("sup:2", "Shop Two s.r.o.", "CZ", "EUR", 30, 10, 2, "EXW", "2004-01-01", "machined parts", "full", 0, None, 28, "B"),
        ("sup:3", "Group Three AG", "DE", "EUR", 60, None, None, "DAP", "1996-01-01", "castings", "full", 0, None, 35, "A"),
        ("sup:9", "Old Record e.K.", "DE", "EUR", 30, None, None, "EXW", "1990-01-01", "castings", "spend only", 1, None, None, "C"),
    ],
    "supplier_intel": [
        ("sup:1", "GmbH", 1954, "family", None, 120, 2024, 19300000, "10-25 M EUR", 39.9, 231, 231, "B", "ISO 9001; ISO 14001"),
        ("sup:2", "s.r.o.", 1998, "founder", None, 22, 2024, None, "2-5 M EUR", 30.0, 302, 230, "B", "ISO 9001"),
        ("sup:3", "AG", 1900, "group", "Holding Three", 900, 2024, 1380000000, ">1000 M EUR", 45.0, 150, 150, "A", ""),
    ],
    "parts": [
        ("part:A", "Casing A", "castings", "cast_iron", "EN-GJL-250", 38.0, "pc", 1, 42, "HN", 100.0, "series", "A"),
        ("part:B", "Bolt kit B", "C-parts", "steel", "8.8", 0.1, "pc", 100, 14, "HN", 50.0, "series", "C"),
        ("part:C", "Casing C", "castings", "cast_iron", "EN-GJL-250", 20.0, "pc", 1, 42, "HX", 80.0, "series", "A"),
    ],
    "sourcing": [
        ("part:A", "sup:1", "active", 100, "2010-01-01", "Hollerau"),
        ("part:B", "sup:1", "active", 60, "2012-01-01", "supplier"),
        ("part:B", "sup:2", "qualified", 40, "2015-01-01", "supplier"),
        ("part:C", "sup:3", "active", 100, "2011-01-01", "Hollerau"),
    ],
    "price_conditions": [
        ("part:A", "sup:1", "2025-01-01", 100.0, "renewal", "EV-1", "2025-12-31", 1, "EUR"),
        ("part:A", "sup:1", "2026-01-01", 102.0, "renewal", "EV-2", None, 1, "EUR"),
        ("part:B", "sup:1", "2026-01-01", 50.0, "contract", "EV-3", None, 100, "EUR"),
        ("part:B", "sup:2", "2026-01-01", 48.0, "contract", "EV-4", None, 100, "EUR"),
        ("part:C", "sup:3", "2026-01-01", 85.0, "contract", "EV-5", None, 1, "EUR"),
    ],
    "negotiation_history": [
        ("EV-1", "2024-11-20", "sup:1", "part:A", "annual renewal", 2.0, -1.0, "accepted below full cost to keep the volume"),
        ("EV-2", "2025-11-20", "sup:1", "part:A", "annual renewal", 3.0, 0.5, ""),
    ],
    "contracts": [("ctr:1", "sup:1", "framework agreement", "2024-01-01", "2026-12-31", 30, "FCA", 90, "fixed per year", "contracts/1.md")],
    "contract_clauses": [
        ("ctr:1#2.1", "ctr:1", "2.1", "scope", "Scope.", None, None, None, None),
        ("ctr:1#3.2", "ctr:1", "3.2", "index", "Index clause.", "S1", 0.5, 0, None),
    ],
    "scorecards": [
        ("sc:1@2025Q3", "sup:1", "2025Q3", "", "", 50, 89.8, 90.0, 1000, 1, 1379, 1, 0, 78.0, "B", "amber"),
        ("sc:1@2025Q4", "sup:1", "2025Q4", "", "", 50, 92.2, 93.0, 1000, 1, 1486, 1, 0, 88.6, "A", "green"),
        ("sc:1@2026Q1", "sup:1", "2026Q1", "", "", 50, 90.2, 91.0, 1000, 1, 1163, 1, 0, 89.3, "A", "green"),
        ("sc:1@2026Q2", "sup:1", "2026Q2", "", "", 50, 86.5, 87.0, 1000, 1, 1290, 1, 0, 86.8, "A", "green"),
        ("sc:1@2026Q3", "sup:1", "2026Q3", "", "", 50, 82.4, 83.0, 1000, 1, 651, 1, 0, 87.9, "A", "green"),
        ("sc:2@2026Q3", "sup:2", "2026Q3", "", "", 50, 62.5, 70.0, 1000, 2, 1863, 2, 1, 70.0, "B", "amber"),
    ],
    "quality_notifications": [
        ("qn:1", "sup:1", "part:A", "gr:1", "2026-03-01", "porosity", 1, 1, 1, 150, "2026-03-05", "2026-04-10"),
        ("qn:2", "sup:1", "part:A", "gr:2", "2025-03-01", "burr", 1, 0, 1, 150, "2025-03-05", "2025-04-10"),
    ],
    "forecasts": [
        ("fc:A@2026-03", "part:A", "2026-03", 12, 950, "pc", 1),
        ("fc:A@2026-06", "part:A", "2026-06", 12, 1000, "pc", 1),
    ],
    "quotes": [
        ("quote:1", "rfq:1", "sup:1", "part:A", "2025-01-22", 101.0, 1, "EUR", 42, "FCA", 30, 30, 0, 1, "", "Payment within 10 days requested."),
        ("quote:2", "rfq:2", "sup:2", "part:B", "2025-02-01", 47.0, 100, "EUR", 28, "EXW", 30, 30, 0, 0, "",
         "Material covered until March 2027; price valid accordingly."),
        ("quote:3", "rfq:1", "sup:2", "part:A", "2025-01-25", 99.0, 1, "EUR", 49, "EXW", 30, 30, 0, 0, "", ""),
    ],
    "spend_cube": [
        ("FY2025", "sup:1", "castings", 1000000.0, 10),
        ("FY2026", "sup:1", "castings", 1000000.0, 10),
        ("FY2026", "sup:1", "MRO", 289395.92, 2),
        ("FY2026", "sup:2", "machined parts", 350000.0, 5),
    ],
    "invoices": [
        ("inv:1", "sup:1", "po:1", "gr:1", "2026-01-01", 1, 1.0, "2026-02-01", "2026-02-03", 1.0, 0),
        ("inv:2", "sup:1", "po:2", "gr:2", "2026-03-01", 1, 1.0, "2026-04-01", "2026-04-05", 1.0, 0),
        ("inv:3", "sup:2", "po:3", "gr:3", "2026-03-01", 1, 1.0, "2026-04-01", "2026-03-11", 1.0, 1),
        ("inv:4", "sup:2", "po:4", "gr:4", "2026-05-01", 1, 1.0, "2026-06-01", "2026-06-01", 1.0, 0),
    ],
    "cost_drivers": [("part:A", "S1", 0.4, "estimate"), ("part:A", "S2", 0.2, "estimate")],
    "should_cost": [
        ("cost:A", "part:A", "2026-07-15", "DE", "sup:1", 101.0, 1, 40.0, 40.0, 21.0, 5, "plant"),
        ("cost:B", "part:B", "2026-07-15", "CZ", "sup:2", 45.0, 100, 20.0, 15.0, 10.0, 5, "plant"),
        ("cost:B-1", "part:B", "2026-07-15", "DE", "sup:1", 49.0, 100, 20.0, 19.0, 10.0, 5, "plant"),
        ("cost:C", "part:C", "2026-07-15", "DE", None, 80.0, 1, 30.0, 30.0, 20.0, 10, "generic"),
    ],
    "news": [
        ("news:1", "2026-03-22", "sup:1", "succession", "Owner of Foundry One seeks a successor", "No successor in the family.", "Paper"),
        ("news:2", "2026-04-01", "sup:2", "noise", "New managing director at Shop Two", "A new managing director.", "Paper"),
        ("news:3", "2026-09-10", None, "market", "Iron castings +1.8 % year on year", "Castings prices rose.", "Paper"),
    ],
    "documents": [
        ("doc:1", "2026-08-02", "call_note", "sup:1", "", "Liquidity", "Hollerau Pumpenwerke, Purchasing", "correspondence/1.md", None, None, None, None),
        ("doc:2", "2026-09-11", "meeting_note", "sup:1", "", "Customer portfolio", "Hollerau Pumpenwerke, Purchasing", "correspondence/2.md", None, None, None, None),
        ("doc:3", "2026-09-12", "letter", "sup:1", "part:A", "Price adjustment", "Foundry One GmbH", "correspondence/3.md", 9.5, 111.69, "2026-11-01", 51),
        ("doc:4", "2025-12-01", "email", "sup:2", "", "Holiday shutdown", "Shop Two s.r.o.", "correspondence/4.md", None, None, None, None),
    ],
}  # fmt: skip

TEXTS = {
    "1.md": "# Liquidity\n\ncall note - 2026-08-02 - Hollerau Pumpenwerke, Purchasing\n\nCall with the managing director: "
    "he asked twice whether we could pay earlier and said the bank is watching every month. "
    "'I cannot sign anything that lowers our margin now.'",
    "2.md": "# Customer portfolio\n\nmeeting note - 2026-09-11 - Hollerau Pumpenwerke, Purchasing\n\n"
    "The sales director said they will focus on customers with volume.",
    "3.md": "# Price adjustment\n\nletter - 2026-09-12 - Foundry One GmbH\n\nWe must raise prices by 9.5 %.",
    "4.md": "# Holiday shutdown\n\nemail - 2025-12-01 - Shop Two s.r.o.\n\nOur plant is closed from 23 December.",
}

FACTS = {
    "idx:S1@2025-08": {"series": "S1", "month": "2025-08", "value": 100.0},
    "idx:S1@2026-02": {"series": "S1", "month": "2026-02", "value": 104.0},
    "idx:S1@2026-08": {"series": "S1", "month": "2026-08", "value": 106.0},
    "idx:S2@2025-06": {"series": "S2", "month": "2025-06", "value": 100.0},
    "idx:S2@2025-12": {"series": "S2", "month": "2025-12", "value": 98.0},
    "idx:S2@2026-06": {"series": "S2", "month": "2026-06", "value": 95.0},
    "fc:A@2026-03": {"part": "part:A", "change_pct": 2.0, "volume_per_year": 950},
    "fc:A@2026-06": {"part": "part:A", "change_pct": 5.0, "volume_per_year": 1000},
    "cost:A": {"part": "part:A", "unit_cost": 101.0, "price_unit": 1, "confidence_pct": 5},
    "cost:B": {"part": "part:B", "unit_cost": 45.0, "price_unit": 100, "confidence_pct": 5},
    "cost:B-1": {"part": "part:B", "unit_cost": 49.0, "price_unit": 100, "confidence_pct": 5},
    "cost:C": {"part": "part:C", "unit_cost": 80.0, "price_unit": 1, "confidence_pct": 10},
    "sc:1@2026Q3": {"supplier": "sup:1", "quarter": "2026Q3", "otd_pct": 82.4, "ppm": 651, "colour": "green"},
    "quote:1": {"supplier": "sup:1", "part": "part:A", "unit_price": 101.0},
    "quote:3": {"supplier": "sup:2", "part": "part:A", "unit_price": 99.0},
    "news:1": {"supplier": "sup:1", "date": "2026-03-22", "topic": "succession"},
    "news:3": {"supplier": None, "date": "2026-09-10", "topic": "market"},
    "doc:1": {"supplier": "sup:1", "date": "2026-08-02", "type": "call_note"},
    "doc:3": {"supplier": "sup:1", "date": "2026-09-12", "type": "letter", "asked_pct": 9.5, "days": 51},
    "ctr:1": {"supplier": "sup:1", "days": 90},
}


def make_package(root, release=False):
    """Write the package into `root` (and a Sunday release next to it if asked); return `root`."""
    root.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(root / "world.sqlite")
    for table, cols in TABLES.items():
        db.execute(f"CREATE TABLE {table} ({cols})")
        for row in ROWS.get(table, []):
            db.execute(f"INSERT INTO {table} VALUES ({','.join('?' * len(row))})", row)
    db.commit()
    db.close()
    (root / "facts.json").write_text(json.dumps(FACTS), encoding="utf-8")
    (root / "datapackage.json").write_text(json.dumps({"version": "9.9.9"}), encoding="utf-8")
    (root / "correspondence").mkdir(exist_ok=True)
    for name, text in TEXTS.items():
        (root / "correspondence" / name).write_text(text, encoding="utf-8")
    if release:
        rel = root / "release-sunday"
        (rel / "data").mkdir(parents=True, exist_ok=True)
        (rel / "correspondence").mkdir(exist_ok=True)
        (rel / "facts.json").write_text(
            json.dumps(
                {
                    "doc:R1": {"supplier": "sup:3", "date": "2026-10-10", "type": "letter"},
                    "news:R1": {"supplier": "sup:3", "date": "2026-10-10", "topic": "allocation"},
                }
            ),
            encoding="utf-8",
        )
        (rel / "data/documents.csv").write_text(
            "id,date,kind,supplier_id,part_ids,subject,author,file\n"
            "doc:R1,2026-10-10,letter,sup:3,part:C,Allocation,Group Three AG,correspondence/r1.md\n",
            encoding="utf-8",
        )
        (rel / "data/news.csv").write_text(
            "id,date,supplier_id,topic,headline,body,source\n"
            "news:R1,2026-10-10,sup:3,allocation,Group Three allocates castings,All customers are on allocation.,Paper\n",
            encoding="utf-8",
        )
        (rel / "correspondence/r1.md").write_text(
            "# Allocation\n\nletter - 2026-10-10 - Group Three AG\n\nWe are on allocation for the rest of the year.",
            encoding="utf-8",
        )
    return root
