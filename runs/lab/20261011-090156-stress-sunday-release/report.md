# Stress test: sellm.agent:make_agent 
**FAIL** (FAIL = any crash, refused move or broken must-have; the rest are warnings)

## sequential (the kit runner): mean 55.9 over 204 scenarios, 408 negotiations

| Check | Count | Worst scenarios |
|---|---|---|
| crashes | 0 | - |
| rejected | 0 | - |
| broken | 0 | - |
| worse | 18 | X07-033 (short_rounds); X07-069 (invented); X07-106 (opening_breaks_must_have); X74-003 (case_facts) |
| below_alt | 0 | - |
| wave_cap | 0 | - |
| timeouts | 187 | D02 (twin); P05 (twin); X07-005 (walk_away_best, no_bid); X07-006 (invented) |

By edge case: current_contract 48, three_years 49, falling_index 50, case_file 51, short_rounds 54, single_order 56, case_facts 56, per_100 57, price_only 57, all_fields 60, opening_breaks_must_have 68, no_bid 69, walk_away_best 100

By archetype: capacity 38, group 47, trader 47, monopolist 47, quality 57, job_shop 58, family 61, twin 64, generous 75

By case type: capacity 52, raw_material 53, renewal 53, bundling 56, quality 57, price_increase 58, rfq 59

Our time per negotiation: median 0.05 s, max 1.67 s.

## parallel (one loop per thread): mean 56.1 over 204 scenarios, 408 negotiations

| Check | Count | Worst scenarios |
|---|---|---|
| crashes | 0 | - |
| rejected | 1 | X07-083 (invented) |
| broken | 0 | - |
| worse | 16 | X07-033 (short_rounds); X07-069 (invented); X07-106 (opening_breaks_must_have); X74-003 (case_facts) |
| below_alt | 0 | - |
| wave_cap | 0 | - |
| timeouts | 17 | D02 (twin); P05 (twin); X07-006 (invented); X07-037 (no_bid, case_facts) |

By edge case: falling_index 50, case_file 51, current_contract 52, three_years 52, price_only 56, per_100 58, short_rounds 58, single_order 59, all_fields 60, case_facts 60, no_bid 67, opening_breaks_must_have 68, walk_away_best 100

By archetype: capacity 38, group 47, monopolist 48, trader 52, job_shop 59, family 60, quality 61, twin 64, generous 73

By case type: capacity 52, raw_material 53, renewal 53, bundling 56, quality 57, price_increase 58, rfq 60

Our time per negotiation: median 0.05 s, max 1.60 s.

