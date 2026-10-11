# Lab compare 20261011-104047-compare-final-81: naive vs calc vs sellm.agent:make_agent

1512 negotiations on 252 scenarios. Scores x 100. **Test** = scenarios the search never saw (held-out twins P04/P10/P18 and freshly generated ones): rank by it. Train = what the search tuned on. Worst 10 % = mean of the worst tenth of scenarios. Counts are per negotiation: crashes and refused moves (422) would cost cases in the final; broken must-haves and deals worse than the opening score 0; 'below alt' = ended under what walking away would have scored.

| # | Strategy | Knobs | Test ± SE | Train | Twins | Case files | Invented | Worst 10 % | Crash | 422 | Broken | Worse | Below alt | Wave cap | Timeouts | No deal |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | sellm.agent:make_agent | default | **52.5** ± 3.3 | 52.9 | 64.5 | 51.8 | 52.2 | 5.2 | 0 | 1 | 0 | 14 | 0 | 0 | 24 | 104 |
| 2 | calc | default | **47.8** ± 3.4 | 45.6 | 50.8 | 42.0 | 47.1 | 0.9 | 0 | 2 | 0 | 0 | 0 | 0 | 11 | 145 |
| 3 | naive | default | **22.6** ± 2.5 | 23.3 | 22.1 | 25.6 | 22.6 | 0.0 | 0 | 0 | 86 | 36 | 132 | 0 | 165 | 0 |

## Is #1 really better? Paired on the same test scenarios

- #1 vs calc default: +4.7 ± 1.5 points on 83 scenarios (clearly better)
- #1 vs naive: +29.8 ± 3.4 points on 83 scenarios (clearly better)

Differences within two standard errors are noise: more seeds or scenarios, or treat them as a tie.

## Where the winner (#1) is weak, next to the baselines

| By case type | bundling | capacity | price_increase | quality | raw_material | renewal | rfq |
|---|---|---|---|---|---|---|---|
| #1 | 56.3 | 57.4 | 49.5 | 56.1 | 41.4 | 48.8 | 56.4 |
| calc default | 49.6 | 51.2 | 45.5 | 53.0 | 35.5 | 42.7 | 45.6 |
| naive | 20.3 | 18.7 | 27.4 | 26.7 | 17.1 | 23.9 | 26.5 |

| By goal | leverage | quality_first | routine | secure_supply | stabilise |
|---|---|---|---|---|---|
| #1 | 43.5 | 62.3 | 48.5 | 53.5 | 58.2 |
| calc default | 38.6 | 56.2 | 42.0 | 47.3 | 49.6 |
| naive | 21.6 | 21.4 | 19.6 | 24.3 | 28.3 |

| By supplier archetype | capacity | family | generous | group | job_shop | monopolist | quality | trader | twin |
|---|---|---|---|---|---|---|---|---|---|
| #1 | 51.7 | 56.4 | 64.5 | 45.5 | 59.9 | 37.4 | 49.4 | 36.7 | 64.5 |
| calc default | 46.8 | 48.9 | 57.8 | 40.5 | 53.5 | 32.9 | 43.4 | 29.6 | 50.8 |
| naive | 17.7 | 26.3 | 48.1 | 16.5 | 29.0 | 7.6 | 21.0 | 21.3 | 22.1 |

| By edge case | all_fields | case_facts | case_file | current_contract | falling_index | no_bid | opening_breaks_must_have | per_100 | price_only | short_rounds | single_order | three_years | walk_away_best |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| #1 | 45.8 | 67.4 | 51.8 | 54.4 | 69.5 | 63.1 | 50.6 | 42.3 | 57.7 | 51.9 | 46.1 | 52.7 | 100.0 |
| calc default | 44.4 | 56.1 | 42.0 | 50.5 | 60.2 | 54.4 | 46.9 | 29.3 | 52.3 | 47.0 | 37.9 | 48.1 | 100.0 |
| naive | 18.5 | 20.9 | 25.6 | 13.5 | 21.5 | 32.2 | 12.6 | 13.3 | 38.1 | 20.9 | 20.8 | 24.5 | 24.0 |

| Per twin | D01 | D02 | P01 | P02 | P03 | P04 | P05 | P07 | P08 | P10 | P11 | P18 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| #1 | 90.5 | 62.1 | 75.2 | 7.9 | 93.5 | 86.0 | 53.6 | 80.5 | 48.9 | 68.6 | 68.1 | 39.5 |
| calc default | 86.4 | 12.7 | 56.0 | 10.2 | 93.5 | 80.7 | 15.1 | 78.3 | 24.5 | 52.0 | 61.6 | 38.2 |
| naive | 26.6 | 23.4 | 64.7 | 14.4 | 9.6 | 78.2 | 0.0 | 13.0 | 22.3 | 0.0 | 0.0 | 13.3 |

Run: `python -m sellm.lab compare naive calc sellm.agent:make_agent --label final-81`, 8 s, options {'clock': True, 'mode': 'parallel', 'wave_cap_s': 480, 'think_s': 2.0, 'vary': True, 'reader': 'keywords', 'supplier': 'engine', 'no_cache': False}.
