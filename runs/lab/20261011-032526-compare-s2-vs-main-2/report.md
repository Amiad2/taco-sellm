# Lab compare 20261011-032526-compare-s2-vs-main-2: sellm.agent:make_agent vs sellm2.agent:make_agent

1008 negotiations on 252 scenarios. Scores x 100. **Test** = scenarios the search never saw (held-out twins P04/P10/P18 and freshly generated ones): rank by it. Train = what the search tuned on. Worst 10 % = mean of the worst tenth of scenarios. Counts are per negotiation: crashes and refused moves (422) would cost cases in the final; broken must-haves and deals worse than the opening score 0; 'below alt' = ended under what walking away would have scored.

| # | Strategy | Knobs | Test ± SE | Train | Twins | Case files | Invented | Worst 10 % | Crash | 422 | Broken | Worse | Below alt | Wave cap | Timeouts | No deal |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | sellm.agent:make_agent | default | **53.3** ± 3.3 | 53.2 | 71.6 | 51.3 | 52.5 | 5.0 | 0 | 1 | 0 | 15 | 0 | 0 | 7 | 104 |
| 2 | sellm2.agent:make_agent | default | **51.5** ± 3.4 | 53.5 | 68.6 | 52.4 | 51.9 | 4.6 | 0 | 1 | 0 | 14 | 0 | 0 | 11 | 104 |

## Is #1 really better? Paired on the same test scenarios

- #1 vs sellm2.agent:make_agent: +1.8 ± 1.0 points on 83 scenarios (not distinguishable)

Differences within two standard errors are noise: more seeds or scenarios, or treat them as a tie.

## Where the winner (#1) is weak, next to the baselines

| By case type | bundling | capacity | price_increase | quality | raw_material | renewal | rfq |
|---|---|---|---|---|---|---|---|
| #1 | 56.2 | 56.3 | 53.1 | 57.6 | 41.7 | 49.0 | 55.9 |
| sellm2.agent:make_agent | 55.6 | 58.3 | 50.5 | 55.2 | 41.5 | 48.8 | 56.8 |

| By goal | leverage | quality_first | routine | secure_supply | stabilise |
|---|---|---|---|---|---|
| #1 | 44.1 | 62.5 | 48.6 | 53.3 | 59.8 |
| sellm2.agent:make_agent | 43.4 | 62.3 | 47.2 | 54.0 | 59.5 |

| By supplier archetype | capacity | family | generous | group | job_shop | monopolist | quality | trader | twin |
|---|---|---|---|---|---|---|---|---|---|
| #1 | 51.6 | 56.8 | 67.1 | 45.1 | 59.8 | 37.5 | 48.9 | 35.4 | 71.6 |
| sellm2.agent:make_agent | 51.6 | 56.9 | 64.5 | 45.7 | 59.3 | 37.1 | 48.5 | 37.3 | 68.6 |

| By edge case | all_fields | case_facts | case_file | current_contract | falling_index | no_bid | opening_breaks_must_have | per_100 | price_only | short_rounds | single_order | three_years | walk_away_best |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| #1 | 47.1 | 67.6 | 51.3 | 54.6 | 70.0 | 62.4 | 49.3 | 40.7 | 58.2 | 50.5 | 46.0 | 52.5 | 100.0 |
| sellm2.agent:make_agent | 45.8 | 64.8 | 52.4 | 53.1 | 68.8 | 63.4 | 50.1 | 41.7 | 57.7 | 52.6 | 42.9 | 52.7 | 100.0 |

| Per twin | D01 | D02 | P01 | P02 | P03 | P04 | P05 | P07 | P08 | P10 | P11 | P18 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| #1 | 89.6 | 40.4 | 90.6 | 55.6 | 91.8 | 86.0 | 68.9 | 76.0 | 58.6 | 74.7 | 80.6 | 46.7 |
| sellm2.agent:make_agent | 89.6 | 34.5 | 90.6 | 25.8 | 92.0 | 86.0 | 74.6 | 76.0 | 58.6 | 68.2 | 80.6 | 46.7 |

Run: `python -m sellm.lab compare sellm.agent:make_agent sellm2.agent:make_agent --label s2-vs-main-2`, 45 s, options {'clock': True, 'mode': 'parallel', 'wave_cap_s': 480, 'think_s': 2.0, 'vary': True, 'reader': 'keywords', 'supplier': 'engine', 'no_cache': False}.
