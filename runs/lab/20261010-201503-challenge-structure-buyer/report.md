# Challenge 20261010-201503-challenge-structure-buyer

Challenger = champion (sellm/agent.py KNOBS) + `{"structure": "buyer"}`
Options {'clock': True, 'mode': 'parallel', 'wave_cap_s': 480, 'think_s': 2.0, 'vary': True, 'reader': 'keywords', 'supplier': 'engine', 'no_cache': False}; 163 test scenarios x 2 seeds.

**TIE: not distinguishable**: -1.1 ± 0.7 points (paired)

| | Test | Twins | Case files | Invented | Worst 10 % | Crash | 422 | Broken | Worse | No deal |
|---|---|---|---|---|---|---|---|---|---|---|
| champion | 44.4 | 57.5 | 41.9 | 44.7 | 0.9 | 0 | 1 | 0 | 0 | 100 |
| challenger | 43.3 | 55.1 | 36.0 | 44.6 | 0.8 | 0 | 1 | 0 | 0 | 101 |

By case type (champion / challenger): bundling 50/51, capacity 46/36, price_increase 44/45, quality 46/45, raw_material 40/39, renewal 44/43, rfq 41/41
