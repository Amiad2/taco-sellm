# Stress test: sellm2.agent:make_agent 
**PASS** (FAIL = any crash, refused move or broken must-have; the rest are warnings)

## sequential (the kit runner): mean 52.6 over 204 scenarios, 408 negotiations

| Check | Count | Worst scenarios |
|---|---|---|
| crashes | 0 | - |
| rejected | 0 | - |
| broken | 0 | - |
| worse | 19 | X07-033 (short_rounds); X07-069 (invented); X07-076 (invented); X07-106 (opening_breaks_must_have) |
| below_alt | 0 | - |
| wave_cap | 0 | - |
| timeouts | 164 | D02 (twin); P05 (twin); X07-005 (walk_away_best, no_bid); X07-006 (invented) |

By edge case: current_contract 36, three_years 44, single_order 48, per_100 51, falling_index 52, case_file 52, short_rounds 52, all_fields 53, case_facts 53, price_only 57, opening_breaks_must_have 58, no_bid 59, walk_away_best 100

By archetype: capacity 34, monopolist 40, group 46, trader 48, family 53, job_shop 55, quality 57, generous 65, twin 69

By case type: capacity 49, renewal 50, bundling 50, raw_material 51, rfq 54, quality 55, price_increase 59

Our time per negotiation: median 0.06 s, max 1.14 s.

## parallel (one loop per thread): mean 52.9 over 204 scenarios, 408 negotiations

| Check | Count | Worst scenarios |
|---|---|---|
| crashes | 0 | - |
| rejected | 0 | - |
| broken | 0 | - |
| worse | 18 | X07-033 (short_rounds); X07-069 (invented); X07-106 (opening_breaks_must_have); X72-004 (short_rounds) |
| below_alt | 0 | - |
| wave_cap | 0 | - |
| timeouts | 9 | X07-083 (invented); X72-001 (short_rounds); X73-002 (no_bid); X76-002 (three_years) |

By edge case: current_contract 43, three_years 47, single_order 50, case_file 52, falling_index 52, per_100 52, all_fields 53, short_rounds 56, price_only 56, case_facts 57, opening_breaks_must_have 58, no_bid 59, walk_away_best 100

By archetype: capacity 39, monopolist 40, group 46, trader 53, family 53, job_shop 57, quality 61, generous 64, twin 69

By case type: capacity 49, renewal 50, bundling 50, raw_material 51, rfq 55, quality 55, price_increase 59

Our time per negotiation: median 0.06 s, max 1.45 s.

