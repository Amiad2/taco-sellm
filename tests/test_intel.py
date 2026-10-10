"""sellm.intel: the dossier contract (docs/PLAN.md section 10), the builder and the case overlay."""

import time

import pytest

from sellm.intel import SCHEMA_VERSION, dossier
from sellm.intel.schema import CORE_FIELDS, SIGNAL_KINDS, TOP_KEYS


def test_the_stub_carries_every_field_of_the_contract():
    d = dossier("sup:70130", ["part:310011"])
    assert set(d) == set(TOP_KEYS) and set(CORE_FIELDS) <= set(d)
    assert d["schema_version"] == SCHEMA_VERSION == 1
    assert d["supplier_id"] == "sup:70130" and d["coverage"] == "case_only"
    assert isinstance(d["economics"]["cost_of_money"], float) and 0 < d["economics"]["cost_of_money"] <= 1
    assert d["economics"]["cash_pressure"] in ("low", "medium", "high")
    assert isinstance(d["signals"], list) and isinstance(d["citable"], list)
    assert set(d["parts"]) == {"part:310011"} and d["parts"]["part:310011"]["drivers"] == []
    assert "informal_costing" in SIGNAL_KINDS


@pytest.mark.parametrize(
    "sid, parts", [(None, None), (123, "part:X"), ("", [None, 5]), ("sup:1", 7), ("sup:1", {"a": 1})]
)
def test_dossier_never_raises(sid, parts):
    d = dossier(sid, parts, case={"weird": True}, opening=["not", "messages"])
    assert d["schema_version"] == 1 and isinstance(d["parts"], dict)


def test_the_stub_is_fast():
    t0 = time.perf_counter()
    for _ in range(100):
        dossier("sup:70130", ["part:310011", "part:310012"])
    assert (time.perf_counter() - t0) / 100 < 0.005
