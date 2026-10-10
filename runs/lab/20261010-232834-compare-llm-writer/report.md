# Lab compare 20261010-232834-compare-llm-writer: sellm.agent:make_agent vs experiments.llm_writer:make_agent

24 negotiations on 12 scenarios. Scores x 100. **Test** = scenarios the search never saw (held-out twins P04/P10/P18 and freshly generated ones): rank by it. Train = what the search tuned on. Worst 10 % = mean of the worst tenth of scenarios. Counts are per negotiation: crashes and refused moves (422) would cost cases in the final; broken must-haves and deals worse than the opening score 0; 'below alt' = ended under what walking away would have scored.

| # | Strategy | Knobs | Test ± SE | Train | Twins | Case files | Invented | Worst 10 % | Crash | 422 | Broken | Worse | Below alt | Wave cap | Timeouts | No deal |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | sellm.agent:make_agent | default | **64.7** ± 12.7 | 65.3 | 65.2 | - | - | 28.1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 2 | experiments.llm_writer:make_agent | default | **55.8** ± 20.0 | 64.1 | 62.0 | - | - | 17.0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

## Is #1 really better? Paired on the same test scenarios

- #1 vs experiments.llm_writer:make_agent: +8.9 ± 7.6 points on 3 scenarios (not distinguishable)

Differences within two standard errors are noise: more seeds or scenarios, or treat them as a tie.

## Where the winner (#1) is weak, next to the baselines

| By case type | bundling | capacity | price_increase | quality | raw_material | renewal | rfq |
|---|---|---|---|---|---|---|---|
| #1 | 81.8 | 66.0 | 67.4 | 67.6 | 45.3 | 90.1 | 46.7 |
| experiments.llm_writer:make_agent | 80.5 | 63.3 | 62.7 | 69.3 | 33.2 | 90.2 | 48.1 |

| By goal | leverage | quality_first | routine | secure_supply | stabilise |
|---|---|---|---|---|---|
| #1 | 46.0 | 67.6 | 83.9 | 66.0 | 74.1 |
| experiments.llm_writer:make_agent | 40.7 | 69.3 | 83.3 | 63.3 | 70.6 |

| By supplier archetype | twin |
|---|---|
| #1 | 65.2 |
| experiments.llm_writer:make_agent | 62.0 |

| Per twin | D01 | D02 | P01 | P02 | P03 | P04 | P05 | P07 | P08 | P10 | P11 | P18 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| #1 | 91.3 | 63.1 | 82.7 | 28.1 | 94.2 | 86.0 | 30.4 | 81.8 | 48.4 | 66.0 | 67.6 | 42.1 |
| experiments.llm_writer:make_agent | 91.3 | 65.8 | 79.8 | 17.0 | 94.3 | 86.0 | 30.4 | 80.5 | 48.4 | 63.3 | 69.3 | 18.1 |

Run: `python -m sellm.lab compare sellm.agent:make_agent experiments.llm_writer:make_agent --supplier llm --fixed-twins --invented 0 --test 0 --seeds 1 --think -1 --workers 4 --label llm-writer`, 339 s, options {'clock': True, 'mode': 'parallel', 'wave_cap_s': 480, 'think_s': None, 'vary': False, 'reader': 'keywords', 'supplier': 'llm', 'no_cache': False}.
