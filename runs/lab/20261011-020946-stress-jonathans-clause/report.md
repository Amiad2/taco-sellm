# Stress test: sellm.agent:make_agent 
**PASS** (FAIL = any crash, refused move or broken must-have; the rest are warnings)

## sequential (the kit runner): mean 55.6 over 204 scenarios, 408 negotiations

| Check | Count | Worst scenarios |
|---|---|---|
| crashes | 0 | - |
| rejected | 0 | - |
| broken | 0 | - |
| worse | 21 | X07-001 (case_file); X07-033 (short_rounds); X07-069 (invented); X07-076 (invented) |
| below_alt | 0 | - |
| wave_cap | 0 | - |
| timeouts | 174 | D02 (twin); P05 (twin); X07-005 (walk_away_best, no_bid); X07-006 (invented) |

By edge case: current_contract 45, three_years 50, falling_index 51, short_rounds 52, case_file 53, single_order 56, case_facts 56, per_100 57, price_only 58, all_fields 59, no_bid 67, opening_breaks_must_have 68, walk_away_best 100

By archetype: capacity 33, trader 46, group 47, monopolist 47, quality 57, job_shop 57, family 60, twin 63, generous 73

By case type: raw_material 52, capacity 53, renewal 53, quality 56, bundling 57, rfq 57, price_increase 58

Our time per negotiation: median 0.04 s, max 1.69 s.

## parallel (one loop per thread): mean 56.1 over 204 scenarios, 408 negotiations

| Check | Count | Worst scenarios |
|---|---|---|
| crashes | 0 | - |
| rejected | 0 | - |
| broken | 0 | - |
| worse | 18 | X07-001 (case_file); X07-033 (short_rounds); X07-069 (invented); X07-106 (opening_breaks_must_have) |
| below_alt | 0 | - |
| wave_cap | 0 | - |
| timeouts | 9 | D02 (twin); X07-049 (short_rounds, per_100, falling_index); X07-083 (invented); X73-002 (no_bid) |

By edge case: falling_index 51, current_contract 51, case_file 52, three_years 53, short_rounds 56, per_100 58, single_order 58, price_only 58, all_fields 59, case_facts 60, no_bid 67, opening_breaks_must_have 68, walk_away_best 100

By archetype: capacity 38, group 47, monopolist 48, trader 50, job_shop 60, quality 60, family 61, twin 64, generous 72

By case type: raw_material 52, capacity 53, renewal 53, quality 56, bundling 57, price_increase 58, rfq 60

Our time per negotiation: median 0.04 s, max 1.58 s.

