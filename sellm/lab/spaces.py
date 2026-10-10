"""Knob spaces the lab can search, per agent. `calc`: the lab's Calculator; `negotiator`: group A's
negotiator behind `--agent sellm` (sellm/negotiator.py DEFAULTS), whose make_agent takes knobs."""

from .strategies import SPACE as CALC

NEGOTIATOR = {
    "open_below": [0.02, 0.04, 0.06, 0.08, 0.10],
    "rounds_to_floor": [3, 4, 5, 6, 7, 8],
    "keep_below": [0.0, 0.003, 0.006, 0.01, 0.02],
    "floor_share": [None, 0.82, 0.86, 0.90, 0.945],
    "rate_guess": [0.06, 0.08, 0.12, 0.20],
    "claims": ["none", "bank"],
    "max_holds": [0, 1, 2],
}
SPACES = {"calc": CALC, "negotiator": NEGOTIATOR}
AGENTS = {"calc": "calc", "negotiator": "sellm.agent:make_agent"}


def space_for(agent):
    """The knob space of an agent name (calc, sellm.agent:make_agent, or a space name)."""
    if agent in SPACES:
        return SPACES[agent]
    return NEGOTIATOR if agent.startswith("sellm.agent") else CALC


def sample(rng, space):
    return {k: rng.choice(v) for k, v in space.items()}
