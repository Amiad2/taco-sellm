# ruff: noqa: E501
"""Tool-use audit: a negotiator that records, for every decision, which tools it really read.

Why: a missing dossier, a swallowed exception or a calculator that was never called does not
crash anything - the agent just plays a worse move. This wrapper makes that visible: one JSON line
per decision in `$SELLM_TRACE` (default runs/logs/trace.jsonl) with

- `dossier`   coverage (full | thin | case_only), cash pressure, cost of money, archetype, signal kinds,
              the running contract's payment days, floor estimate, how many `citable` facts it holds;
- `tools`     every call of `sellm.calculator` (packages, price_for, supplier_cost, recent_low) and of
              `sellm.intel.dossier`, with sizes and exceptions;
- `aim`       the price target and where it came from (cost:<id> of its own plant, or a prior);
- `kind`, `sheets`, `arguments`, `flags` of the move; `errors` (the negotiator's own rescue path).

`python -m sellm.audit runs/logs/trace.jsonl` prints one table per case and flags what was not used.
"""

import json
import os
import sys
import threading
import time

from . import calculator, llm
from .negotiator import Negotiator, Thread

_TLS = threading.local()
_LOCK = threading.Lock()


def _note(**row):
    rec = getattr(_TLS, "rec", None)
    if rec is not None:
        rec.setdefault("tools", []).append(row)


def _size(out):
    try:
        return len(out)
    except TypeError:
        return None


def _wrap(module, name):
    orig = getattr(module, name)
    if getattr(orig, "_audited", False):
        return

    def wrapper(*a, **k):
        try:
            out = orig(*a, **k)
        except Exception as e:
            _note(tool=f"{module.__name__.split('.')[-1]}.{name}", error=repr(e)[:160])
            raise
        row = {"tool": f"{module.__name__.split('.')[-1]}.{name}", "n": _size(out)}
        if name == "supplier_cost" and isinstance(out, dict):
            row["cost_basis"] = (out.get("cost") or {}).get("basis")
            row["evidence"] = [e["kind"] for e in out.get("evidence", [])]
        if name == "packages" and out:
            row["best"] = {"c": round(out[0][0]), "structure": out[0][1]}
        _note(**row)
        return out

    wrapper._audited = True
    setattr(module, name, wrapper)


for _name in ("packages", "price_for", "supplier_cost", "recent_low", "levers"):
    _wrap(calculator, _name)

try:  # the dossier is imported lazily inside Negotiator.intel(): wrap the package attribute
    from . import intel as _intel

    _orig_dossier = _intel.dossier

    def _audited_dossier(*a, **k):
        try:
            out = _orig_dossier(*a, **k)
        except Exception as e:
            _note(tool="intel.dossier", error=repr(e)[:160])
            raise
        _note(tool="intel.dossier", coverage=(out or {}).get("coverage"), warnings=((out or {}).get("warnings") or [])[:3])
        return out

    _intel.dossier = _audited_dossier
except Exception:  # no intel package: the audit then shows no dossier calls, which is the finding
    pass


class Audited(Negotiator):
    """The negotiator, unchanged, with a trace of what it used for every decision."""

    def __init__(self, package=None, trace=None, tag="", **knobs):
        super().__init__(package, **knobs)
        self.trace_path = trace or os.environ.get("SELLM_TRACE") or "runs/logs/trace.jsonl"
        self.tag = tag
        self._last_draft = None

    def message(self, case, threads, draft):
        self._last_draft = draft
        return super().message(case, threads, draft)

    def decide(self, case, threads, focus=None):
        rec = {"t": round(time.time(), 1), "tag": self.tag, "case": case.get("case_id"), "focus": focus}
        before = dict(self.stats)
        llm_before = (llm.STATS["calls"], llm.STATS["failed"])
        _TLS.rec, self._last_draft = rec, None
        try:
            out = super().decide(case, threads, focus)
        finally:
            _TLS.rec = None
        sid = (out or {}).get("supplier_id") or focus
        events = threads.get(sid, [])
        rec["sid"] = sid
        rec["round"] = sum(1 for m in events if m.get("from") == "buyer")
        msg = (out or {}).get("message") or {}
        rec["action"] = (msg.get("action") or {}).get("type")
        rec["sheets"] = [s.get("terms") for s in msg.get("term_sheets") or []]
        rec["errors"] = self.stats["errors"] - before["errors"]
        rec["llm_calls"] = llm.STATS["calls"] - llm_before[0]
        rec["llm_failed"] = llm.STATS["failed"] - llm_before[1]
        if self._last_draft:
            d = self._last_draft
            rec["kind"] = d.get("kind")
            rec["arguments"] = d.get("arguments")
            rec["flags"] = d.get("flags")
        try:
            view = Thread(case, sid, events)
            found = self.intel(case, view)
            eco = found.get("economics") or {}
            parts = found.get("parts") or {}
            first = next(iter(parts.values()), {}) if parts else {}
            rec["dossier"] = {
                "coverage": found.get("coverage"),
                "cash": eco.get("cash_pressure"),
                "cost_of_money": eco.get("cost_of_money"),
                "archetype": eco.get("archetype"),
                "signals": [(s["kind"], s["strength"]) for s in found.get("signals", [])],
                "contract_payment_days": (found.get("contract") or {}).get("payment_days"),
                "floor_estimate": (first.get("floor_estimate") or {}).get("value"),
                "citable": len(found.get("citable") or []),
            }
            aim = self.aim(case, view, self.opening_structure(case, view))
            rec["aim"] = {"target": round(aim["target"], 3), "source": aim["source"], "full_cost": round(aim["full_cost"], 3)}
        except Exception as e:  # the audit must never break a move
            rec["audit_error"] = repr(e)[:160]
        with _LOCK:
            os.makedirs(os.path.dirname(self.trace_path) or ".", exist_ok=True)
            with open(self.trace_path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(rec, default=str) + "\n")
        return out


def report(path):
    rows = [json.loads(x) for x in open(path, encoding="utf-8") if x.strip()]
    by_case = {}
    for r in rows:
        by_case.setdefault(r["case"], []).append(r)
    bad = 0
    for case, recs in sorted(by_case.items()):
        first_asks = [r for r in recs if r.get("kind") == "ask" and r.get("round") == 0]
        calls = [t for r in recs for t in r.get("tools", [])]
        errs = [t for t in calls if t.get("error")]
        cov = {r["dossier"]["coverage"] for r in recs if r.get("dossier")}
        packages = sum(1 for t in calls if t["tool"] == "calculator.packages")
        doss = sum(1 for t in calls if t["tool"] == "intel.dossier")
        cites = sum(1 for r in recs for a in (r.get("arguments") or []))
        errors = sum(r.get("errors", 0) for r in recs)
        flags = []
        if "full" not in cov:
            flags.append("NO FULL DOSSIER")
        if not packages and first_asks:
            flags.append("CALCULATOR NOT CALLED")
        if errs or errors:
            flags.append("ERRORS")
        bad += bool(flags)
        print(f"{case:10} decisions {len(recs):3}  dossier {sorted(c for c in cov if c)}  dossier calls {doss:3}  packages() calls {packages:3}  arguments {cites:2}  rescue {errors}  {' '.join(flags) or 'ok'}")
    return bad


if __name__ == "__main__":
    sys.exit(1 if report(sys.argv[1] if len(sys.argv) > 1 else "runs/logs/trace.jsonl") else 0)
