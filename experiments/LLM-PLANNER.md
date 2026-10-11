# LLM-PLANNER - where a language model earns its place in this agent (Sun 02:30-04:45)

Jonathan's question: the organisers hand out an LLM key, so a model must help somewhere - can it tell
us how to negotiate with a supplier, and would it have found P02's index clause without the test
sessions? Record of what was built (`sellm/planner.py`, `SELLM_PLAN=llm`), what was measured, and
what was rejected. Sessions and commits: `experiments/LEDGER-JONATHAN.md`.

## 1. The answer in three lines

- **Yes, the model finds the trade.** Given the case, the options, the supplier's opening e-mail and
  what the dossier holds on it, and no hint about any case, gpt-6-sol names P02's copper clause,
  P01's and P05's faster payment and P04's / P10's longer contract - 3 of 3 calls each, every time
  with the passage it rests on.
- **No, it must not decide the move.** Followed beyond what was measured it lost: the clause offered
  at once to the two suppliers that demand one (P08 0.48-0.53 against 0.55, P18 0.39-0.40 against 0.47);
  "open on payment terms" read as a wish for faster payment (P03, 2 of 3 calls); a looser ppm
  commitment for P11 (Amiad measured it: 0.620 against 0.778).
- **So the model reads and code acts.** The planner names what the supplier wants and which cost
  drivers it blames; code acts on the kinds that were measured, prices every offer, and lets the
  dossier decide where our data has a reading. On the ten practice cases the planner changes one
  e-mail (P01, +0.028); its use is the supplier the dossier's rules do not cover.

## 2. What the planner is

One question per supplier, before our first e-mail (`planner.voted`): three calls at once, a want or
a blamed cost driver counts when two of three name it (confidence counted, not asked for). The model
never gives a number. Code drops a want whose field or option does not exist in the case, whose
evidence is not a passage of the material it was given, or that only repeats the supplier's own
quote. The plan is kept on disk per case, supplier and material, so a resumed session plays the same
moves. No answer within 12 s: no plan, and the agent plays its rules.

What code does with it (`sellm/endgame.py`):

| The planner says | Code does | Measured |
|---|---|---|
| it would give price for faster payment | fastest payment in the first ask - only for a supplier without a cash reading in the dossier | by rule P01 0.953 -> 0.969; planner alone gives the same first e-mail (test) |
| it would give price for an index clause, relationship term, fixed-price opening | the clause as a second sheet at the price where our total cost is lowest, priced with the highest cost its quote allows | P02 0.531 -> 0.725 by rule; planner alone gives the same e-mail (test) |
| it blames cost driver X in its letter or quote, and X fell | X is cited with its larger fall, from its twelve-month peak | P01 0.969 -> 0.997 (letter: "energy, raw material and wage costs") |
| anything else (contract length, volume, lead time, ppm) | logged only | P11 ppm: 0.620 (Amiad); clause first P08 / P18: worse |

## 3. Offline: would it have found the trade? (no arena session)

`experiments/planner_offline.py`, three calls per supplier, 2.1-8.9 s each.

| Case | Supplier | The planner names | What we know from play |
|---|---|---|---|
| P01 | foundry | payment 14 days ("Could you pay our invoices within 10 days?") | right: 0.953 -> 0.969 |
| P02 | Nordmark | index clause ("CU-NOTATION rose 47.7 % ... 20 % of our cost") | right: 0.531 -> 0.725 |
| P03 | converter | nothing, or once payment ("He was open on payment terms") | nothing is right; the payment reading is wrong |
| P04 | bearings | 36 months ("only multi-year volume agreements change price") | right, the calculator asks it anyway |
| P05 | three bidders | payment 14 days for the two job shops; nothing or a longer lead time for the third | right for the two; lead time bought nothing (Amiad) |
| P07 | fasteners | nothing | - |
| P08, P18 | steel bar | the alloy clause (their letters propose it) | true, and offering it first is worse |
| P10 | seals | 36 months, volume | the calculator asks 36 months anyway |
| P11 | castings | ppm 1500 (2 of 3) | wrong: 0.620 |
| D01, D02 | demo suppliers, no data | nothing | - |

On the nine unplayed case files it names a trade with evidence for six suppliers (faster payment for
the three cash-short ones, a clause, a volume commitment), stable over three calls.

## 4. Live

- `jonathans_branch@b7b279e`, ten practice cases, plans made live: 75.4, the same ten deals as
  without a model; 10 plans, 3 of 3 answers each, 2.8-7.0 s.
- `jonathans_branch@8a854c4` through the final runner, ten cases at once: 80.3, 0 crashes, 0 refused
  moves, every case under 15 s. Without `SELLM_PLAN=llm` the same commit plays P01 at 0.969: 80.0.

## 5. What the model did not do, measured earlier

Writing the e-mails (71.6 against 72.9), a verdict "take the offer?" that may act (P01 and P18
worse), reading a supplier's persona without a dossier (32 of 48, as good as always "no"):
`experiments/LLM-ADVISOR.md`, `experiments/PERSONA-READER.md`.

## 6. Limits

- Ten practice cases, twelve suppliers, one model. The planner's gain on them is one case; its
  purpose - a supplier whose letter the dossier's rules do not read - cannot be measured before the
  final.
- A planner want is an opinion with a quotation. Each kind of want needs its own measured rule
  before code may act on it; three of the five kinds it named lost points when followed.
