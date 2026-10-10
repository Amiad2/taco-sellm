# Challenge 20261010-203021-challenge-ablation

Challenger = champion (sellm/agent.py KNOBS) + `{"floor_guess": 0.88}`
Options {'clock': True, 'mode': 'parallel', 'wave_cap_s': 480, 'think_s': 2.0, 'vary': True, 'reader': 'keywords', 'supplier': 'engine', 'no_cache': False}; 163 test scenarios x 2 seeds.

**ADOPT: clearly better**: +1.5 ± 0.7 points (paired)

| | Test | Twins | Case files | Invented | Worst 10 % | Crash | 422 | Broken | Worse | No deal |
|---|---|---|---|---|---|---|---|---|---|---|
| champion | 44.4 | 57.5 | 41.9 | 44.7 | 0.9 | 0 | 1 | 0 | 0 | 100 |
| challenger | 45.9 | 57.3 | 44.3 | 46.0 | 0.9 | 0 | 1 | 0 | 0 | 100 |

By case type (champion / challenger): bundling 50/52, capacity 46/47, price_increase 44/48, quality 46/45, raw_material 40/41, renewal 44/45, rfq 41/42
