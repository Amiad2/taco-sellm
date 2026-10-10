"""Buyer strategies to screen in the lab. `Calculator` decides with numbers only - no LLM, so
thousands of negotiations cost nothing - and has knobs for what we want to compare:

  structure      keep: the supplier's terms | buyer: the cheapest terms for us at the same price |
                 joint: the cheapest terms for us at the same value to the supplier (needs a guess
                 of its cost of money)
  floor_guess    our estimate of its floor as a share of its opening (when no should-cost exists)
  open_below     we open this share below that estimate
  steps, shape   planned concessions up to its standing price; shape 1 equal, <1 shrinking, >1 growing
  sheets         term sheets per e-mail (extra ones: other terms at the same cost to us)
  after_final    accept | hold (one holding message, then accept) | push (one more lower ask)
  claims         none | cost (the should-cost estimate once) | bank (one new checked figure per round)
  tone           warm | neutral | hard (ultimatum wording)
  adaptive       shrink our step when the supplier gives back much less than it (its per-round limit
                 binds), so our price stays low for more rounds
  learn          when the supplier counters on one of our variant sheets, ask on that structure
  hold_others    with one loop per thread: keep a finished thread alive with a holding e-mail while
                 the others still negotiate (a supplier left waiting at its final offer may withdraw)

It never uses the lab's hidden numbers: only the case file, the thread and the data package, so
the same object can play the arena. `decide(case, threads)` is the kit's agent interface.
"""

import math

from arena_kit.cost import complete_offer, must_haves_ok, supplier_value, total_cost
from arena_kit.docs import standard_terms
from arena_kit.play import latest, live_threads, moves_left, standing

from .persona import structures

DEFAULTS = dict(
    structure="joint",
    guess_rate=0.08,
    floor_guess=0.88,
    use_should_cost=True,
    open_below=0.03,
    steps=5,
    shape=1.0,
    sheets=1,
    take_alternative=True,
    after_final="accept",
    claims="cost",
    tone="warm",
    ask_breakdown=False,
    accept_gap=0.002,
    adaptive=False,
    learn=False,
    hold_others=True,
    mirror_guess=0.6,
)

TONE = {
    "warm": "Thank you for your offer and for the reliable cooperation over the past years.",
    "neutral": "Thank you for your offer.",
    "hard": "Your price is unacceptable. Otherwise we will move to another supplier.",
}


