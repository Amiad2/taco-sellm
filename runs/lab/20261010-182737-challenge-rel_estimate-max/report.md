# Challenge 20261010-182737-challenge-rel_estimate-max

Challenger = champion (sellm/agent.py KNOBS) + `{"rel_estimate": "max"}`
Options {'clock': True, 'mode': 'parallel', 'wave_cap_s': 480, 'think_s': 2.0, 'vary': True, 'reader': 'keywords', 'supplier': 'engine', 'no_cache': False}; 163 test scenarios x 2 seeds.

**REJECT: clearly worse**: -3.5 ± 1.1 points (paired)

| | Test | Twins | Case files | Invented | Worst 10 % | Crash | 422 | Broken | Worse | No deal |
|---|---|---|---|---|---|---|---|---|---|---|
| champion | 56.9 | 65.8 | 56.6 | 56.7 | 7.9 | 0 | 1 | 0 | 0 | 72 |
| challenger | 53.4 | 61.6 | 48.2 | 54.3 | 5.7 | 0 | 2 | 0 | 0 | 73 |

By case type (champion / challenger): bundling 62/60, capacity 56/58, price_increase 57/53, quality 59/54, raw_material 47/48, renewal 56/50, rfq 57/51
