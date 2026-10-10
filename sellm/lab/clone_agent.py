"""sellm/lab/clone_agent.py - Isolated experimental agent for local feedback loop.

DO NOT touch sellm/agent.py! This file is an independent experimental clone that
subclasses Calculator and integrates sellm.intel dossiers and signal-driven
heuristics.
"""

import math

from arena_kit.play import standing
from sellm.intel import dossier
from sellm.lab.strategies import DEFAULTS, Calculator

CLONE_DEFAULTS = {
    **DEFAULTS,
    "structure": "joint",
    "use_should_cost": True,
    "floor_guess": 0.85,
    "open_below": 0.08,
    "steps": 7,
    "shape": 0.85,
    "sheets": 2,
    "take_alternative": True,
    "after_final": "accept",
    "claims": "bank",
    "tone": "warm",
    "accept_gap": 0.005,
    "adaptive": True,
    "rel_estimate": "max",
    "rel_margin": 0.97,
    "hold_others": True,
    "open_guard": None,  # None: at most 23 % below its standing offer (v3); a share: at most that below our floor
}


class CloneAgent(Calculator):
    """Experimental Clone Agent v3 with intel-aware heuristics and opening bounds. Its cheaper second sheet
    is sent back by the Calculator's take_alternative (a decide() override meant to do it never fired: it
    read res['term_sheets'] where the move keeps them under res['message'])."""

    def __init__(self, package=None, **knobs):
        super().__init__(package=package, **{**CLONE_DEFAULTS, **knobs})
        self.dossiers = {}
        self.name = "clone_agent_v3 " + " ".join(f"{k}={v}" for k, v in knobs.items())

    def _get_dossier(self, case, sid, events):
        """Fetch and cache Intel dossier for the thread's supplier."""
        if sid not in self.dossiers:
            d = dossier(sid, case.get("parts", []), case=case, opening=events, package=self.package)
            self.dossiers[sid] = d if isinstance(d, dict) else {}
        return self.dossiers[sid]

    def _estimate(self, case, sid, events):
        """Intel-enhanced supplier cost and interest rate estimate."""
        est = super()._estimate(case, sid, events)
        if est is None:
            return None

        d = self._get_dossier(case, sid, events)
        econ = d.get("economics") or {}
        cost_of_money = econ.get("cost_of_money")
        if cost_of_money and cost_of_money > 0:
            est["interest_rate"] = cost_of_money

        floors = []
        parts = d.get("parts") or {}
        for p_info in parts.values():
            if not isinstance(p_info, dict):
                continue
            fe = p_info.get("floor_estimate") or {}
            if isinstance(fe, dict):
                val = fe.get("value")
                if val and val > 0:
                    floors.append(val)
        if floors:
            est["full_cost"] = max(est["full_cost"], sum(floors))

        return est

    def plan(self, case, sid, events, force=None):
        """Intel-driven negotiation plan per thread."""
        p = super().plan(case, sid, events, force=force)
        d = self._get_dossier(case, sid, events)

        signals_raw = d.get("signals") or []
        signals = {s.get("kind"): s.get("strength", 1) for s in signals_raw if isinstance(s, dict)}

        econ = d.get("economics") or {}
        archetype = econ.get("archetype", "other")

        # Dynamic open_below strategy
        open_below = self.k["open_below"]
        if "capacity_tight" in signals or "margin_floor" in signals or archetype in ("monopolist", "trader"):
            open_below = 0.035
        elif "wants_volume" in signals or "informal_costing" in signals:
            open_below = 0.10

        standing_id, terms = standing(events)
        std = p["std"]
        val_now = self._sup_value(case, std, terms)

        part_id = case["parts"][0] if case.get("parts") else None
        p_info = (d.get("parts") or {}).get(part_id) or {} if part_id else {}
        fe = (p_info.get("floor_estimate") or {}) if isinstance(p_info, dict) else {}
        floor_val = fe.get("value") if isinstance(fe, dict) else None

        floor_target = floor_val if (floor_val and floor_val > 0) else (val_now * self.k["floor_guess"])
        p_floor = self._price_at(case, std, p["structure"], floor_target)
        p_limit = self._price_at(case, std, p["structure"], val_now)

        if math.isfinite(p_floor) and p_floor > 0:
            p_raw = min(p_floor * (1 - open_below), p_limit * 0.97)
            if self.k.get("open_guard") is None:
                # v3: never more than 23 % below its standing offer (protects supplier patience)
                p["p_open"] = max(p_raw, p_limit * 0.77)
            else:
                # never more than open_guard below our floor estimate: further down offends (lab lowball penalty)
                p["p_open"] = min(max(p_raw, p_floor * (1 - self.k["open_guard"])), p_limit * 0.97)

        return p
