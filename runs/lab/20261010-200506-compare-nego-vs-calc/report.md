# Lab compare 20261010-200506-compare-nego-vs-calc: naive vs calc vs sellm.agent:make_agent

1032 negotiations on 172 scenarios. Scores x 100. **Test** = scenarios the search never saw (held-out twins P04/P10/P18 and freshly generated ones): rank by it. Train = what the search tuned on. Worst 10 % = mean of the worst tenth of scenarios. Counts are per negotiation: crashes and refused moves (422) would cost cases in the final; broken must-haves and deals worse than the opening score 0; 'below alt' = ended under what walking away would have scored.

| # | Strategy | Knobs | Test ± SE | Train | Twins | Case files | Invented | Worst 10 % | Crash | 422 | Broken | Worse | Below alt | Wave cap | Timeouts | No deal |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | calc | default | **48.2** ± 3.0 | 44.0 | 50.8 | 43.5 | 46.9 | 0.6 | 0 | 0 | 0 | 0 | 0 | 0 | 5 | 91 |
| 2 | sellm.agent:make_agent | default | **47.2** ± 3.0 | 45.4 | 60.7 | 43.0 | 46.0 | 2.6 | 0 | 1 | 0 | 11 | 0 | 0 | 30 | 74 |
| 3 | naive | default | **23.8** ± 2.2 | 22.8 | 22.1 | 27.5 | 22.6 | 0.0 | 0 | 0 | 66 | 18 | 78 | 0 | 113 | 0 |

## Is #1 really better? Paired on the same test scenarios

- #1 vs sellm.agent:make_agent: +1.0 ± 1.4 points on 103 scenarios (not distinguishable)
- #1 vs naive: +24.4 ± 3.2 points on 103 scenarios (clearly better)

Differences within two standard errors are noise: more seeds or scenarios, or treat them as a tie.

## Where the winner (#1) is weak, next to the baselines

| By case type | bundling | capacity | price_increase | quality | raw_material | renewal | rfq |
|---|---|---|---|---|---|---|---|
| #1 | 51.8 | 54.7 | 45.9 | 49.8 | 38.7 | 44.5 | 42.7 |
| sellm.agent:make_agent | 50.5 | 49.5 | 47.0 | 49.4 | 36.5 | 42.8 | 47.8 |
| naive | 22.0 | 16.7 | 26.2 | 26.0 | 18.8 | 25.3 | 25.7 |

| By goal | leverage | quality_first | routine | secure_supply | stabilise |
|---|---|---|---|---|---|
| #1 | 39.0 | 55.1 | 42.5 | 52.7 | 48.3 |
| sellm.agent:make_agent | 38.2 | 53.9 | 40.6 | 50.4 | 55.2 |
| naive | 20.6 | 23.4 | 20.8 | 25.0 | 29.6 |

| By supplier archetype | capacity | family | generous | group | job_shop | monopolist | quality | trader | twin |
|---|---|---|---|---|---|---|---|---|---|
| #1 | 47.2 | 48.4 | 63.9 | 42.5 | 54.4 | 13.8 | 47.5 | 30.6 | 50.8 |
| sellm.agent:make_agent | 48.8 | 50.0 | 56.2 | 40.6 | 53.0 | 11.8 | 46.7 | 27.9 | 60.7 |
| naive | 15.0 | 26.4 | 41.6 | 16.2 | 32.2 | 4.4 | 26.1 | 18.7 | 22.1 |

| By edge case | all_fields | case_facts | case_file | current_contract | falling_index | no_bid | opening_breaks_must_have | per_100 | price_only | short_rounds | single_order | three_years | walk_away_best |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| #1 | 38.6 | 58.4 | 43.5 | 50.6 | 56.8 | 54.7 | 42.5 | 29.1 | 58.7 | 54.1 | 48.2 | 54.9 | 100.0 |
| sellm.agent:make_agent | 38.6 | 59.0 | 43.0 | 50.5 | 54.8 | 54.6 | 38.7 | 30.8 | 56.4 | 51.4 | 47.1 | 54.4 | 100.0 |
| naive | 20.9 | 26.3 | 27.5 | 11.0 | 19.8 | 32.1 | 12.1 | 13.6 | 33.4 | 18.8 | 23.6 | 24.8 | 27.8 |

| Per twin | D01 | D02 | P01 | P02 | P03 | P04 | P05 | P07 | P08 | P10 | P11 | P18 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| #1 | 86.4 | 12.7 | 56.0 | 10.2 | 93.5 | 80.7 | 15.1 | 78.3 | 24.5 | 52.0 | 61.6 | 38.2 |
| sellm.agent:make_agent | 95.7 | 61.3 | 69.7 | 16.0 | 94.7 | 76.6 | 50.2 | 65.4 | 38.2 | 67.9 | 61.1 | 31.0 |
| naive | 26.6 | 23.4 | 64.7 | 14.4 | 9.6 | 78.2 | 0.0 | 13.0 | 22.3 | 0.0 | 0.0 | 13.3 |

Run: `python -m sellm.lab compare naive calc sellm.agent:make_agent --invented 60 --test 100 --seeds 2 --label nego-vs-calc`, 13 s, options {'clock': True, 'mode': 'parallel', 'wave_cap_s': 480, 'think_s': 2.0, 'vary': True, 'reader': 'keywords', 'supplier': 'engine', 'no_cache': False}.
