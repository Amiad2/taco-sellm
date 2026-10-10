# Lab compare 20261010-184910-compare-test-clone1: calc vs sellm.lab.clone_agent:CloneAgent

1008 negotiations on 252 scenarios. Scores x 100. **Test** = scenarios the search never saw (held-out twins P04/P10/P18 and freshly generated ones): rank by it. Train = what the search tuned on. Worst 10 % = mean of the worst tenth of scenarios. Counts are per negotiation: crashes and refused moves (422) would cost cases in the final; broken must-haves and deals worse than the opening score 0; 'below alt' = ended under what walking away would have scored.

| # | Strategy | Knobs | Test ± SE | Train | Twins | Case files | Invented | Worst 10 % | Crash | 422 | Broken | Worse | Below alt | Wave cap | Timeouts | No deal |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | calc | default | **52.6** ± 3.2 | 52.5 | 54.6 | 48.3 | 53.4 | 5.7 | 0 | 2 | 0 | 0 | 2 | 0 | 10 | 112 |
| 2 | sellm.lab.clone_agent:CloneAgent | default | **0.0** ± 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 504 | 0 | 0 | 0 | 0 | 0 | 0 | 504 |

## Is #1 really better? Paired on the same test scenarios

- #1 vs sellm.lab.clone_agent:CloneAgent: +52.6 ± 3.2 points on 83 scenarios (clearly better)

Differences within two standard errors are noise: more seeds or scenarios, or treat them as a tie.

## Where the winner (#1) is weak, next to the baselines

| By case type | bundling | capacity | price_increase | quality | raw_material | renewal | rfq |
|---|---|---|---|---|---|---|---|
| #1 | 55.3 | 59.3 | 52.9 | 57.4 | 38.8 | 49.4 | 52.9 |
| sellm.lab.clone_agent:CloneAgent | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |

| By goal | leverage | quality_first | routine | secure_supply | stabilise |
|---|---|---|---|---|---|
| #1 | 42.8 | 61.5 | 49.6 | 55.0 | 56.2 |
| sellm.lab.clone_agent:CloneAgent | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |

| By supplier archetype | capacity | family | generous | group | job_shop | monopolist | quality | trader | twin |
|---|---|---|---|---|---|---|---|---|---|
| #1 | 51.5 | 56.1 | 65.6 | 45.2 | 61.9 | 34.8 | 47.1 | 37.8 | 54.6 |
| sellm.lab.clone_agent:CloneAgent | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |

| By edge case | all_fields | case_facts | case_file | current_contract | falling_index | no_bid | opening_breaks_must_have | per_100 | price_only | short_rounds | single_order | three_years | walk_away_best |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| #1 | 48.0 | 60.8 | 48.3 | 54.6 | 65.1 | 62.9 | 52.7 | 39.4 | 59.3 | 54.0 | 46.0 | 54.8 | 97.4 |
| sellm.lab.clone_agent:CloneAgent | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |

| Per twin | D01 | D02 | P01 | P02 | P03 | P04 | P05 | P07 | P08 | P10 | P11 | P18 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| #1 | 91.5 | 25.1 | 57.0 | 24.2 | 89.6 | 80.7 | 13.5 | 73.3 | 22.6 | 70.0 | 74.3 | 34.0 |
| sellm.lab.clone_agent:CloneAgent | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |

## Crashes (504), first ones

- sellm.lab.clone_agent:CloneAgent on D01 ([]): `AttributeError: 'NoneType' object has no attribute 'get'`
- sellm.lab.clone_agent:CloneAgent on D01 ([]): `AttributeError: 'NoneType' object has no attribute 'get'`
- sellm.lab.clone_agent:CloneAgent on D02 ([]): `AttributeError: 'NoneType' object has no attribute 'get'`
- sellm.lab.clone_agent:CloneAgent on D02 ([]): `AttributeError: 'NoneType' object has no attribute 'get'`
- sellm.lab.clone_agent:CloneAgent on P01 ([]): `AttributeError: 'NoneType' object has no attribute 'get'`

Run: `python -m sellm.lab compare calc sellm.lab.clone_agent:CloneAgent --invented 160 --test 80 --seeds 2 --label test-clone1`, 13 s, options {'clock': True, 'mode': 'parallel', 'wave_cap_s': 480, 'think_s': 2.0, 'vary': True, 'reader': 'keywords', 'supplier': 'engine', 'no_cache': False}.
