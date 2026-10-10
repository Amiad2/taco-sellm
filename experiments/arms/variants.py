"""Agent variants for the practice-arena experiments (module:function for `python -m sellm.evalrun`)."""

from .audit import Audited


def a1(package=None):
    """Reference: the negotiator as committed in 19b339f (calculator packages, dossier cash/cost of money)."""
    return Audited(package, tag="a1")


def bank(package=None):
    """a1 + the argument bank (sellm.claims.arguments over the dossier's citable facts)."""
    return Audited(package, tag="bank", bank=True)


def signals(package=None):
    """a1 + the dossier's signals set the share of the opening we aim at."""
    return Audited(package, tag="signals", signals=True)


def both(package=None):
    return Audited(package, tag="both", bank=True, signals=True)


def bank2(package=None):
    """bank, but one fact per topic and no ppm sentences (they came back contradicted)."""
    return Audited(package, tag="bank2", bank=True, ppm="skip", one_per_topic=True)


def ppmfix(package=None):
    """bank2 with ppm sentences written without the thousands comma ("2376 ppm")."""
    return Audited(package, tag="ppmfix", bank=True, ppm="plain", one_per_topic=True)


def bank2s(package=None):
    """bank2 + the dossier's signals set the share we aim at."""
    return Audited(package, tag="bank2s", bank=True, ppm="skip", one_per_topic=True, signals=True)


def clause(package=None):
    """bank2s + where the supplier insists on an index clause, ask its widest deadband."""
    return Audited(package, tag="clause", bank=True, ppm="skip", one_per_topic=True, signals=True, clause=True)


def nodossier(package=None):
    """bank2s without the dossier: what a supplier we hold no data on looks like (hidden cases)."""
    agent = Audited(package, tag="nodossier", bank=True, ppm="plain", one_per_topic=True, signals=True)
    agent.k["dossier"] = False  # not a constructor knob: Negotiator.__init__ takes `dossier` as its own parameter
    return agent


def full(package=None):
    """The candidate: bank with ppm sentences fixed, one fact per topic, dossier signals."""
    return Audited(package, tag="full", bank=True, ppm="plain", one_per_topic=True, signals=True)
