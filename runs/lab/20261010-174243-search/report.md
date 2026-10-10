# Lab search 20261010-174243-search: 1 min, 64 random variants to start

3779 negotiations on 252 scenarios. Scores x 100. **Test** = scenarios the search never saw (held-out twins P04/P10/P18 and freshly generated ones): rank by it. Train = what the search tuned on. Worst 10 % = mean of the worst tenth of scenarios. Counts are per negotiation: crashes and refused moves (422) would cost cases in the final; broken must-haves and deals worse than the opening score 0; 'below alt' = ended under what walking away would have scored.

| # | Strategy | Knobs | Test ± SE | Train | Twins | Case files | Invented | Worst 10 % | Crash | 422 | Broken | Worse | Below alt | Wave cap | Timeouts | No deal |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | calc | accept_gap=0.0, after_final=push, ask_breakdown=True, claims=cost, floor_guess=0.8, guess_rate=0.08, open_below=0.0, shape=1.0, sheets=1, steps=6, structure=joint, take_alternative=True, tone=neutral, use_should_cost=False | **54.5** ± 3.2 | 50.4 | 57.3 | 50.4 | 54.3 | 4.5 | 0 | 0 | 0 | 0 | 0 | 0 | 2 | 68 |
| 2 | calc | accept_gap=0.01, after_final=accept, ask_breakdown=True, claims=cost, floor_guess=0.8, guess_rate=0.2, open_below=0.03, shape=2.0, sheets=2, steps=6, structure=joint, take_alternative=True, tone=neutral, use_should_cost=False | **54.4** ± 3.2 | 46.5 | 62.3 | 49.3 | 53.2 | 3.7 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 69 |
| 3 | calc | accept_gap=0.005, after_final=push, ask_breakdown=True, claims=bank, floor_guess=0.88, guess_rate=0.08, open_below=0.06, shape=0.5, sheets=3, steps=7, structure=joint, take_alternative=False, tone=neutral, use_should_cost=False | **53.9** ± 3.2 | 43.1 | 64.4 | 49.6 | 51.7 | 3.5 | 0 | 0 | 0 | 0 | 0 | 0 | 7 | 76 |
| 4 | calc | default | **53.2** ± 3.2 | 45.1 | 59.0 | 48.9 | 51.9 | 4.5 | 0 | 2 | 0 | 0 | 0 | 0 | 3 | 69 |
| 5 | calc | accept_gap=0.0, after_final=accept, ask_breakdown=False, claims=none, floor_guess=0.8, guess_rate=0.2, open_below=0.03, shape=2.0, sheets=3, steps=8, structure=buyer, take_alternative=False, tone=neutral, use_should_cost=False | **52.6** ± 3.3 | 41.9 | 55.6 | 44.6 | 51.6 | 3.8 | 0 | 1 | 0 | 0 | 0 | 0 | 8 | 73 |
| 6 | calc | accept_gap=0.0, after_final=accept, ask_breakdown=False, claims=cost, floor_guess=0.85, guess_rate=0.06, open_below=0.03, shape=1.0, sheets=3, steps=5, structure=keep, take_alternative=True, tone=neutral, use_should_cost=True | **47.6** ± 3.4 | 47.6 | 43.8 | 44.1 | 48.5 | 0.4 | 0 | 14 | 0 | 0 | 0 | 0 | 12 | 93 |
| 7 | calc | accept_gap=0.0, after_final=hold, ask_breakdown=True, claims=bank, floor_guess=0.8, guess_rate=0.06, open_below=0.03, shape=2.0, sheets=2, steps=4, structure=keep, take_alternative=False, tone=warm, use_should_cost=False | **46.5** ± 3.6 | 44.2 | 34.6 | 41.1 | 47.5 | 0.0 | 0 | 0 | 0 | 0 | 0 | 0 | 13 | 101 |
| 8 | calc | accept_gap=0.002, after_final=hold, ask_breakdown=True, claims=bank, floor_guess=0.92, guess_rate=0.12, open_below=0.03, shape=0.5, sheets=2, steps=7, structure=keep, take_alternative=True, tone=warm, use_should_cost=False | **41.4** ± 3.5 | 44.8 | 32.8 | 38.8 | 43.1 | 0.0 | 0 | 1 | 0 | 0 | 0 | 0 | 10 | 110 |
| 9 | naive | default | **25.2** ± 2.6 | 26.6 | 22.1 | 28.8 | 25.8 | 0.0 | 0 | 0 | 106 | 29 | 153 | 0 | 176 | 0 |
| 10 | calc | accept_gap=0.002, after_final=push, ask_breakdown=True, claims=cost, floor_guess=0.95, guess_rate=0.06, open_below=0.0, shape=0.5, sheets=1, steps=5, structure=keep, take_alternative=True, tone=neutral, use_should_cost=False | **-** ± - | 35.2 | - | 34.3 | 35.5 | 5.1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 11 |
| 11 | calc | accept_gap=0.0, after_final=push, ask_breakdown=False, claims=none, floor_guess=0.8, guess_rate=0.2, open_below=0.1, shape=1.0, sheets=2, steps=4, structure=joint, take_alternative=False, tone=hard, use_should_cost=True | **-** ± - | 31.4 | - | 31.4 | 31.4 | 0.0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 19 |
| 12 | calc | accept_gap=0.005, after_final=accept, ask_breakdown=True, claims=cost, floor_guess=0.85, guess_rate=0.08, open_below=0.06, shape=2.0, sheets=2, steps=3, structure=keep, take_alternative=True, tone=hard, use_should_cost=False | **-** ± - | 40.2 | - | 41.6 | 39.8 | 0.0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 11 |

