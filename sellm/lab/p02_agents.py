"""Five dial settings for the real P02 test (Sat 22:50): `--agent sellm.lab.p02_agents:a1` etc."""

from .dials import DialNegotiator

AGGRO = dict(horizon=3, keep_below=0.0, pace=0.3)  # the lab's best aggression for P02 (+0.055 ± 0.019)
VARIANTS = {
    "a1": dict(AGGRO),
    "a2": dict(AGGRO, n_args=2),
    "a3": dict(AGGRO, n_args=3, arg_order="history"),
    "a4": dict(AGGRO, n_args=2, tone="empathy"),
    "a5": dict(n_args=2, arg_order="history"),
}


def _make(name):
    def make(package=None):
        return DialNegotiator(package, **VARIANTS[name])

    make.__name__ = name
    return make


for _n in VARIANTS:
    globals()[_n] = _make(_n)
