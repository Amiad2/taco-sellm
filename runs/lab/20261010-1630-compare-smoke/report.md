# Lab compare 20261010-1630: naive vs calc

288 negotiations, 72 scenarios (12 twins). Scores x 100; 'worst 10 %' is the mean of the worst tenth of scenarios; crashes, broken must-haves and deals worse than the opening are counted per negotiation.

| # | Strategy | Knobs | Scen. | Mean | Twins | Invented | Held-out | Worst 10 % | No deal | Crash | Broken | Worse |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | calc | - | 72 | **48.7** | 52.9 | 47.9 | 57.5 | 7.3 | 6 | 0 | 0 | 2 |
| 2 | naive | - | 72 | **36.4** | 22.3 | 39.3 | 30.1 | 0.0 | 0 | 0 | 10 | 6 |

Per twin (best three and baselines):

| Strategy | D01 | D02 | P01 | P02 | P03 | P04 | P05 | P07 | P08 | P10 | P11 | P18 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| calc | 0.82 | 0.34 | 0.55 | 0.18 | 0.91 | 0.72 | 0.12 | 0.77 | 0.21 | 0.70 | 0.73 | 0.31 |
| naive | 0.23 | 0.33 | 0.59 | 0.22 | 0.07 | 0.78 | 0.00 | 0.12 | 0.21 | 0.00 | 0.00 | 0.12 |

Run: `uv run python -m sellm.lab compare naive calc --invented 60 --seeds 2 --label smoke`, 31 s.
