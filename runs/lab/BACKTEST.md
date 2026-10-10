# Lab backtest: how close the twins are to the real suppliers

Generated Sat 2026-10-10 by `uv run python -m sellm.lab backtest` (after `--fit`). Every buyer e-mail of
our real sessions in `runs/` (practice and sandbox, 233 supplier replies) is replayed into the twin
of its case; the twin's reply is compared with the real one. Error: the value of the supplier's offer
to the supplier itself (so a different structure is not an error), as a share of its opening value.

## Accuracy

| Case | Replies | Mean abs error (% of opening value) | Status agrees | Claims agree |
|---|---|---|---|---|
| D01 | 146 | 0.22 | 143/146 | - |
| D02 | 42 | 2.61 | 33/42 | 12/18 |
| P01 | 9 | 0.61 | 8/9 | - |
| P02 | 4 | 0.69 | 3/4 | - |
| P03 | 4 | 0.83 | 2/4 | 2/4 |
| P04 | 3 | 0.33 | 3/3 | 2/2 |
| P05 | 6 | 8.06 | 3/6 | - |
| P07 | 4 | 0.56 | 3/4 | - |
| P08 | 5 | 0.10 | 5/5 | - |
| P10 | 2 | 3.26 | 1/2 | 1/1 |
| P11 | 5 | 0.98 | 4/5 | 3/3 |
| P18 | 3 | 1.28 | 2/3 | 1/1 |
| **all** | 233 | **0.95** | 210/233 | |

Read it like this: D01 (28 sessions) and P01, P04, P07, P08 are reproduced within about half a percent
of the opening value per reply, and the status (open / final_offer / agreed / walked_away) matches in
9 of 10 replies overall. **P05 and P10 are not**: one session each, and the RFQ job shops in P05 and
the capacity-tight seal maker in P10 concede very differently from the rest. Treat lab results on those
two as weak.

## Floors (calibrated to C_best)

The floor is the full cost in value space: the cheapest package the twin accepts costs exactly the
case's C_best. On P01 this gives 129.91; the relationship charge the arena billed on our P01 deal
implies 129.95. Where a plant-specific should-cost exists the floors sit within 3-5 % of it (P02
363.96 vs 374.95, P03 397.46 vs 403.21, P10 25.64 vs 24.31), as close as the estimate itself.

| Case | Type / goal | Floor per supplier (value at its standard terms) | C_best |
|---|---|---|---|
| D01 | price_increase / stabilise | sup:DEMO-F1 48.07 (opening 52.90) | 408,624 |
| D02 | rfq / leverage | sup:DEMO-J1 12.79 (opening 17.10), sup:DEMO-C1 11.97 (opening 16.00) | 156,739 |
| P01 | price_increase / stabilise | sup:70110 129.91 (opening 138.55) | 1,096,816 |
| P02 | price_increase / stabilise | sup:70510 363.96 (opening 370.96) | 2,235,514 |
| P03 | renewal / stabilise | sup:70530 397.46 (opening 438.21) | 3,909,043 |
| P04 | renewal / routine | sup:70620 4.87 (opening 4.96) | 196,529 |
| P05 | rfq / leverage | sup:70210 29.68 (opening 36.00), sup:70240 25.97 (opening 31.50), sup:70250 31.74 (opening 38.50) | 223,424 |
| P07 | bundling / routine | sup:70610 4.95 (opening 5.74) | 299,241 |
| P08 | raw_material / leverage | sup:70710 5.00 (opening 6.05) | 960,309 |
| P10 | capacity / secure_supply | sup:70410 25.64 (opening 32.20) | 1,328,927 |
| P11 | quality / quality_first | sup:70140 42.01 (opening 47.00) | 722,500 |
| P18 | raw_material / leverage | sup:70740 4.62 (opening 6.10) | 222,651 |

## Fitted dynamics

first_step: share of (opening - floor) in the first counter; mirror: share of our step it gives back;
cap: most it gives back for our step in its 2nd counter (share of its opening value), shrinking by
cap_decay per further counter; patience: our messages until final_offer (a tiny step counts twice).
Fitted on a grid, per case one step around the global best. Cases with one session are fitted on 2-6
replies: these are plausible values, not measurements.

| Case | first_step | mirror | cap | cap_decay | patience |
|---|---|---|---|---|---|
| D01 | 0.35 | 0.5 | 0.004 | 1.0 | 6 |
| D02 | 0.2 | 0.7 | 0.007 | 0.8 | 5 |
| P01 | 0.5 | 0.7 | 0.004 | 0.8 | 7 |
| P02 | 0.2 | 0.3 | 0.004 | 0.8 | 5 |
| P03 | 0.2 | 0.3 | 0.004 | 0.8 | 5 |
| P04 | 0.5 | 0.5 | 0.007 | 0.8 | 5 |
| P05 | 0.2 | 0.3 | 0.004 | 0.8 | 5 |
| P07 | 0.35 | 0.7 | 0.007 | 1.0 | 5 |
| P08 | 0.35 | 0.7 | 0.007 | 0.8 | 5 |
| P10 | 0.2 | 0.3 | 0.004 | 0.8 | 5 |
| P11 | 0.5 | 0.7 | 0.007 | 1.0 | 5 |
| P18 | 0.2 | 0.7 | 0.007 | 0.8 | 5 |

What it says about the real suppliers: they give back far less than our step (cap at the grid's
lowest value 0.4 % of the opening for most), so a large step buys a large concession only up to a
small limit per round - and how much room is left after five rounds is decided mostly by the first
counter. Strategies to screen follow from this; see `sellm/lab/strategies.py`.
