# PERSISTENCE - can the agent get more by asking longer and harder? (Sat 22:05-23:00)

Jonathan's question: we accept after 4-6 rounds; a more persistent agent should get more. Tested
one change at a time on the real suppliers, one session each (practice suppliers answer identical
messages with identical numbers). The variants are knobs of a layer in its own file,
`sellm/endgame.py` (all off by default: it then plays exactly like the negotiator; `sellm/negotiator.py`
and `sellm/calculator.py` were not edited). Runner: `experiments/persistence.py`. Rows:
`experiments/results/2026-10-10-persistence.json`. Sessions: `runs/`, labels `PERSIST ...` and `TEST past-target`.
Practice sessions used: 10.

## 1. Who ends a negotiation today

Negotiator v1.4 (@cdd9cf8), the ten practice cases:

| Ended by | Cases | After our messages |
|---|---|---|
| the supplier, with `final_offer` | P02, P03, P04, P05, P07, P08 | 3 to 6 |
| us, target reached (relationship term) | P01 | 4 |
| us, it took our ask or its own second sheet | P10, P11, P18 | 2 to 5 |

So in six of ten cases there is nothing to be persistent about: the supplier says its last word and
a final offer is final (sandbox, Sat 15:50: pushing after it lost one of two deals). The room is in
the four cases we end ourselves.

## 2. Results

Reference = negotiator v1.4 without the layer. `.` = not played.

| Variant | D01 (free) | P01 | P04 | P07 | P08 | P11 | P18 |
|---|---|---|---|---|---|---|---|
| reference | 0.921 (0.921-0.947 over four sessions) | 0.915 | 0.860 | 0.747 | 0.549 | 0.778 | 0.467 |
| `past_target` | 0.947 | **0.953** | . | . | . | . | . |
| `past_target` + hold our price (`past_creep=0`) | 0.921 | 0.960 | . | . | . | . | . |
| `past_target` + `creep=0.25` (every step at most a quarter of the gap) | 0.959 | 0.960 | . | . | . | 0.710 | 0.467 |
| the same + `zone=0.009` (ask 0.9 % below its offer once it repeats it) | . | . | 0.860 | . | . | 0.710 | 0.434 |
| first ask closer to its price (`floor_share=0.927`) | D02: 0.441 against 0.567 | . | . | 0.773 | 0.549 (same moves) | . | . |

## 3. Findings

- **P1 (seen twice). Stopping at our target leaves money where the supplier is still moving.** In
  a case with a relationship term the negotiator accepts once the offer is at or below the price
  where our own estimate says total cost is lowest. P01: accepted 135.10; asking once more brought
  133.96 (0.915 -> 0.953). D01: 50.20 -> 50.00 on the same path. The estimate of the supplier's cost
  was too high in three of four checkable cases, so the stop came too early.
- **P2 (seen). A supplier takes an ask about 1 % below its standing offer and counters one further
  away.** P01: 133.69 against its 136.50 (2.1 % below) got a counter of 135.10; 133.70, 133.71 and
  133.96 against 135.10 (1.0 %, 1.0 %, 0.8 %) were taken at once. P18 took 5.50 against 5.60 (1.8 %).
  D01's foundry countered 0.7 % below with a lower offer instead.
- **P3 (seen). That is not a rule to build on: whether it says yes depends on the path.** P11 took
  45.09 against its 45.50 in the reference session and refused the same 45.09 in the zone test,
  where the asks before it were different; Omar measured the same case at 0.710 after a change that
  only replaced one cited fact (22:30). P11's 0.778 is one lucky path.
- **P4 (seen). Slower steps do not make a supplier that has stopped moving move.** P11 stood at
  45.50 for five rounds while our asks crept from 44.34 to 45.01, then said `final_offer`. P04 stood
  at 4.94 whatever we asked (4.62, 4.74, 4.90). Holding our price at D01 (a step of 0.01) got the
  same 50.20 twice: "it gives nothing without a move from us" is true there.
- **P5 (seen). How many rounds a supplier gives depends on how far away our asks are - for one
  supplier.** P07: asks 4.82, 4.98, 5.12 got `final_offer` at the third answer (5.41); asks 5.08,
  5.18, 5.25, 5.31 got a fourth answer (5.37), as the kit agent had (5.36). But the job shop in D02
  follows our level: the closer first ask ended at 15.00 instead of 14.40. One supplier each way,
  so the first ask stays as it is.

## 4. What to adopt

1. **`past_target`, alone.** Replayed over all 239 decision states of the latest full runs (ten
   practice cases, D01, D02) it decides differently in 5 - exactly the ones where the negotiator
   accepted because the target was reached (P01, D01). Everywhere else the moves are identical, so
   nothing else can change. Measured: P01 +0.038, D01 +0.026 on its path. Worst case: the supplier
   says `final_offer` at the offer the negotiator would have accepted anyway. It stops at the
   target of a cost estimate 5 % lower, so it cannot chase a supplier far below its cost.
2. Not `creep`, `zone` or `past_creep`: no gain that survives P11 and P18. The knobs stay in the
   layer, off, with this record.

To switch it on for `--agent sellm`: `sellm/agent.py:make_agent` returns
`sellm.endgame.Persistent(..., past_target=True)` (one line; not done - waiting for Jonathan).

## 5. Open

- The hidden cases: about four of ten practice cases carry a relationship term; the rule acts only
  there, and only when the supplier is still moving at our target.
- P2 suggests that the last ask before a supplier's offer decides the price it takes. Mapping that
  per supplier would need its schedule, which hidden suppliers do not show in advance.
