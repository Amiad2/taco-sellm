# ruff: noqa: E501  (long test data lines)
import glob
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "package"


@pytest.fixture(scope="session")
def pkg():
    if not (DATA / "facts.json").is_file():
        pytest.skip("data package not downloaded (uv run arena data)")
    from arena_kit.data import DataPackage

    p = DataPackage(DATA)
    p.lookup("")
    return p


@pytest.fixture(autouse=True)
def strict(monkeypatch):
    monkeypatch.setenv("SELLM_STRICT", "1")  # a bug must fail the test, not hide behind the safe move


def records(label=None):
    out = []
    for f in sorted(glob.glob(str(ROOT / "runs" / "practice" / "*" / "*.json")) + glob.glob(str(ROOT / "runs" / "sandbox" / "*" / "*.json"))):
        r = json.loads(Path(f).read_text(encoding="utf-8"))
        if isinstance(r, dict) and "case" in r and (label is None or label in (r.get("label") or "")):
            out.append(r)
    if not out:
        pytest.skip("no saved sessions in runs/")
    return out


def states(record):
    """Every state a thread went through up to a supplier message, the other threads at their opening."""
    openings = {s: [t["messages"][0]] for s, t in record["threads"].items()}
    for sid, thread in record["threads"].items():
        for i, m in enumerate(thread["messages"]):
            if m.get("from") != "buyer" and not m.get("action"):
                yield sid, {**openings, sid: thread["messages"][: i + 1]}
