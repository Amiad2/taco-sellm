"""Our buyer agent, played by `arena play|run --agent sellm`. Replace `make_agent` to change it."""

import os

from sellm.negotiator import Negotiator

# Overrides of the negotiator's defaults (sellm/negotiator.py DEFAULTS). Empty: the defaults are the
# values measured on the real sandbox (docs/LOG.md Sat 18:22).
KNOBS = dict()

# The best Calculator variant of the first lab search (runs/lab/20261010-1632-search-first/report.md,
# #1), tone warm. Kept as the control arm of experiments/ab_sandbox.py: on the real sandbox case D01
# it scored 0.789, a scripted moderate path 0.95 (docs/LOG.md Sat 18:22).
CALC_KNOBS = dict(
    structure="joint",
    guess_rate=0.2,
    floor_guess=0.85,
    use_should_cost=False,
    open_below=0.1,
    steps=8,
    shape=0.75,
    sheets=3,
    take_alternative=False,
    after_final="accept",
    claims="bank",
    tone="warm",
    ask_breakdown=False,
    accept_gap=0.01,
)


def make_agent(package=None, writer=None, **knobs):
    """A fresh agent for one case. `writer`: template (default) or llm; `SELLM_WRITER` sets it for a
    run. `knobs` override the negotiator's defaults (the lab passes them)."""
    return Negotiator(package, writer=writer or os.environ.get("SELLM_WRITER") or None, **{**KNOBS, **knobs})
