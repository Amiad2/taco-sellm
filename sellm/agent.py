"""Our buyer agent, played by `arena play|run --agent sellm`. Replace `make_agent` to change it."""

from sellm.lab.strategies import Calculator

# Best variant of the first lab search (runs/lab/20261010-1632-search-first/report.md, #1), except
# tone: warm and neutral tie in the lab, and the FAQ's P01 recording shows tone moves real suppliers.
KNOBS = dict(
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


def make_agent(package=None):
    """A fresh agent for one case: it keeps per-case state."""
    return Calculator(package, **KNOBS)
