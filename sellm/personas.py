# ruff: noqa: E501  (table text)
"""The supplier personas the agent distinguishes, and what each changes in its play.

Nothing here decides a move. The rules live in `sellm/negotiator.py` (`cash`, `share`) and
`sellm/endgame.py` (`fast_pay`); this file gives them names, says for a supplier which ones apply
and why (the dossier's evidence), and what the agent does because of it - for the log of a run, for
the pitch, and for anyone who asks "why did the agent write that?". tests/test_personas.py checks
that the description and the first ask the agent really sends agree.

    uv run python -m sellm.personas            all suppliers we hold a dossier on
    uv run python -m sellm.personas P01 P05    the suppliers of played cases, with the first ask

A supplier has one persona for cash and at most one for price:

| Persona | The dossier says | The agent | Measured on practice |
|---|---|---|---|
| short_of_cash | a cash_short signal, or cash pressure medium / high | asks for the fastest payment in its first ask | P01 +0.016, P05 |
| relaxed_about_cash | cash pressure low | asks for the latest payment | granted in P02, P03, P04, P07, P08, P18 |
| fixed_list_price | list_price_fixed (2+) or margin_floor | expects the end at 96 % of the opening: opens close to its price | P11 +0.07, P04 equal |
| hungry_for_volume | wants_volume (2+), and no fixed list price | expects the end at 84 %: opens deeper | P18 +0.04 |
| unknown | no dossier beyond the case | sends two offers that cost us the same, quoted and latest payment days | about 3.5 points below a known supplier |
"""

PERSONAS = {
    "short_of_cash": (
        "short of cash",
        "the fastest payment in the first ask: what it gives for it is worth more than the days cost us",
    ),
    "relaxed_about_cash": ("relaxed about cash", "the latest payment in the first ask"),
    "fixed_list_price": (
        "fixed list price or margin at its floor",
        "we expect the end near its opening (96 %) and open close to it; the points are in the terms and in checked facts",
    ),
    "hungry_for_volume": (
        "hungry for volume",
        "we expect the end deeper (84 % of its opening) and open there, with the long commitment up front",
    ),
    "unknown": (
        "no data on it",
        "two offers that cost us the same (quoted and latest payment days); we follow the one it answers",
    ),
}
TAGS = ("approval_ladder", "capacity_tight")  # read by nobody yet: listed so that the gap is visible


def traits(dossier):
    """[(persona, evidence)] for one dossier, in the order cash, price. The same thresholds as the rules."""
    if not dossier or dossier.get("coverage") != "full":
        return [("unknown", "the dossier knows the case only")]
    eco = dossier.get("economics") or {}
    signals = {}
    for sig in dossier.get("signals") or []:
        signals.setdefault(sig.get("kind"), sig)
    strength = {kind: (sig.get("strength") or 0) for kind, sig in signals.items()}

    def why(kind):
        sig = signals.get(kind) or {}
        text = (sig.get("excerpt") or "").strip()
        refs = ", ".join((sig.get("evidence") or [])[:2])
        return f"{kind} {strength.get(kind)}: {text[:110]}" + (f" ({refs})" if refs else "")

    out = []
    pressure = eco.get("cash_pressure")
    if "cash_short" in signals or pressure in ("medium", "high"):
        out.append(
            (
                "short_of_cash",
                why("cash_short")
                if "cash_short" in signals
                else f"cash pressure {pressure} ({eco.get('cost_of_money_basis')})",
            )
        )
    elif pressure == "low":
        out.append(
            (
                "relaxed_about_cash",
                f"cash pressure low, cost of money {eco.get('cost_of_money')} ({eco.get('cost_of_money_basis')})",
            )
        )
    if strength.get("list_price_fixed", 0) >= 2 or strength.get("margin_floor", 0) >= 1:
        out.append(
            (
                "fixed_list_price",
                why("list_price_fixed" if strength.get("list_price_fixed", 0) >= 2 else "margin_floor"),
            )
        )
    elif strength.get("wants_volume", 0) >= 2:
        out.append(("hungry_for_volume", why("wants_volume")))
    return out or [("unknown", "no cash reading in the dossier")]


def describe(dossier):
    """{"personas": [...], "tags": [...], "lines": [readable lines]} for a log or a slide."""
    found = traits(dossier)
    tags = [k for k in TAGS if any(s.get("kind") == k for s in (dossier or {}).get("signals") or [])]
    lines = [f"{PERSONAS[p][0]} - because: {evidence}. So: {PERSONAS[p][1]}." for p, evidence in found]
    return {"personas": [p for p, _ in found], "tags": tags, "lines": lines}


def main(argv=None):
    import collections
    import glob
    import json
    import os
    import sys
    from pathlib import Path

    from arena_kit.cli import load_env

    from .intel import dossier

    load_env()
    root = Path(__file__).resolve().parent
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        count = collections.Counter()
        for path in sorted((root / "dossiers").glob("7*.json")):
            d = dossier(f"sup:{path.stem}")
            info = describe(d)
            count[" + ".join(info["personas"])] += 1
            name = (d.get("identity") or {}).get("name") or ""
            print(f"sup:{path.stem} {name[:34]:34s} {' + '.join(info['personas']):38s} {', '.join(info['tags'])}")
        print()
        for combo, n in count.most_common():
            print(f"{n:3d}  {combo}")
        return 0
    from arena_kit.data import DataPackage

    from .agent import make_agent
    from .negotiator import Thread

    data = os.environ.get("ARENA_DATA", "data/package")
    package = DataPackage(data) if os.path.isdir(data) else None
    for name in args:
        files = sorted(glob.glob(f"runs/*/{name.split(':')[-1]}/*.json"))
        if not files:
            print(f"{name}: no saved session in runs/")
            continue
        record = json.loads(open(files[-1], encoding="utf-8").read())
        case = record["case"]
        threads = {s: t["messages"][:1] for s, t in record["threads"].items()}
        print(f"{case['case_id']}  {case.get('title', '')}")
        for sid in threads:
            agent = make_agent(package)
            message = agent.decide(case, threads, focus=sid)["message"]
            view = Thread(case, sid, threads[sid])
            info = describe(agent.intel(case, view))
            print(
                f"  {sid}: {' + '.join(info['personas'])}" + (f"  [{', '.join(info['tags'])}]" if info["tags"] else "")
            )
            for line in info["lines"]:
                print(f"      {line}")
            quoted = view.filled(view.opening["term_sheets"][0]["terms"])
            for sheet in message.get("term_sheets") or []:
                print(f"      first ask: {sheet['terms']}   (it quoted {quoted})")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
