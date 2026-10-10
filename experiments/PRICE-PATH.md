# PRICE-PATH - first ask, horizon, relationship push, should-cost (Sun 00:20-00:40, Omar)

Omar's questions: is the first ask (target x 0.94) too high and should it be dynamic; how far can the
target be pushed before a supplier quits; is the 4-round horizon too short; can relationship
suppliers be pushed harder; what would knowing the supplier's should-cost gain. Full report (German,
for Omar and the team): https://claude.ai/code/artifact/cd7f860c-5e80-433d-b1fe-40bb34782ddf

**Result: none of the price levers gains on average; today's open_below 0.06, horizon 4 and target
sit at the optimum. The only measurable lever is a better cost estimate for unknown suppliers (at
most +2 points), and an estimate that is too low costs -5.9. Never ask after a final offer.**

## Sources

- Real sessions in `runs/` (all agents, practice and sandbox): 316 threads from 200 sessions with a
  calibrated floor (`sellm/lab/twins.json` personas' `full_cost`, set so the cheapest acceptable package
  costs the real `C_best`; P05's RFQ floors are synthetic and left out of the per-case figures).
- Lab sweep `uv run python -m experiments.price_path --invented 200 --seeds 3`: 29 variants x 212
  scenarios (12 fitted twins, 200 invented) x 3 seeds = 18,444 negotiations, engine suppliers, clock on,
  one loop per thread; `runs/lab/20261011-0024-price-path/summary.json`. Target pushed up:
  `runs/lab/20261011-0031-price-path-up/summary.json`. Differences are paired (same scenario and seed)
  against `sellm.agent.make_agent` at 20a318a, in points on the 100 scale, +- standard error.

## Results

| Question | Real sessions | Lab (paired, all scenarios) |
|---|---|---|
| First ask lower | within each case, the lower half of first asks reached the same price: -0.03 pp of the floor over 10 cases (D01 -1.2 pp); final_offer earlier in P11 (5.6 vs 7.0 messages) and D01 | open_below 0.00 -2.58, 0.03 -0.25, **0.06 today**, 0.10 -1.90, 0.15 -4.40, 0.20 -6.55 |
| Target pushed | suppliers stop 2-24 % above their floor (median lowest price / floor: P10 1.244, P18 1.189, P07 1.089, P03 1.087, P11 1.083, P08 1.078, D01 1.048, P01 1.040, P02 1.019, P04 1.015) | x0.85 -6.64, x0.90 -4.21, x0.94 -2.47, x0.97 -1.38, **x1.00**, x1.03 -0.30, x1.05 -1.53, x1.08 -4.83 |
| Walk-aways | 6 in 316 threads: 4 after a push past final_offer (practice 3 of 4 such pushes withdrew), 2 in P05 with a first ask 13.6 % below the floor | push_final 0.005 -0.49, 0.01 -4.77 (twins -21.06, 59 more lost deals) |
| Horizon | final_offer after a median of 4 of our messages, in 64 % after at most 4 (171 threads) | 3 -0.27, **4**, 6 -0.26, 8 -0.83, 10 -1.26 (twins 6 -1.40, 8 -3.99, 10 -6.58) |
| Relationship push | stabilise/secure_supply suppliers end closer to the floor (1.060 vs 1.096) but give a smaller share of their room (0.32 vs 0.40); walk-aways 2 % in both | only in relationship cases: horizon 6 -0.03, open 0.10 -1.11, target x0.95 -1.09; per twin D01 +4.7..+5.2, P01 +5.6..+6.3, P02 -2.8..-3.4; invented relationship suppliers lose for every archetype |
| Should-cost known (oracle) | today: own-plant should-cost +1.4..+2.1 % (P10 -5.2 %), priors -2.2..+10.8 % | exact floor, first ask 6 % below -1.74; 3 % below +1.71; at the floor +1.97; floor +5 % **+2.05**; floor -5 % **-5.89**; twins all -0.4..-2.9, invented +1.8..+2.3 |

## What follows (for code changes)

1. Keep `open_below` 0.06, `horizon` 4 and the target; write the measured curves next to the knobs.
2. Never ask after `final_offer` (`push_final` stays off); a test that the agent accepts a final offer.
3. Keep `past_target`; do not widen it into a general relationship push.
4. The one lever: a cost estimate with less spread for suppliers without an own-plant should-cost
   (dossier history asked vs agreed, generic should-cost x country, recent low, cost drivers), rounded
   up when unsure, with the first ask 0-3 % below it when it is sure. Upper bound +2 points; never go
   below today's prior while the new estimate is uncertain. Measure against the oracle in this lab
   frame first, then one practice session each for P07, P11, P18.

## Limits

The lab is a model (under 1 % error per reply in the backtest, but Amiad's P02 dials were predicted
+5.5 and gave 0 for real); the first-ask and oracle curves rest on its rule that an offer more than
6 % below cost offends (from sandbox tests). Floors come from `C_best` through that model. The real
sessions are observational. Lab scores of single twins differ from the arena (P01: lab 0.726, real
0.969): read the paired differences, not the levels.
