# Stress test: sellm.agent:make_agent 
**FAIL** (FAIL = any crash, refused move or broken must-have; the rest are warnings)

## sequential (the kit runner): mean 54.3 over 284 scenarios, 568 negotiations

| Check | Count | Worst scenarios |
|---|---|---|
| crashes | 0 | - |
| rejected | 0 | - |
| broken | 0 | - |
| worse | 22 | X07-033 (short_rounds); X07-069 (invented); X07-106 (opening_breaks_must_have); X07-148 (case_facts, falling_index) |
| below_alt | 0 | - |
| wave_cap | 0 | - |
| timeouts | 233 | D02 (twin); P05 (twin); X07-005 (walk_away_best, no_bid); X07-006 (invented) |

By edge case: three_years 43, falling_index 44, current_contract 45, short_rounds 47, case_facts 48, case_file 51, single_order 52, per_100 55, all_fields 57, no_bid 58, price_only 62, opening_breaks_must_have 64, walk_away_best 100

By archetype: capacity 33, monopolist 43, group 45, quality 51, trader 54, job_shop 58, family 58, twin 64, generous 74

By case type: renewal 48, rfq 53, price_increase 55, quality 55, capacity 55, raw_material 56, bundling 57

Our time per negotiation: median 0.10 s, max 3.61 s.

## parallel (one loop per thread): mean 54.4 over 284 scenarios, 568 negotiations

| Check | Count | Worst scenarios |
|---|---|---|
| crashes | 0 | - |
| rejected | 1 | X07-083 (invented) |
| broken | 0 | - |
| worse | 20 | X07-033 (short_rounds); X07-069 (invented); X07-106 (opening_breaks_must_have); X07-148 (case_facts, falling_index) |
| below_alt | 0 | - |
| wave_cap | 0 | - |
| timeouts | 21 | D02 (twin); P05 (twin); X07-006 (invented); X07-037 (no_bid, case_facts) |

By edge case: falling_index 44, three_years 45, current_contract 48, short_rounds 50, case_file 51, case_facts 51, single_order 54, per_100 56, all_fields 57, no_bid 58, price_only 61, opening_breaks_must_have 64, walk_away_best 100

By archetype: capacity 33, monopolist 43, group 45, quality 54, trader 57, family 58, job_shop 59, twin 64, generous 72

By case type: renewal 48, rfq 54, price_increase 55, quality 55, capacity 55, raw_material 56, bundling 57

Our time per negotiation: median 0.10 s, max 3.07 s.

