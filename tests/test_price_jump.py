"""The order history as an argument (`sellm/claims.py` `_po`): where a supplier raised its price within
the last twelve months, the bank cites the last order at the old price and the latest one.
experiments/LEDGER-JONATHAN.md J8, J9."""

import glob
import json
from pathlib import Path

import pytest

from sellm import claims

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "package"


@pytest.fixture(scope="module")
def package():
    if not DATA.is_dir():
        pytest.skip("needs the data package")
    from arena_kit.data import DataPackage

    return DataPackage(DATA)


def po_facts(package, case_id):
    files = sorted(glob.glob(str(ROOT / "runs" / "practice" / case_id / "*.json")))
    if not files:
        pytest.skip(f"no saved session of {case_id}")
    case = json.loads(Path(files[-1]).read_text(encoding="utf-8"))["case"]
    sid = case["suppliers"][0]
    return [a for a in claims.arguments(case, sid, None, package=package, used=set()) if a["kind"] == "po"]


def test_a_price_jump_within_twelve_months_is_cited_first(package):
    """P18: 5.26 until June, 5.84 since July - 'based on this historical data we can reduce our price'
    (0.598 -> 0.657); the two-year pair '5.75, 5.84' was dismissed 24 of 28 times."""
    first, second = po_facts(package, "P18")[:2]
    assert "EUR 5.26 per unit in 2026-06 and at EUR 5.84 per unit in 2026-09" in first["sentence"]
    assert "EUR 5.75 per unit in 2024-09" in second["sentence"]
    assert first["ids"][1] == second["ids"][1], "both end at the latest order: citing one uses the other up"
    # P08: flat over two years, so there was no fact at all - and 5.17 last winter against 5.45 now (0.637 -> 0.814)
    (only,) = po_facts(package, "P08")
    assert "EUR 5.17 per unit in 2025-12 and at EUR 5.45 per unit in 2026-09" in only["sentence"]


def test_without_a_jump_the_history_is_cited_as_before(package):
    for case_id, start in (("P02", "EUR 339.37 per unit in 2024-09"), ("P04", "EUR 4.29 per unit in 2024-09")):
        (only,) = po_facts(package, case_id)
        assert start in only["sentence"]
    for case_id in ("P01", "P10", "P11"):
        assert po_facts(package, case_id) == []
