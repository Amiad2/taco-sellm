# PRACTICE-ARMS - what 30 practice sessions on the real arena said (Sat 21:15-21:35)

Written by an outside review session (Claude Code, Jonathan's MacBook) that was asked to look at the
project without bias, to build a few of the team's findings into the agent, and to test several
things on the real practice suppliers, with practice quota no longer scarce (450 limit).
**Nothing in this file changes `docs/PLAN.md` or `docs/STATUS.md`; it is evidence and a proposal.**
Raw numbers: `experiments/results/2026-10-10-practice-arms.json`. Every session in full:
`runs/practice/<case>/` (labels start with `EVAL`). The code of the arms: `experiments/arms/`.

## 0. The five things to take away

1. **The 53.2 of the 20:38 run was two cases, and the cause is already fixed in `19b339f`.** P04
   (0.81 -> 0.00) and P08 (0.43 -> 0.15) cost 109 points; the other eight cases together were
   +26 points better than the kit agent. The negotiator judged contract length at the supplier's *opening*
   price, where a second year looks dearer than the fallback. Pricing the package at the price we
   expect to end at (the calculator, Jonathan 21:06) gives **67.5 on all ten** (kit LLM agent 61.5).
2. **The argument bank (`sellm/claims.py`) moves real suppliers, if two things are fixed.** With
   verified facts P01 went 0.831 -> 0.915 and P02 0.293 -> 0.531; the supplier's reply says "we did
   not know that - a fair point". But **every ppm sentence came back `contradicted` (3 of 3)**
   because of the thousands comma ("2,376 ppm"), and a second forecast or complaint is `duplicate`
   once one fact of that topic is used. Both are small fixes (section 4, F3 and F4).
3. **The dossier is used, and it is worth about 3.5 points on the six cases tested** against the
   same agent without it (5 better, 1 equal): what a hidden supplier we hold no data on would cost.
4. **What we ask first barely matters; what structure the supplier will quote and which verified
   fact we bring does.** P04 4.09 -> 4.54, P11 38.88 -> 42.41, P18 5.02 -> 4.89 as the first ask:
   the supplier's final price did not move at all. Stop tuning price paths on practice.
5. **Practice suppliers answer identical messages with identical numbers.** One session per case is
   enough for single-supplier cases (P05, the RFQ, varies 0.66-0.77), and any variant can be
   replayed offline over recorded sessions to see *which* cases it would change before spending a
   session (`experiments/arms/tools/replay.py`). A full grid of seven arms over ten cases would
   have been 70 sessions; replay showed which cases an arm changes, so 30 were enough.

Candidate (`full` = bank + ppm fix + one fact per topic + dossier signals), per case, measured or
inferred by identical-move replay: **about 71 on the ten cases** (a1 at HEAD: 67; kit LLM: 61.5).

## 1. Method

- Base: `19b339f` (Jonathan 21:06, calculator + negotiator) plus `f6e083b` (Amiad's claims bank),
  copied to a separate directory so that the working tree of the running session was not touched.
  `main` has moved on since (`cd67dda` 21:23, the deadband rule; `a5738b8`, runner v1.2): the
  patch applies to `19b339f` only, see section 6 for what overlaps.
  All arms are `Negotiator` knobs (patch: `experiments/arms/negotiator-arms.patch`, off by default).
- Runner: `sellm.runner` (Amiad) behind a launcher that waits for a free session slot
  (`experiments/arms/evalrun.py`), one loop per thread, `ARENA_NO_PULL=1` on purpose (an unpushed
  variant). Every decision was written to a trace by `experiments/arms/audit.py` (section 5).
- Design: one change per arm, run only on the cases where a replay over recorded sessions says the
  arm would send something different. 30 practice sessions (quota 41 -> 75 included a few of other
  sessions' runs; mine are the 30 labelled `EVAL`), plus 2 free sandbox sessions.
- Reference columns: kit LLM agent (15:27, `runs/BASELINE.md`), negotiator v1.1 (20:32),
  `a1` = HEAD at 21:06, the batch Jonathan's session ran (not mine). **Caveat: that batch's first
  ask on P08 (5.06) and P10 (28.60) differs from what HEAD 19b339f replays (4.91, 24.72), so for
  those two cases the `a1` column is not exactly HEAD.** The cause was found by Jonathan's session
  at 21:36 (`d792ee3`): data lookups failed silently when several cases were decided at once, and
  the agent fell back to its guess. A clean `a1@HEAD` on P10 gave 0.647 (the same as the bank arm:
  the bank did not change P10). None of the 23 first asks of my arms deviated from the sequential
  replay (checked from the traces), so the arms were not hit.

## 2. Results per case

Score per session. `.` = not played (the arm sends the same moves as the arm to its left, replay
checked). `[x]` = inferred from the arms that were played, not one run of that object.

| Case | kit LLM | v1.1 | a1 | bank | bank2 | ppmfix | bank2s | clause | full | no dossier |
|---|---|---|---|---|---|---|---|---|---|---|
| P01 | 0.789 | 0.874 | 0.831 | **0.915** | . | . | . | . | [0.915] | 0.864 |
| P02 | 0.105 | 0.183 | 0.293 | 0.521 | 0.522 | **0.531** | . | . | [0.531] | 0.510 |
| P03 | 0.903 | 0.855 | 0.919 | **0.923** | . | . | . | . | [0.923] | . |
| P04 | 0.810 | 0.000 | 0.860 | 0.860 | . | . | 0.860 | . | 0.860 | 0.860 |
| P05 (RFQ) | 0.676 | 0.769 | 0.769 | 0.659 | . | . | . | . | [0.66-0.77] | . |
| P07 | 0.779 | 0.720 | 0.747 | 0.740 | **0.747** | . | . | . | [0.747] | 0.739 |
| P08 | 0.433 | 0.152 | 0.527 | **0.549** | . | . | . | 0.462 | [0.549] | 0.482 |
| P10 | 0.570 | 0.655 | 0.663 | 0.647 | . | . | . | . | [0.647] | . |
| P11 | 0.710 | 0.710 | 0.710 | 0.543 | 0.710 | 0.710 | 0.710 | . | **0.778** | . |
| P18 | 0.377 | 0.406 | 0.430 | 0.386 | . | . | 0.467 | 0.467 | **0.467** | 0.406 |
| **mean** | **61.5** | **53.2** | **67.5** | 67.5 | | | | | **~71** [P05 0.66-0.77] | |

What each arm is (knobs in the patch):

| Arm | Change on top of `a1` |
|---|---|
| `bank` | when the rival offer, should-cost and falling-index rules have nothing, cite the next fact of `claims.arguments()` (never one already cited, never a `quote`) |
| `bank2` | `bank` + one fact per topic per case + no ppm sentences |
| `ppmfix` | `bank2` with ppm written without the thousands comma ("2376 ppm") |
| `bank2s` | `bank2` + the dossier's signals set the share of the opening we aim at (`list_price_fixed` >= 2 or `margin_floor`: 0.96; `wants_volume` >= 2: 0.84; the supplier's lowest price of the last year no longer caps the target when its list price is fixed) |
| `clause` | `bank2s` + where the supplier insists on an index clause, ask the variant with the widest deadband |
| `full` | `ppmfix` + `bank2s` |
| `no dossier` | `full` with `dossier` switched off: what a supplier without a dossier gets (it sends two equal-C offers, 30 and 90 days) |

Free sandbox, `full`: D01 0.921, D02 0.567 (negotiator v1.1: 0.920 / 0.530).

## 3. Reading the transcripts: what was said

- **P01 (Brandlhuber), bank**: four verified facts in four e-mails, each followed by a concession:
  index PPI-D351 -3.7 % ("we did not know that"), the notice letter `doc:20260911-70110-P01` (51
  days) against `ctr:4600070110` (90), should-cost `cost:310010` 132.64, forecast `fc:310010@2026-09`
  +10.1 %. Supplier: 141.70 -> 137.50 -> 136.50 -> 135.10; accepted 135.10 (0.915). `a1` without
  the facts ended at 136.80.
- **P02 (Nordmark), bank**: price history `po:` pair, forecast +11.9 %, OTD 90.4 % all `verified`
  and moved it 373.97 -> 372.03 -> 371.82; the fourth, `qn:20004826 ... 5,263 ppm`, was
  `contradicted`: "That costs trust ... please provide the underlying documentation", final offer.
- **P11 (Kalwisz), bank**: `sc:70140@2026Q3 ... 2,376 ppm` and `qn:... 27,778 ppm`
  `contradicted` twice; the supplier stopped at 46.50 (a1: 45.50). With "2376 ppm" the same
  sentence was `verified` (ppmfix, full).
- **P08/P18**: the supplier ties the index clause to the term: 12 months quotes no clause, 24/36
  months "we must apply the clause". Asking the widest deadband (`clause`) made it *raise* the price
  (5.57 -> 5.59 instead of 5.48): it prices the deadband at least as high as it is worth to us.
- **P05**: all three bidders react to a rival's offer cited by its ID ("it does move us a bit");
  the supplier at 70240 said outright that 90 days payment "means more cost for us, not less" while
  we kept asking 90 days from a `cash_pressure: low` monopolist. The close came from 70250 (28.50).

## 4. Findings

Confidence: **seen** = in a transcript, **computed** = from the cost function, **inferred** = reasoning from several sessions.

- **F1 (seen, computed). The 53.2 run lost on structure, not on price.** Offline loss analysis of
  `a1`: the price on the deal's own structure that would reach `C_best` is within +0.2 % (P04),
  +0.7 % (P03), +1.2 % (P01), +1.5 % (P02) of what we got; the cases that still have room are P07
  +7.8 %, P08 +8.7 %, P05 +8.5-12.6 %, P10 +15.8 %, P18 +18.6 %.
- **F2 (seen). Practice suppliers are deterministic in the numbers.** The same agent twice (v1.1 at
  20:32 and 21:03) gave identical scores on 9 of 10 cases; D01 x3 identical. Only RFQ threads move
  with timing. So (a) one session per single-supplier case suffices, (b) replaying a variant over
  recorded sessions tells exactly which cases it changes, (c) a change that leaves the first
  message unchanged leaves the whole session unchanged.
- **F3 (seen, 3/3 and 2/2). Integers with a thousands comma in a ppm sentence are `contradicted`.**
  "was 2,376 ppm", "recorded 5,263 ppm", "27,778 ppm": contradicted. The same sentences without
  the comma: `verified` (sc quality) / `duplicate` (qn after sc, see F4). Fix in
  `sellm/claims.py` lines 145 and 156: `{ppm:,.0f}` -> `{ppm:.0f}` (and rebuild the dossiers:
  `uv run python -m sellm.intel build`, their `citable` has the comma baked in). EUR figures with
  decimals ("EUR 1,608.32") and forecast units were fine.
- **F4 (seen). One fact per topic per case.** In P07 `fc:360011` was `verified`, then `fc:360012` and
  `fc:360030` (other parts) `duplicate`. In P11 `qn:` after `sc:` ppm was `duplicate`. Topics that
  were verified together in one case: idx, doc+ctr, cost, po, fc, sc OTD, sc quality. The bank's
  ranking should pick the next *topic*, not the next ID.
- **F5 (seen, 3 cases). The supplier's final price on the same structure did not depend on our
  first ask.** P04 4.09 vs 4.54: 4.94 both; P11 38.88 vs 42.41: 45.50 both; P18 5.02 vs 4.89:
  5.50 both at 90 days. The D01 finding (a lower opening alone changes nothing) holds on practice
  suppliers. Suppliers follow their own concession schedule (P11: 47.00, 46.50, 46.00, 45.50
  whatever we asked). What did change in P18 is which alternative sheet the supplier put next to its
  offer (F8). The 17 % openings were neither needed nor harmful in these three; a milder opening
  costs nothing in score here and is safer against hidden suppliers that read a lowball as "not
  serious" (the lab's lowball penalty, unconfirmed on practice).
- **F6 (seen). Verified facts move some suppliers by 1-2 %, others not at all.** Moved: P01 (notice
  letter, forecast, should-cost), P02 (price history, forecast, OTD), P05 (index, rival offer).
  "Holds, but does not change our calculation": P04, P07, P08, P18 (forecast, OTD). Which fact moves
  which supplier is in its notes and signals (`docs/PLAN.md` section 10); the bank does not use the
  signals to order its facts yet (open).
- **F7 (seen). The dossier is worth about 3.5 points on those cases, and its absence is cheap.** `no dossier` vs
  `full` on 6 cases: P01 -0.051, P02 -0.021, P04 0, P07 -0.008, P08 -0.067, P18 -0.061 (mean 64.4
  against 67.8). A hidden supplier with no dossier gets the two-offer menu (30 and 90 days at equal
  C) and loses little. The gain comes from `cash_pressure` / `cost_of_money`: 90 days asked of a
  `low` supplier, 14 days of a `high` one.
- **F8 (seen). The signals arm helps on P11 and P18 and is neutral on P04.** P11 0.710 -> 0.778 only
  together with the fixed ppm sentence (neither alone moved it). P18 0.386 (bank, first ask 5.02)
  -> 0.467 (first ask 4.89): the supplier's first reply to 4.89 carried a second sheet with an
  index clause with a 5 % deadband at +0.10 (5.7 against 5.6), which our C prefers by 5,866; the
  reply to 5.02 had no such sheet. So the first ask can change *which alternatives the supplier
  offers*, not the price on a given structure. Treat this as path luck until a second supplier shows it.
- **F9 (seen). Asking for a deadband is supplier-specific; at the same price it is worth 22,800
  (P08) and 5,900 (P18), but the supplier does not keep the price.** `clause`: P08 0.549 -> 0.462
  (5.55 with 5 % against 5.35 with 0 %: it prices the deadband above what it is worth to us),
  P18 unchanged at 0.467 (it gave the 5 % variant at +0.10, worth more to us). Two sessions
  without label at 21:23:38 (the same rule as `cd67dda`, probably Jonathan's session trying it)
  ended P18 0.485 (5.40, 30 days, 5 %) and P08 0.419 (5.59, 5 %). Together: P08 -0.08 to -0.11,
  P18 +0.04 to +0.05. The commit message of `cd67dda` counts "with the 5 % deadband 0.657" at the
  price we closed with the 0 % clause; the supplier re-prices, so that figure is not reachable in P08. The index clause is still 40 % of the remaining P08 gap
  (32,000 of 79,000) and 18 % of P18's; what the supplier would give for 12 months without a
  clause is open (it quotes the clause for 24 and 36 months, none for 12; C says 12 months costs
  38,700 more in P08).
- **F10 (computed). Every `ppm_commitment` and `chargeback` in a deal comes from the supplier's
  standard terms** (P01 900 ppm, P18 70, P08 50) because they are not negotiable in those cases.
  Nothing to win there except in P11.
- **F11 (seen). Latent bug: `make_agent(package, dossier=False)` does not switch the dossier off.**
  `Negotiator.__init__(package, writer, chat, dossier, **knobs)` takes `dossier` as its own
  parameter, so the knob `dossier=True` in `DEFAULTS` can never be set from the constructor (the
  lab's search and challenge commands pass knobs this way). The no-dossier arm sets `agent.k["dossier"]`
  after construction.
- **F12 (seen). The `recent_low` clamp in `aim()` dominates the share on cases without a
  should-cost.** P04: target = min(0.88 x 4.96, 4.29) = 4.355 whatever share is given; 4.29 is the
  supplier's price of 2024-09. It is a price "it can go back to" only if nothing changed; for a
  supplier with a fixed list price it makes the first ask 17.5 % below its offer.

## 5. Tool-use audit (does the agent really use the calculator and the dossier?)

`sellm/audit.py` wraps the negotiator and writes one JSON line per decision. Over 153 decisions in
all arms (10 practice cases, free sandbox excluded):

| Tool | Result |
|---|---|
| `sellm.intel.dossier` | called in every thread, **coverage `full` for all 10 practice suppliers**, 0 exceptions; read: `cash_pressure`, `cost_of_money`, `signals`; **not read: `contract`, `alternatives`, `forecast`, `parts.*.history`, `economics.archetype`** |
| `calculator.packages` | called once per supplier thread (the first ask), 37 calls, always returned candidates; **never again after the supplier's first answer** (later structures come from the supplier's own sheets, `structure()`) |
| `calculator.supplier_cost` / `recent_low` | 28 calls; `own_low_12m` is the only evidence that reaches a decision (F12) |
| `calculator.price_for` | 6 calls (the menu for a supplier without dossier) |
| `claims.arguments` | not called by the committed negotiator; arms `bank*` call it. Before `f6e083b` the dossiers' `citable` was empty for every supplier; now 12-24 facts per decision |
| negotiator rescue path | 0 of 153 decisions; LLM calls 0 (no LLM in the agent) |

Run `python -m sellm.audit runs/logs/trace.jsonl` after any run to get this table per case; it exits
1 when a case had no full dossier, no `packages()` call, or a rescue.

## 6. What I would adopt, in order (a proposal for group A and C)

1. `sellm/claims.py`: drop the thousands comma in the two ppm sentences; rebuild the dossiers (F3).
2. `Negotiator.arguments()`: after the rival / should-cost / falling-index rules, take the next fact
   of `claims.arguments(...)` that is of an unused **topic** (F4) and not a `quote`. Patch in
   `experiments/arms/negotiator-arms.patch` (knobs `bank`, `ppm`, `one_per_topic`).
3. Optional, small and in-sample: the `signals` share (F8). Formulated after the floors of the
   practice cases were known, so it needs the hidden cases to confirm; at worst neutral here.
4. Fix F11 (`dossier` knob) and F12 (let the `recent_low` clamp go when the list price is fixed).
5. `cd67dda` (ask once for the cheapest option of a field the supplier changed) is the same idea
   as my `clause` arm; on practice it was P08 -0.1, P18 +0.05. Jonathan's session measured it
   separately and switched it off in `d792ee3` (knob `second_choice`): the two measurements agree.
   Do not tune the first ask on practice (F5).

Not tested, and worth a session each when the quota allows: contract length no longer than the
horizon (P07: the kit agent got 5.36 for 24 months, we got 5.41 for 36); ordering the bank by the
dossier's signals (F6); an LLM writer that answers the supplier's questions; asking for 12 months
without a clause (F9).

## 7. Caveats

- Ten practice cases, one session each: in-sample. P04, P10 and P18 were looked at before this
  review (P04 drove the structure fix), so they are no longer a clean hold-out.
- `full` is measured as an object on P04, P11, P18 only; the other seven are inferred from the arm
  that sent identical moves (checked by replay: P01, P03, P08, P10 identical to `bank`; P02 and
  P07 played in `ppmfix` / `bank2`).
- P05 is an RFQ: the same agent scored 0.769, 0.665 and 0.659. Differences below 0.1 there mean nothing.
- The `a1` column for P08 and P10 is a batch whose first ask differs from HEAD (section 1).
- The suppliers are LLM-driven bots in a simulator; "verified, we took it into account" is their
  wording and the numbers moved with it, but the hidden suppliers may react differently.

## 8. Reproduce

```bash
# base = origin/main at 19b339f or later; the arms are knobs of the negotiator
git apply experiments/arms/negotiator-arms.patch
cp experiments/arms/{audit,variants,evalrun}.py sellm/
export ARENA_NO_PULL=1 SELLM_TRACE=runs/logs/trace.jsonl
python -m sellm.evalrun --set practice --agent sellm.variants:full --cases P04 P11 P18 \
    --label "EVAL full ..."
python -m sellm.audit runs/logs/trace.jsonl
# which cases would a variant change? replay over recorded sessions, no quota
python experiments/arms/tools/replay.py <since_epoch> <until_epoch> bank2
```
