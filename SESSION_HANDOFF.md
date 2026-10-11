# SESSION_HANDOFF - omars_branch, Sun 11 Oct 2026 ~02:55 CEST

For the next agent on `omars_branch`. Written from the repo, `docs/LOG.md`, the arena traces and
`experiments/LEDGER.md` (every arena session of this research, with its commit). Measured results
are marked as such; anything else is labelled a hypothesis. The repo's memory stays authoritative:
`AGENTS.md` (rules, read first), `docs/CONTEXT.md` (the challenge), `docs/STATUS.md` (now),
`docs/LEARNINGS.md`, `docs/LOG.md`. The handoff before this one (01:45) is in git history (`2df3350`).

## 1. Objective and constraints

- Team sellm's buyer agent for the Tacto Negotiation Arena: it negotiates by e-mail over
  `https://arena.tacto.ai/v1` with hosted LLM supplier bots and accepts a standing term sheet or walks
  away. Only term sheets bind; unstated terms close on the supplier's standard terms.
- Case score `clip((C_open - C_deal) / (C_open - C_best), 0, 1)`; C = `arena_kit/cost.py`. Broken
  must-have or a deal worse than the opening = 0; no deal = the alternative's score.
- **Live Final Sun 12:00**: hidden cases, 5 waves of 8 min, every case weighs the same, points = sum of
  wave means x 100. No human in the loop; never call `/v1/events*`, `/screen`, `/leaderboard`,
  `/results`. One key, 10 open sessions, 10 calls/s, 60 s per message per thread. **Team freeze
  11:00, the final runs `main`** on Jonathan's MacBook. Sunday data release 08:00.

## 2. Architecture (unchanged in shape)

Runner -> agent -> negotiator -> template e-mail; no LLM in the default path.

1. **Runner** `sellm/runner.py` (`python -m sellm.runner --set final --agent sellm`). **New default on
   omars_branch: one loop per case, the agent picks the thread, one message of a session in flight**
   (`Limits.turns`/`serial`; `--per-thread` restores one loop per thread). Keeps the cap closing, resume,
   move deadline, holds, re-read before accept. The kit runner (`arena run`) plays the same order.
2. **Agent** `sellm/agent.py:make_agent` -> `sellm/endgame.py:Persistent` (subclass of
   `sellm/negotiator.py:Negotiator`) with `KNOBS = {past_target, fast_pay, clause_offer, idx_recent=2.0}`.
3. **Negotiator** `move()` -> ask / hold / take_alternative / accept / walk_away; `plan()` sizes the
   price path (first ask = target x 0.94, meet after 4 messages); `opening_structure()` picks the
   package with `sellm/calculator.py` (C of every option combination); `arguments()` sends one checked
   fact per e-mail: rival offer > own-plant should-cost > falling cost-driver index > `sellm/claims.py`
   bank (fixed order by case type). Every move is a pure function of case + threads.
4. **Knowledge**: `sellm/intel/` dossiers (46 suppliers in `sellm/dossiers/`, case overlay, signals
   such as `material_hedged`, `cash_short`, `list_price_fixed`); data via `arena_kit/data.py`.
5. **Rules on this branch** (all knobs, default off in `Negotiator.DEFAULTS`; on via `KNOBS`):
   - `clause_offer` (Jonathan, `sellm/endgame.py`, `sellm/planner.py`): with a relationship term and a
     fixed price at the supplier's cost, the index clause as a second sheet at our cost-optimal price.
   - `idx_recent=2.0` (this session, `Negotiator.index_claims`): cite the largest fall >= 2 % of a
     cost-driver index from its 12-month peak when its yearly change rose (today: AS-14404 -5.5 %,
     AS-14301 -7.6 %, PPI-C2431 -2.3 %), **not to a supplier whose dossier says `material_hedged`**
     (`Negotiator.hedged`). Off-path knobs kept for experiments: `contract`, `gate`, `idx_window`.

## 3. Implementation state

- **Branch `omars_branch`, candidate `f473d97` (tag `best-omars_branch-75.4`)**; HEAD adds only the
  experiment knob `idx_window` (off), ledger lines and merges of `main`. Working tree clean, pushed.
