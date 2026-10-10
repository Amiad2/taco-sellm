# Stress test: calc {'structure': 'joint', 'guess_rate': 0.2, 'floor_guess': 0.85, 'use_should_cost': False, 'open_below': 0.1, 'steps': 8, 'shape': 0.75, 'sheets': 3, 'take_alternative': False, 'after_final': 'accept', 'claims': 'bank', 'tone': 'warm', 'ask_breakdown': False, 'accept_gap': 0.01}
**FAIL** (FAIL = any crash, refused move or broken must-have; the rest are warnings)

## sequential (the kit runner): mean 58.4 over 204 scenarios, 408 negotiations

| Check | Count | Worst scenarios |
|---|---|---|
| crashes | 0 | - |
| rejected | 3 | X75-000 (per_100); X78-000 (falling_index); X80-001 (price_only) |
| broken | 0 | - |
| worse | 5 | X07-011 (invented); X71-002 (walk_away_best); X80-004 (price_only) |
| below_alt | 6 | X07-038 (invented); X71-001 (walk_away_best); X71-002 (walk_away_best) |
| wave_cap | 0 | - |
| timeouts | 175 | D02 (twin); P05 (twin); X07-005 (walk_away_best, no_bid); X07-006 (invented) |

By edge case: falling_index 51, case_facts 53, three_years 54, all_fields 57, short_rounds 57, case_file 57, current_contract 58, price_only 61, per_100 68, opening_breaks_must_have 68, single_order 68, no_bid 71, walk_away_best 92

By archetype: monopolist 42, trader 43, capacity 47, group 52, family 61, quality 61, twin 63, job_shop 64, generous 76

By case type: capacity 57, raw_material 57, rfq 58, bundling 58, renewal 58, quality 60, price_increase 64

Our time per negotiation: median 0.30 s, max 17.12 s.

## parallel (one loop per thread): mean 58.8 over 204 scenarios, 408 negotiations

| Check | Count | Worst scenarios |
|---|---|---|
| crashes | 0 | - |
| rejected | 0 | - |
| broken | 0 | - |
| worse | 5 | X07-011 (invented); X71-002 (walk_away_best); X80-004 (price_only) |
| below_alt | 6 | X07-038 (invented); X71-001 (walk_away_best); X71-002 (walk_away_best) |
| wave_cap | 0 | - |
| timeouts | 20 | D02 (twin); P05 (twin); X07-005 (walk_away_best, no_bid); X07-006 (invented) |

By edge case: falling_index 51, case_facts 56, three_years 56, all_fields 57, case_file 57, short_rounds 59, current_contract 60, price_only 61, opening_breaks_must_have 68, per_100 68, single_order 70, no_bid 71, walk_away_best 92

By archetype: monopolist 43, trader 46, capacity 47, group 52, twin 61, family 61, quality 63, job_shop 65, generous 78

By case type: capacity 57, raw_material 57, bundling 58, renewal 58, rfq 59, quality 60, price_increase 64

Our time per negotiation: median 0.31 s, max 16.21 s.

