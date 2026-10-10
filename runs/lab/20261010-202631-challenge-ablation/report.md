# Challenge 20261010-202631-challenge-ablation

Challenger = champion (sellm/agent.py KNOBS) + `{"accept_gap": 0.002}`
Options {'clock': True, 'mode': 'parallel', 'wave_cap_s': 480, 'think_s': 2.0, 'vary': True, 'reader': 'keywords', 'supplier': 'engine', 'no_cache': False}; 163 test scenarios x 2 seeds.

**TIE: not distinguishable**: -0.0 ± 0.0 points (paired)

| | Test | Twins | Case files | Invented | Worst 10 % | Crash | 422 | Broken | Worse | No deal |
|---|---|---|---|---|---|---|---|---|---|---|
| champion | 44.4 | 57.5 | 41.9 | 44.7 | 0.9 | 0 | 1 | 0 | 0 | 100 |
| challenger | 44.4 | 57.5 | 42.0 | 44.6 | 0.9 | 0 | 1 | 0 | 0 | 100 |

By case type (champion / challenger): bundling 50/50, capacity 46/46, price_increase 44/44, quality 46/46, raw_material 40/40, renewal 44/44, rfq 41/41
