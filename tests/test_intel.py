"""sellm.intel: the dossier contract (docs/PLAN.md section 10), the builder and the case overlay."""

import time

import pytest

from sellm.intel import SCHEMA_VERSION, dossier
from sellm.intel.schema import CORE_FIELDS, SIGNAL_KINDS, TOP_KEYS, validate


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


def test_the_stub_is_valid():
    assert validate(dossier("sup:70130", ["part:310011"])) == []


def _broken(change):
    d = dossier("sup:70130", ["part:310011"])
    change(d)
    return validate(d)


@pytest.mark.parametrize(
    "change, needle",
    [
        (lambda d: d.pop("signals"), "missing"),
        (lambda d: d.update(extra=1), "unknown"),
        (lambda d: d.update(schema_version=2), "schema_version"),
        (lambda d: d.update(coverage="partial"), "coverage"),
        (lambda d: d["economics"].update(cost_of_money=0.0), "cost_of_money"),
        (lambda d: d["economics"].update(cash_pressure="severe"), "cash_pressure"),
        (lambda d: d["economics"].update(archetype="pirate"), "archetype"),
        (
            lambda d: d["signals"].append({"kind": "gossip", "strength": 1, "evidence": ["doc:1"], "excerpt": ""}),
            "kind",
        ),
        (
            lambda d: d["signals"].append({"kind": "cash_short", "strength": 4, "evidence": ["doc:1"], "excerpt": ""}),
            "strength",
        ),
        (
            lambda d: d["signals"].append({"kind": "cash_short", "strength": 1, "evidence": ["b", "a"], "excerpt": ""}),
            "sorted",
        ),
        (
            lambda d: d["parts"]["part:310011"].update(floor_estimate={"value": 5, "low": 6, "high": 7, "basis": "x"}),
            "band",
        ),
        (
            lambda d: d["parts"]["part:310011"]["alternatives"].append({"supplier_id": "sup:1", "private": False}),
            "private",
        ),
        (lambda d: d["standard_terms"].update(source="gossip"), "source"),
        (lambda d: d["economics"].update(we_pay_late_days=float("nan")), "finite"),
    ],
)
def test_the_validator_reports_every_breach(change, needle):
    errors = _broken(change)
    assert errors and any(needle in e for e in errors), errors