class Calculator:
    def __init__(self, package=None, **knobs):
        self.k = {**DEFAULTS, **knobs}
        self.package = package
        self.plans, self.cited, self.held, self.pushed, self.sent_back = {}, set(), set(), set(), set()
        self.name = "calc " + " ".join(f"{k}={v}" for k, v in knobs.items())

    # -- the numbers ---------------------------------------------------------------------------
    def _std(self, case, events, sheet_terms):
        std = {**{k: v for k, v in sheet_terms.items() if k != "unit_price"}, **standard_terms(events)}
        from arena_kit.cost import closing_terms

        out = closing_terms(case, std, std)
        out.pop("unit_price", None)
        return out

    def _sup_value(self, case, std, terms):
        return supplier_value(case, terms, {"standard": std, "interest_rate": self.k["guess_rate"]})

    def _price_at(self, case, std, structure, value):
        v0 = self._sup_value(case, std, {**structure, "unit_price": 0.0})
        v1 = self._sup_value(case, std, {**structure, "unit_price": 1.0})
        return (value - v0) / (v1 - v0) if v1 > v0 else math.inf

    def _should_cost(self, case):
        if not (self.package and self.k["use_should_cost"]):
            return None
        for part in case["parts"]:
            fact = self.package.lookup(f"cost:{part.split(':', 1)[1]}")
            if fact and fact.get("unit_cost"):
                return f"cost:{part.split(':', 1)[1]}", fact["unit_cost"]
        return None

    def plan(self, case, sid, events, force=None):
        """Once per thread: the structure we ask for, our floor estimate and the price path."""
        _, terms = standing(events)
        std = self._std(case, events, terms)
        value_now = self._sup_value(case, std, terms)
        candidates = [s for s in structures(case) if must_haves_ok(case, {**s, "unit_price": 1.0}, std)]
        current = {k: v for k, v in complete_offer(case, terms).items() if k != "unit_price"}
        if force is not None:
            structure = force
        elif self.k["structure"] == "keep" or not candidates:
            structure = current
        elif self.k["structure"] == "buyer":
            structure = min(candidates, key=lambda s: total_cost(case, {**s, "unit_price": terms["unit_price"]}, std))
        else:

            def joint(s):
                p = self._price_at(case, std, s, value_now)
                return total_cost(case, {**s, "unit_price": p}, std) if math.isfinite(p) and p > 0 else math.inf

            structure = min(candidates, key=joint)
        structure = {
            k: v for k, v in complete_offer(case, {**structure, "unit_price": 1.0}).items() if k != "unit_price"
        }
        sc = self._should_cost(case)
        floor_value = sc[1] if sc else self.k["floor_guess"] * value_now
        p_floor = self._price_at(case, std, structure, floor_value)
        p_limit = self._price_at(case, std, structure, value_now)
        p_open = min(p_floor * (1 - self.k["open_below"]), p_limit * 0.97)
        old = self.plans.get(sid, {})
        self.plans[sid] = dict(
            std=std, structure=structure, p_open=p_open, p_limit=p_limit, sent=old.get("sent", 0), sc=sc,
            last_price=None, last_step=None, supplier_eq=None, learned=old.get("learned", False),
        )  # fmt: skip
        return self.plans[sid]

    def _supplier_eq(self, case, plan, terms):
        """The supplier's standing offer as a price on our structure, at equal value to it."""
        return self._price_at(case, plan["std"], plan["structure"], self._sup_value(case, plan["std"], terms))

    def ask(self, plan, n):
        steps, shape = max(1, self.k["steps"]), self.k["shape"]
        frac = min(1.0, (n / steps) ** shape)
        return round(plan["p_open"] + (plan["p_limit"] - plan["p_open"]) * frac, 2)

    # -- the decision --------------------------------------------------------------------------
    def decide(self, case, threads, focus=None):
        """The kit's interface; `focus` (one loop per thread) asks for a move in that thread."""
        live = live_threads(threads)
        alt = case["buyer"].get("alternative") or {}
        c_alt = total_cost(case, alt["terms"]) if alt.get("terms", {}).get("unit_price") else math.inf

        def c_of(sid):
            sheet_id, terms = standing(threads[sid])
            if not sheet_id:
                return math.inf
            std = standard_terms(threads[sid])
            return total_cost(case, terms, std) if must_haves_ok(case, terms, std) else math.inf

        costs = {sid: c_of(sid) for sid in live}
        best = min(live, key=lambda s: costs[s]) if live else None
        # a deal worse than the cheapest opening scores 0, like no deal: never take one
        openings = []
        for events in threads.values():
            first = next((m for m in events if m.get("from") != "buyer" and m.get("term_sheets")), None)
            if first:
                terms, std = first["term_sheets"][0]["terms"], standard_terms(events)
                if must_haves_ok(case, terms, std):
                    openings.append(total_cost(case, terms, std))
        c_open = min(openings) if openings else math.inf

        def accept(sid):
            if sid is None or costs[sid] >= c_alt or costs[sid] >= c_open:
                return {"supplier_id": (live or list(threads))[0], "message": {"action": {"type": "walk_away"}}}
            return {
                "supplier_id": sid,
                "message": {"action": {"type": "accept", "term_sheet_id": standing(threads[sid])[0]}},
            }

        agreed = [s for s in live if latest(threads[s]).get("status") == "agreed" and costs[s] < math.inf]
        if agreed:
            return accept(min(agreed, key=lambda s: costs[s]))
        movable = [
            s for s in live if moves_left(case, threads[s]) > 0 and not self._done(case, s, threads[s], costs[s])
        ]
        if not movable:
            return accept(best)
        if focus is not None and focus in live:
            if focus in movable:
                return self._move(case, focus, threads, costs, best)
            if self.k["hold_others"] and moves_left(case, threads[focus]) > 1 and focus == best:
                return self._hold(case, focus)  # the best offer stays alive while the others go on
        sid = min(movable, key=lambda s: (sum(m.get("from") == "buyer" for m in threads[s]), costs[s]))
        return self._move(case, sid, threads, costs, best)

    def _hold(self, case, sid):
        body = "Dear Sir or Madam,\n\nThank you, we are reviewing your offer internally and will revert shortly."
        return {"supplier_id": sid, "message": {"subject": f"Re: {case['title']}", "body": body, "term_sheets": []}}

    def _done(self, case, sid, events, cost):
        """Nothing more to get from this thread: take or leave its standing offer."""
        status = latest(events).get("status")
        if status == "final_offer":
            mode = self.k["after_final"]
            if mode == "hold" and sid not in self.held:
                return False
            if mode == "push" and sid not in self.pushed:
                return False
            return True
        plan = self.plans.get(sid)
        if plan is None:
            return False
        nxt = self.ask(plan, plan["sent"])
        _, terms = standing(events)
        ours = total_cost(case, {**plan["structure"], "unit_price": nxt}, plan["std"])
        return cost <= ours * (1 + self.k["accept_gap"])

    def _move(self, case, sid, threads, costs, best):
        events = threads[sid]
        plan = self.plans.get(sid) or self.plan(case, sid, events)
        status = latest(events).get("status")
        lines = [TONE[self.k["tone"]]]
        if status == "final_offer" and self.k["after_final"] == "hold":
            self.held.add(sid)
            return self._hold(case, sid)
        if status == "final_offer":
            self.pushed.add(sid)
        # a cheaper second sheet from the supplier: send its terms back, it agrees, we accept
        sheets = latest(events).get("term_sheets") or []
        if self.k["take_alternative"] and len(sheets) > 1 and sid not in self.sent_back:
            std = standard_terms(events)
            alt_terms = sheets[1]["terms"]
            c_alt_sheet = total_cost(case, alt_terms, std) if must_haves_ok(case, alt_terms, std) else math.inf
            if c_alt_sheet < costs[sid]:
                nxt = self.ask(plan, plan["sent"])
                ours = total_cost(case, {**plan["structure"], "unit_price": nxt}, plan["std"])
                if c_alt_sheet <= ours * (1 + self.k["accept_gap"]):
                    self.sent_back.add(sid)
                    return self._mail(
                        case,
                        sid,
                        ["We can accept your alternative package as offered."],
                        [complete_offer(case, alt_terms)],
                    )
        # learn: the supplier countered on one of our variants - it values that structure
        _, terms = standing(events)
        if self.k["learn"] and not plan["learned"] and plan["sent"] > 0 and terms:
            theirs = {k: v for k, v in complete_offer(case, terms).items() if k != "unit_price"}
            if theirs != plan["structure"] and must_haves_ok(case, {**theirs, "unit_price": 1.0}, plan["std"]):
                plan = self.plan(case, sid, events, force=theirs)
                plan["learned"] = True
        # our price path; in an RFQ the best rival offer is our argument
        price = self.ask(plan, plan["sent"])
        eq = self._supplier_eq(case, plan, terms) if terms.get("unit_price") else math.inf
        if self.k["adaptive"] and plan["last_price"] is not None and plan["supplier_eq"] is not None:
            given = plan["supplier_eq"] - eq  # what it gave back for our last step, on our structure
            step = plan["last_step"] or 0.0
            if step > 0 and given < self.k["mirror_guess"] * step * 0.7:  # its limit binds: smaller steps
                price = min(price, round(plan["last_price"] + max(given / self.k["mirror_guess"], step * 0.25), 2))
        if math.isfinite(eq) and price >= eq:
            price = round(min(price, eq) * 0.999, 2)
        plan["last_step"] = price - plan["last_price"] if plan["last_price"] is not None else None
        plan["last_price"], plan["supplier_eq"] = price, eq
        plan["sent"] += 1
        main = complete_offer(case, {**plan["structure"], "unit_price": price})
        out = [main]
        if self.k["sheets"] > 1:
            out += self._variants(case, plan, main)[: self.k["sheets"] - 1]
        lines += self._arguments(case, sid, threads, plan, best)
        if self.k["ask_breakdown"] and plan["sent"] == 1:
            lines.append("Could you share a breakdown of your cost per unit?")
        lines.append(f"We propose EUR {price:.2f} per unit on the terms attached.")
        return self._mail(case, sid, lines, out)

    def _mail(self, case, sid, lines, sheets):
        body = "Dear Sir or Madam,\n\n" + " ".join(lines) + "\n\nKind regards\nPurchasing, Hollerau Pumpenwerke"
        return {
            "supplier_id": sid,
            "message": {"subject": f"Re: {case['title']}", "body": body, "term_sheets": [{"terms": t} for t in sheets]},
        }

    def _variants(self, case, plan, main):
        """Other structures that cost us the same: the supplier's pick shows what it values."""
        target = total_cost(case, main, plan["std"])
        out = []
        for s in structures(case):
            s = {k: v for k, v in complete_offer(case, {**s, "unit_price": 1.0}).items() if k != "unit_price"}
            if s == plan["structure"] or not must_haves_ok(case, {**s, "unit_price": 1.0}, plan["std"]):
                continue
            c0 = total_cost(case, {**s, "unit_price": 0.0}, plan["std"])
            c1 = total_cost(case, {**s, "unit_price": 1.0}, plan["std"])
            if c1 <= c0:
                continue
            p = round((target - c0) / (c1 - c0), 2)
            if p > 0:
                out.append(
                    (
                        abs(sum(s[k] != plan["structure"].get(k) for k in s)),
                        complete_offer(case, {**s, "unit_price": p}),
                    )
                )
        out.sort(key=lambda x: x[0])
        return [t for _, t in out]

    def _arguments(self, case, sid, threads, plan, best):
        mode, out = self.k["claims"], []
        if mode == "none":
            return out
        sc = plan["sc"]
        if sc and sc[0] not in self.cited:
            self.cited.add(sc[0])
            out.append(f"Our should-cost estimate {sc[0]} puts the full cost at EUR {sc[1]:.2f} per unit.")
            if mode == "cost":
                return out
        if mode != "bank":
            return out
        if best and best != sid:  # a rival's standing offer, cited to the others
            oid, terms = standing(threads[best])
            if oid and (sid, oid) not in self.cited and terms.get("unit_price"):
                self.cited.add((sid, oid))
                out.append(f"We hold a competing offer {oid} at EUR {terms['unit_price']:.2f} per unit.")
                return out
        for claim in self._index_claims(case):
            if claim[0] not in self.cited:
                self.cited.add(claim[0])
                out.append(claim[1])
                break
        return out

    def _index_claims(self, case):
        """Falling cost-driver indices of the case's parts over the last 12 months of each series."""
        if not self.package:
            return []
        parts = case["parts"]
        rows = self.package.query(
            f"select distinct series_id from cost_drivers where part_id in ({','.join('?' * len(parts))})", tuple(parts)
        )
        out = []
        for r in rows:
            ids = self.package.ids(f"idx:{r['series_id']}@")
            if len(ids) < 13:
                continue
            a, b = ids[-13], ids[-1]
            va, vb = self.package.lookup(a)["value"], self.package.lookup(b)["value"]
            change = (vb / va - 1) * 100
            if change < 0:
                out.append((b, f"The index {r['series_id']} fell {abs(change):.1f} % from {a} to {b}."))
        return out


