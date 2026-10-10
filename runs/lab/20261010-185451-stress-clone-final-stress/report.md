# Stress test: sellm.lab.clone_agent:CloneAgent 
**FAIL** (FAIL = any crash, refused move or broken must-have; the rest are warnings)

## sequential (the kit runner): mean 59.7 over 204 scenarios, 408 negotiations

| Check | Count | Worst scenarios |
|---|---|---|
| crashes | 0 | - |
| rejected | 3 | X07-083 (invented); X75-000 (per_100); X80-001 (price_only) |
| broken | 0 | - |
| worse | 3 | X07-011 (invented); X80-004 (price_only) |
| below_alt | 0 | - |
| wave_cap | 0 | - |
| timeouts | 171 | D02 (twin); P05 (twin); X07-005 (walk_away_best, no_bid); X07-006 (invented) |

By edge case: falling_index 51, three_years 53, current_contract 56, short_rounds 56, case_facts 57, case_file 58, price_only 61, all_fields 61, per_100 67, single_order 69, opening_breaks_must_have 70, no_bid 71, walk_away_best 100

By archetype: capacity 47, monopolist 48, trader 49, group 51, quality 61, twin 61, family 64, job_shop 65, generous 73

By case type: raw_material 57, renewal 58, capacity 58, quality 59, rfq 60, bundling 61, price_increase 63

Our time per negotiation: median 0.30 s, max 13.65 s.

## parallel (one loop per thread): mean 59.6 over 204 scenarios, 408 negotiations

| Check | Count | Worst scenarios |
|---|---|---|
| crashes | 0 | - |
| rejected | 0 | - |
| broken | 0 | - |
| worse | 3 | X07-011 (invented); X80-004 (price_only) |
| below_alt | 0 | - |
| wave_cap | 0 | - |
| timeouts | 17 | D02 (twin); P05 (twin); X07-005 (walk_away_best, no_bid); X07-037 (no_bid, case_facts) |

By edge case: falling_index 51, three_years 55, case_file 58, current_contract 58, short_rounds 59, case_facts 60, all_fields 61, price_only 62, per_100 68, opening_breaks_must_have 70, single_order 71, no_bid 71, walk_away_best 100

By archetype: capacity 47, monopolist 47, group 50, trader 53, twin 61, quality 63, family 63, job_shop 65, generous 75

By case type: raw_material 57, renewal 58, capacity 58, quality 59, rfq 60, bundling 61, price_increase 63

Our time per negotiation: median 0.31 s, max 20.42 s.

