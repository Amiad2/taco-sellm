# Lab compare 20261011-031741-compare-s2-vs-main: sellm.agent:make_agent vs sellm2.agent:make_agent

1008 negotiations on 252 scenarios. Scores x 100. **Test** = scenarios the search never saw (held-out twins P04/P10/P18 and freshly generated ones): rank by it. Train = what the search tuned on. Worst 10 % = mean of the worst tenth of scenarios. Counts are per negotiation: crashes and refused moves (422) would cost cases in the final; broken must-haves and deals worse than the opening score 0; 'below alt' = ended under what walking away would have scored.

| # | Strategy | Knobs | Test ± SE | Train | Twins | Case files | Invented | Worst 10 % | Crash | 422 | Broken | Worse | Below alt | Wave cap | Timeouts | No deal |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | sellm.agent:make_agent | default | **53.3** ± 3.3 | 53.2 | 71.6 | 51.3 | 52.5 | 5.0 | 0 | 1 | 0 | 15 | 0 | 0 | 7 | 104 |
| 2 | sellm2.agent:make_agent | default | **50.3** ± 3.5 | 52.1 | 69.2 | 51.5 | 50.5 | 2.4 | 0 | 0 | 0 | 12 | 0 | 0 | 9 | 120 |

## Is #1 really better? Paired on the same test scenarios

- #1 vs sellm2.agent:make_agent: +2.9 ± 1.8 points on 83 scenarios (not distinguishable)

Differences within two standard errors are noise: more seeds or scenarios, or treat them as a tie.

## Where the winner (#1) is weak, next to the baselines

| By case type | bundling | capacity | price_increase | quality | raw_material | renewal | rfq |
|---|---|---|---|---|---|---|---|
| #1 | 56.2 | 56.3 | 53.1 | 57.6 | 41.7 | 49.0 | 55.9 |
| sellm2.agent:make_agent | 51.9 | 54.6 | 49.3 | 56.3 | 41.4 | 50.5 | 54.8 |

| By goal | leverage | quality_first | routine | secure_supply | stabilise |
|---|---|---|---|---|---|
| #1 | 44.1 | 62.5 | 48.6 | 53.3 | 59.8 |
| sellm2.agent:make_agent | 43.5 | 60.7 | 46.0 | 52.1 | 57.5 |

| By supplier archetype | capacity | family | generous | group | job_shop | monopolist | quality | trader | twin |
|---|---|---|---|---|---|---|---|---|---|
| #1 | 51.6 | 56.8 | 67.1 | 45.1 | 59.8 | 37.5 | 48.9 | 35.4 | 71.6 |
| sellm2.agent:make_agent | 51.3 | 56.3 | 54.4 | 43.4 | 56.6 | 36.0 | 50.7 | 35.9 | 69.2 |

| By edge case | all_fields | case_facts | case_file | current_contract | falling_index | no_bid | opening_breaks_must_have | per_100 | price_only | short_rounds | single_order | three_years | walk_away_best |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| #1 | 47.1 | 67.6 | 51.3 | 54.6 | 70.0 | 62.4 | 49.3 | 40.7 | 58.2 | 50.5 | 46.0 | 52.5 | 100.0 |
| sellm2.agent:make_agent | 42.6 | 65.0 | 51.5 | 55.0 | 68.8 | 62.6 | 47.3 | 40.0 | 57.7 | 50.5 | 41.7 | 53.2 | 100.0 |

| Per twin | D01 | D02 | P01 | P02 | P03 | P04 | P05 | P07 | P08 | P10 | P11 | P18 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| #1 | 89.6 | 40.4 | 90.6 | 55.6 | 91.8 | 86.0 | 68.9 | 76.0 | 58.6 | 74.7 | 80.6 | 46.7 |
| sellm2.agent:make_agent | 89.6 | 41.5 | 90.6 | 25.8 | 91.8 | 86.0 | 74.6 | 76.0 | 58.6 | 68.2 | 80.6 | 46.7 |

Run: `python -m sellm.lab compare sellm.agent:make_agent sellm2.agent:make_agent --label s2-vs-main`, 54 s, options {'clock': True, 'mode': 'parallel', 'wave_cap_s': 480, 'think_s': 2.0, 'vary': True, 'reader': 'keywords', 'supplier': 'engine', 'no_cache': False}.