SPACE = {
    "structure": ["joint", "buyer", "keep"],
    "guess_rate": [0.06, 0.08, 0.12, 0.2],
    "floor_guess": [0.8, 0.85, 0.88, 0.92, 0.95],
    "use_should_cost": [True, False],
    "open_below": [0.0, 0.03, 0.06, 0.1],
    "steps": [3, 4, 5, 6, 7, 8],
    "shape": [0.5, 0.75, 1.0, 1.5, 2.0],
    "sheets": [1, 2, 3],
    "take_alternative": [True, False],
    "after_final": ["accept", "hold", "push"],
    "claims": ["none", "cost", "bank"],
    "tone": ["warm", "neutral", "hard"],
    "ask_breakdown": [False, True],
    "accept_gap": [0.0, 0.002, 0.005, 0.01],
}


def sample_knobs(rng):
    """A random Calculator variant: every knob drawn from SPACE."""
    return {k: rng.choice(v) for k, v in SPACE.items()}


def registry(package):
    """Strategies by name, each a factory taking knobs. `llm` calls your LLM key: use it sparingly."""
    from arena_kit.agents import LLMAgent, llm_from_env
    from arena_kit.agents.naive import NaiveAgent

    return {
        "naive": lambda **k: NaiveAgent(),
        "calc": lambda **k: Calculator(package, **k),
        "llm": lambda **k: LLMAgent(llm_from_env(), package),
    }
