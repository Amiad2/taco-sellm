# Stress test: sellm.agent:make_agent 
**FAIL** (FAIL = any crash, refused move or broken must-have; the rest are warnings)

## sequential (the kit runner): mean 56.7 over 204 scenarios, 408 negotiations

| Check | Count | Worst scenarios |
|---|---|---|
| crashes | 0 | - |
| rejected | 5 | X07-037 (no_bid, case_facts); X07-044 (case_file); X07-087 (invented); X07-104 (case_file) |
| broken | 0 | - |
| worse | 21 | X07-033 (short_rounds); X07-055 (no_bid, current_contract); X07-076 (invented); X71-001 (walk_away_best) |
| below_alt | 4 | X71-001 (walk_away_best); X71-002 (walk_away_best) |
| wave_cap | 0 | - |
| timeouts | 179 | D02 (twin); P05 (twin); X07-005 (walk_away_best, no_bid); X07-006 (invented) |

By edge case: falling_index 46, three_years 52, short_rounds 54, current_contract 55, case_facts 55, case_file 57, all_fields 58, single_order 59, price_only 59, per_100 61, no_bid 67, opening_breaks_must_have 68, walk_away_best 91

By archetype: capacity 36, monopolist 38, trader 50, group 50, job_shop 58, family 60, quality 60, twin 65, generous 74

By case type: renewal 49, raw_material 54, bundling 54, rfq 55, capacity 60, price_increase 61, quality 62

Our time per negotiation: median 0.02 s, max 0.19 s.

## parallel (one loop per thread): mean 57.6 over 204 scenarios, 408 negotiations

| Check | Count | Worst scenarios |
|---|---|---|
| crashes | 0 | - |
| rejected | 1 | X07-083 (invented) |
| broken | 0 | - |
| worse | 14 | X07-033 (short_rounds); X71-001 (walk_away_best); X71-002 (walk_away_best); X76-001 (three_years) |
| below_alt | 4 | X71-001 (walk_away_best); X71-002 (walk_away_best) |
| wave_cap | 0 | - |
| timeouts | 35 | D02 (twin); P05 (twin); X07-005 (walk_away_best, no_bid); X07-057 (opening_breaks_must_have, per_100, single_order) |

By edge case: falling_index 46, three_years 54, short_rounds 56, case_file 57, case_facts 57, all_fields 58, single_order 60, price_only 61, current_contract 62, per_100 63, opening_breaks_must_have 68, no_bid 70, walk_away_best 91

By archetype: monopolist 38, capacity 45, group 50, trader 53, family 61, quality 62, job_shop 62, twin 65, generous 74

By case type: renewal 49, raw_material 54, bundling 54, rfq 59, capacity 60, price_increase 61, quality 62

Our time per negotiation: median 0.02 s, max 0.23 s.