## Is #1 really better? Paired on the same test scenarios

- #1 vs #2: +0.1 ± 0.4 points on 83 scenarios (not distinguishable)
- #1 vs #3: +0.6 ± 0.9 points on 83 scenarios (not distinguishable)
- #1 vs calc default: +1.3 ± 0.7 points on 83 scenarios (not distinguishable)
- #1 vs naive: +29.3 ± 3.3 points on 83 scenarios (clearly better)

Differences within two standard errors are noise: more seeds or scenarios, or treat them as a tie.

## Where the winner (#1) is weak, next to the baselines

| By case type | bundling | capacity | price_increase | quality | raw_material | renewal | rfq |
|---|---|---|---|---|---|---|---|
| #1 | 59.5 | 59.6 | 59.5 | 51.5 | 40.5 | 47.6 | 58.0 |
| calc default | 59.2 | 60.6 | 58.4 | 50.0 | 39.3 | 44.9 | 51.3 |
| naive | 23.2 | 23.0 | 30.3 | 28.6 | 18.7 | 26.5 | 31.1 |

| By goal | leverage | quality_first | routine | secure_supply | stabilise |
|---|---|---|---|---|---|
| #1 | 43.5 | 67.2 | 55.7 | 54.1 | 49.5 |
| calc default | 42.8 | 65.6 | 53.3 | 50.4 | 46.6 |
| naive | 23.7 | 24.4 | 22.7 | 27.3 | 32.8 |

| By supplier archetype | capacity | family | generous | group | job_shop | monopolist | quality | trader | twin |
|---|---|---|---|---|---|---|---|---|---|
| #1 | 45.4 | 59.8 | 62.7 | 45.9 | 68.4 | 13.3 | 52.8 | 45.0 | 57.3 |
| calc default | 44.8 | 55.7 | 42.9 | 44.8 | 64.4 | 13.8 | 53.9 | 41.6 | 59.0 |
| naive | 21.5 | 28.7 | 50.8 | 19.7 | 34.5 | 9.2 | 29.7 | 24.8 | 22.1 |

| By edge case | all_fields | case_facts | case_file | current_contract | falling_index | no_bid | opening_breaks_must_have | per_100 | price_only | short_rounds | single_order | three_years | walk_away_best |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| #1 | 51.3 | 54.7 | 50.4 | 59.5 | 63.9 | 65.4 | 41.4 | 47.0 | 59.1 | 64.1 | 46.8 | 63.1 | 100.0 |
| calc default | 49.1 | 47.2 | 48.9 | 57.5 | 56.6 | 57.3 | 40.9 | 47.6 | 57.1 | 63.4 | 42.3 | 62.1 | 100.0 |
| naive | 21.4 | 24.0 | 28.8 | 15.4 | 25.3 | 36.4 | 13.9 | 17.8 | 42.7 | 25.2 | 23.3 | 27.5 | 26.9 |

| Per twin | D01 | D02 | P01 | P02 | P03 | P04 | P05 | P07 | P08 | P10 | P11 | P18 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| #1 | - | - | - | - | - | 80.7 | - | - | - | 57.1 | - | 34.2 |
| calc default | - | - | - | - | - | 80.7 | - | - | - | 62.0 | - | 34.2 |
| naive | 25.0 | 22.6 | 58.6 | 28.1 | 6.4 | 78.2 | 0.0 | 10.9 | 22.8 | 0.0 | 0.0 | 12.9 |

Run: `python -m sellm.lab search --minutes 1.0 --start 64 --invented 160 --test 80 --seeds 2 --mode parallel --wave-cap 480.0 --think 2.0 --reader keywords --invent-seed 1`, 144 s, options {'clock': True, 'mode': 'parallel', 'wave_cap_s': 480.0, 'think_s': 2.0, 'vary': True, 'reader': 'keywords'}.