- Changes of this session: `sellm/negotiator.py` (knobs `contract`, `idx_recent` + `hedged`, `gate` +
  `dismissed`, `idx_window`), `sellm/runner.py` (`serial`, `turns`, CLI default), `sellm/agent.py`
  (KNOBS), `tests/test_runner.py` (+2 tests), `tests/test_endgame.py` (KNOBS pin), merge of
  `jonathans_branch@67001e7`; experiments `experiments/structure_args.py`, `combined_replay.py`,
  `LEDGER.md`. **205 tests pass, 1 skipped**; `ruff check .` only reports the old I001 in
  `sellm/lab/p02_c_agents.py` (not ours).
- **Not on `main` yet.** `main` still plays 72.9 (`@7a49c38` behaviour) with the old runner loops.
- Known issues: `.env` on Omar's machine has `OPENAI_API_KEY` but the code reads `LLM_API_KEY` (only
  matters if `SELLM_LLM` is set; it is off). P11's last accept is path-sensitive (0.778 vs 0.710).

## 4. Arena results (all measured; one session per case unless noted)

| ID | Change | Result | Decision |
|---|---|---|---|
| E0 | reference `@7a49c38` | 72.9 (P01 .969 P02 .531 P03 .923 P04 .860 P05 .820 P07 .747 P08 .549 P10 .647 P11 .778 P18 .467) | - |
| E1 | contract = horizon (24 not 36 months) | P08 0.538 (0.549): the clause is demanded at 24 months too | rejected |
| E2 | recent index fall as argument | P18 **0.520** (0.467), P08 **0.438** (0.549, "not our reality: covered at fixed prices") | -> E2g |
| E2g | E2 + hedge guard | P08 = reference by replay; P05 0.820 (C1) | **adopted** |
| E3 | leave out facts the dossier predicts are dismissed | P08 0.515, P07 0.734, P03 0.923, P18 0.567 (net 0) | rejected |
| E4 | cite the larger window of a falling index | P01 0.997, P11 0.710 twice, P05 0.820 (net -0.04) | rejected |
| R1 | runner, one POST per session in flight | P05 0.735, 0 timeouts (was 0.665) | -> R2 |
| R2 | runner, one loop per case (agent picks thread) | P05 0.820 = kit runner, 3 s | **adopted (runner default)** |
| C1 | merge clause offer + E2g | P05 0.820; nine cases by exact replay -> **75.4** | **candidate** |

Sandbox with the candidate through the runner: D01 0.947, D02 0.567 (free). Lab stress of the
agent at `a5b363c`: PASS (0 crashes, 0 refused, 0 broken; `runs/lab/20261011-020037-stress-omar-sellm-a5b/`).
Earlier results (price path, LLM writer/verdict, persistence): previous handoff in `2df3350`,
`experiments/PRICE-PATH.md`, `PERSISTENCE.md`, `LLM-ADVISOR.md`, `PRACTICE-ARMS.md`.

## 5. Budget

- Omar's budget: **50 arena runs; 1 run = 1 practice session** (`POST /v1/sessions` on a hosted case;
  a full practice run = 10). Sandbox D01/D02 and `arena-sim` are free and not counted.
- **This session: 14 practice sessions** (ledger). The previous session on this branch used 21. If the
  50 includes those: 35 used, 15 left; if not: 14 used, 36 left. The ledger plans to stay within 29
  for this session; **Omar should say which reading he meant.**
- Team quota (shared, 450 per rolling 24 h): left 225 at 02:35; keep 40 for Sunday.

## 6. Argumentation: what the data says

- Mechanism (`docs/CONTEXT.md` 7): a fact = data ID + our figure in one sentence; the arena checks it
  (`claim_results`), the supplier then decides whether it matters to it. Its trace says so: "it holds and
  we took it into account" / "we did not know that - a fair point" vs "it holds, but it does not change
  our calculation" / "that is not our reality: ...".
- **Measured, causal (same e-mails except the fact):** a recent AS-14404 fall moved P18 0.20 on the
  first counter; the same fact to a hedged supplier (P08) moved nothing and lost 0.111 (an earlier
  final offer). Earlier sessions: facts moved P01 (+0.084) and P02 (+0.238), not P04/P07/P08/P18;
  'irrelevant' facts cancel a verified one in the same e-mail (Jonathan, P02).
