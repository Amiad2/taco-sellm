"""Our buyer agent, played by `arena play|run --agent sellm`. Replace `make_agent` to change it."""

import os

from sellm.endgame import Persistent

# What `--agent sellm` plays on top of the defaults of the negotiator (sellm/negotiator.py DEFAULTS)
# and of its persistence layer (sellm/endgame.py DEFAULTS). Each rule was measured on practice
# (experiments/PERSISTENCE.md, experiments/P02-ARGUMENTS.md, experiments/LEDGER.md): the first two change
# P01 (0.915 -> 0.969) and D01's accept, the third P02 (jonathans_branch), the fourth P18 and P05
# (omars_branch), and no other move in the recorded sessions.
KNOBS = dict(
    past_target=True,  # with a relationship term: keep asking past our target while the supplier still moves
    fast_pay=True,  # a supplier the dossier calls short of cash is asked for the fastest payment
    # With a relationship term, where the supplier quotes a fixed price at its cost and an index clause is
    # negotiable: the clause as a second offer, at the price where our total cost is lowest (P02 0.531 -> 0.725,
    # no other recorded case changes; experiments/P02-ARGUMENTS.md)
    clause_offer=True,
    # A cost-driver index that fell >= 2 % from its peak of the last 12 months is cited (AS-14404 -5.5 % since
    # 2026-06), except to a supplier whose material is hedged (dossier material_hedged). P18 0.467 -> 0.520,
    # P08 unchanged (without the guard 0.438: 'not our reality'); experiments/LEDGER.md E2, E2g
    idx_recent=2.0,
)

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
    """A fresh agent for one case. `knobs` override the defaults (the lab passes them).

    `SELLM_LLM=shadow|apply` adds the LLM (sellm/advisor.py): it writes the e-mail around the moves
    code has fixed and gives a verdict with a confidence on the supplier's standing offer - logged
    only (`shadow`) or acted on within guards (`apply`). Without it no LLM is called."""
    mode = os.environ.get("SELLM_LLM", "").strip().lower()
    if mode in ("shadow", "apply"):
        from sellm.advisor import Advised

        return Advised(package, writer=writer, verdict=mode, **{**KNOBS, **knobs})
    return Persistent(package, writer=writer or os.environ.get("SELLM_WRITER") or None, **{**KNOBS, **knobs})
