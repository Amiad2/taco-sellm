# Stress test: sellm.agent:make_agent 
**PASS** (FAIL = any crash, refused move or broken must-have; the rest are warnings)

## sequential (the kit runner): mean 54.0 over 284 scenarios, 568 negotiations

| Check | Count | Worst scenarios |
|---|---|---|
| crashes | 0 | - |
| rejected | 0 | - |
| broken | 0 | - |
| worse | 25 | X07-001 (case_file); X07-033 (short_rounds); X07-069 (invented); X07-076 (invented) |
| below_alt | 0 | - |
| wave_cap | 0 | - |
| timeouts | 207 | D02 (twin); P05 (twin); X07-005 (walk_away_best, no_bid); X07-006 (invented) |

By edge case: current_contract 43, three_years 44, falling_index 45, short_rounds 46, case_facts 48, single_order 51, case_file 52, per_100 55, all_fields 56, no_bid 57, price_only 63, opening_breaks_must_have 64, walk_away_best 100

By archetype: capacity 30, monopolist 43, group 45, quality 51, trader 54, job_shop 57, family 57, twin 64, generous 72

By case type: renewal 47, rfq 52, quality 55, capacity 55, price_increase 56, raw_material 56, bundling 57

Our time per negotiation: median 0.10 s, max 3.22 s.

## parallel (one loop per thread): mean 54.4 over 284 scenarios, 568 negotiations

| Check | Count | Worst scenarios |
|---|---|---|
| crashes | 0 | - |
| rejected | 0 | - |
| broken | 0 | - |
| worse | 22 | X07-001 (case_file); X07-033 (short_rounds); X07-069 (invented); X07-106 (opening_breaks_must_have) |
| below_alt | 0 | - |
| wave_cap | 0 | - |
| timeouts | 9 | D02 (twin); X07-049 (short_rounds, per_100, falling_index); X07-083 (invented); X73-002 (no_bid) |

By edge case: falling_index 45, three_years 46, current_contract 47, short_rounds 48, case_facts 51, case_file 52, single_order 53, all_fields 55, per_100 56, no_bid 57, opening_breaks_must_have 63, price_only 63, walk_away_best 100

By archetype: capacity 33, monopolist 43, group 45, quality 53, trader 56, family 58, job_shop 59, twin 66, generous 71

By case type: renewal 47, rfq 54, quality 55, capacity 55, price_increase 56, raw_material 56, bundling 57

Our time per negotiation: median 0.11 s, max 3.74 s.