- **The dossier predicts acceptance (observational, `docs/LOG.md` 02:30):** material_hedged -> index
  dismissed; list_price_fixed (70620) -> everything dismissed (37/37); capacity_tight -> volume
  dismissed; informal_costing -> data taken; delivery records taken only with a delivery/quality
  problem signal. Acting on the last one (E3) did not pay: a round with no fact also ends suppliers.
- **Magnitude is not monotone** (E4): the larger fall helped P01 and hardened P11 (reproduced).
- Untested: news and letter-based facts on hidden suppliers; reacting to a dismissal in the same thread;
  two facts in one e-mail; the stated drivers of strangers that are not cost drivers of the part
  (risk: 'irrelevant').

## 7. Evaluation

```bash
export PATH="$HOME/.local/bin:$PATH"
uv run pytest -q                                        # 205 passed, 1 skipped (~2.5 min)
uv run python -m experiments.structure_args replay E4    # which recorded cases a variant changes (free)
uv run python -m experiments.combined_replay             # today's KNOBS vs the measured sessions (free)
uv run python -m experiments.structure_args arena E2g --cases P18   # 1 practice session, ledger line
uv run python -m sellm.runner --set practice --cases P05 --label "..."   # through the final runner
uv run python -m sellm.runner --set sandbox --cases D01 D02            # free
uv run arena me                                          # quota (free)
```

Practice suppliers answer identical e-mail histories with identical prices, so a variant only needs
sessions on the cases where replay shows a different e-mail; but the last accept/hold decision can
flip on a changed history (P11), so one session is evidence for that case, not for a supplier type.
Logs: `runs/<set>/<case>/*.{md,json}` (traces with supplier reasons), `runs/logs/` (runner),
`experiments/results/2026-10-11-structure-args.json`.

## 8. Discoveries and what not to repeat

- RFQ timeouts came from parallel messages in one session, not from slow decisions: one message in
  flight in the agent's order fixes them (R2). Do not run the final with one loop per thread.
- Contract length beyond the horizon is neither priced nor rewarded by P07/P08/P10 suppliers (E1).
- Do not re-test: E1-E4 above, the price path (horizon, first ask, oracle; `PRICE-PATH.md`), LLM
  writer/verdict, pushes after a final offer.

## 9. Next steps (highest value first)

1. **Merge the candidate into `main` before 11:00** (team decision; it is jonathans_branch's 74.9 +
   E2g + the runner default). Then `scripts/preflight` on the final machine; final command
   `python -m sellm.runner --set final --agent sellm` (one loop per case is the default).
2. **Sun 08:00 data release** (group B, Omar): `scripts/sync`, `uv run arena data`,
   `uv run python -m sellm.intel build`, `check`, `verify` (must PASS), read new letters/news for
   signal wording (`material covered`, cash, capacity), commit `sellm/dossiers` on `main`. Then
   `experiments/combined_replay.py` to see whether the rebuild changed any practice move.
3. Optional, if budget is agreed: one full practice run of the merged `main` through the final runner
   as the rehearsal (10 sessions).
- Open questions: how the hedge and dismissal signals look in the Sunday data for the hidden pool;
  whether hidden RFQs with 3 bidders stay inside 8 minutes under load (R1 replies took up to 47 s
  while teammates ran a full run; the runner closes 90 s before the cap).

## 10. Repository handoff

- `omars_branch` (tracks `origin/omars_branch`), candidate `f473d97`, tag `best-omars_branch-75.4`.
  Reference before this session: `a5b363c` (= behaviour of `@7a49c38`, 72.9).
- Restore: `git switch -c restore-<hash> <hash>`; bring back with `git revert` or a merge; never
  `git reset --hard` over pushed work, never force-push. Turn a rule off by removing it from `KNOBS`.
- Shared files (`docs/`, `runs/`) live on `main`: switch, `scripts/sync`, change, commit, sync, switch
  back, `git merge main` (take `main`'s `runs/labels.json` on conflict).
