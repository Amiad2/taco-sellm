"""The lab: the arena's suppliers simulated locally, to test buyer strategies for free.

    from sellm.lab import LocalTable, twins
    from arena_kit.play import play
    scenario = twins.load()[0]
    result = play(LocalTable(scenario, facts, seed=1), scenario.case["case_id"], agent)

Command line: `uv run python -m sellm.lab --help`. How far to trust it: docs/PLAN.md section 6.
"""

from .persona import Persona, best_package, calibrate
from .table import LocalTable, Scenario

__all__ = ["LocalTable", "Persona", "Scenario", "best_package", "calibrate"]
