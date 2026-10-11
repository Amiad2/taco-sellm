# SESSION_HANDOFF - omars_branch, Sun 11 Oct 2026 04:40 CEST

**Where the team stands (04:40):** the frontier is `jonathans_branch@8a854c4`, **80.3** through the final
runner (tag `best-jonathans_branch-80.3`, planner live with `SELLM_PLAN=llm`). It contains everything
adopted on this branch (E2g, the runner's one loop per case, its clock guard and slot wait) and builds
on its findings (a second index series is a new fact; price-history windows). `omars_branch@0466bcf`
(75.4 through the final runner) is a strict subset. Amiad proposes `sellm2` (76.4, `amiads_branch`).
This branch plays no more practice sessions (27 used).

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

- **Branch `omars_branch`**, validated version `0466bcf` (tag `best-omars_branch-75.4-runner`); later
  commits are ledger, docs and merges of `main` only. Working tree clean, pushed.
- Changes of this session: `sellm/negotiator.py` (knobs `contract`, `idx_recent` + `hedged`, `gate` +
  `dismissed`, `idx_window`, `refill` + `gap`; only `idx_recent` is on), `sellm/runner.py` (`serial`,
  `turns`, CLI default one loop per case, clock guard for waiting bidders, wait for a free session slot),
  `sellm/agent.py` (KNOBS), `tests/test_runner.py` (+6 tests), `tests/test_endgame.py` (KNOBS pin),
  merge of `jonathans_branch@67001e7`; `experiments/structure_args.py`, `combined_replay.py`,
  `LEDGER.md`. Tests: 206+ passed, 1 skipped; `ruff check .` only reports the old I001 in
  `sellm/lab/p02_c_agents.py` (not ours).
- **All adopted changes are in `jonathans_branch`** (checked with `git merge-base --is-ancestor` for
  `c5c2d53`, `f60a212`, `4912998`, `0c60254`). Nothing of this branch is on `main` except docs and runs;
  `main`'s agent is still `@7a49c38` (72.9) with one loop per thread.
- Known issues: P11's last accept is path-sensitive (0.778 vs 0.710 on changed histories). `.env` on
  Omar's machine has `OPENAI_API_KEY` but the code reads `LLM_API_KEY` - matters for the planner
  (`SELLM_PLAN=llm`) of jonathans_branch if it is run from this machine.

## 4. Arena results (all measured; one session per case unless noted)

| ID | Change | Result | Decision |
|---|---|---|---|
| E0 | reference `@7a49c38` | 72.9 (P01 .969 P02 .531 P03 .923 P04 .860 P05 .820 P07 .747 P08 .549 P10 .647 P11 .778 P18 .467) | - |
| E1 | contract = horizon (24 not 36 months) | P08 0.538 (0.549): the clause is demanded at 24 months too | rejected |
| E2 | recent index fall as argument | P18 **0.520** (0.467), P08 **0.438** (0.549, "not our reality: covered at fixed prices") | -> E2g |
| E2g | E2 + hedge guard | P08 = reference by replay; P05 0.820 (C1) | **adopted** |
| E3 | leave out facts the dossier predicts are dismissed | P08 0.515, P07 0.734, P03 0.923, P18 0.567 (net 0) | rejected |
| E4 | cite the larger window of a falling index | P01 0.997, P11 0.710 twice, P05 0.820 (net -0.04) | rejected here; jonathans_branch uses it only for an index the supplier blames |
| E5 | fill a round without a new fact (duplicate, question) | P07 0.740, P08 0.515, P03 0.923 | rejected |
| R1 | runner, one POST per session in flight | P05 0.735, 0 timeouts (was 0.665) | -> R2 |
| R2 | runner, one loop per case (agent picks thread) | P05 0.820 = kit runner, 3 s | **adopted (runner default)** |
| C1 | merge clause offer + E2g | P05 0.820; nine cases by exact replay -> 75.4 | candidate |
| V1/V1b | the candidate, ten cases in parallel through the final runner | **75.4, every case as predicted**; P07/P10 first lost to `429 at most 10 open sessions` | runner now waits for a slot |

Sandbox with the candidate through the runner: D01 0.947, D02 0.567 (free). Lab stress of the agent
at `a5b363c`: PASS (`runs/lab/20261011-020037-stress-omar-sellm-a5b/`). Team frontier after this:
`jonathans_branch@8a854c4` 80.3 (its ledger `experiments/LEDGER-JONATHAN.md`, J1-J10).

## 5. Budget

- Omar's budget: **50 arena runs; 1 run = 1 practice session** (`POST /v1/sessions` on a hosted case;
  a full practice run = 10; a case whose session never opened costs nothing). Sandbox D01/D02 and
  `arena-sim` are free and not counted.
- **This session: 27 practice sessions** (ledger, one line per session). The previous session on this
  branch used 21. If the 50 includes those: 48 used, 2 left; if not: 27 used, 23 left. The ledger
  kept within 29 to be safe under both readings; **Omar should say which one he meant.**
- Team quota (shared, 450 per rolling 24 h): 188 left at 03:08; Jonathan's night search stops at 100
  left; keep 40 for Sunday.

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
- Tested since on jonathans_branch (`experiments/LEDGER-JONATHAN.md`): a second fallen index series is a
  new fact (J1: P18 0.598, P08 0.637 - the hedge covers only the hedged material); the price-history
  pair around the supplier's last price jump moves it (J8/J9: P08 0.814, P03 0.956, P18 0.657); two
  facts in the first e-mail lose (J5); promises and questions do not buy price (J-ontime, E5).
- Untested: news and letter-based facts on hidden suppliers; reacting to a dismissal in the same
  thread; the stated drivers of strangers that are not cost drivers of the part (risk: 'irrelevant').

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

1. **Team decision before 11:00: which version goes to `main`.** Measured through the final runner:
   `jonathans_branch@8a854c4` **80.3** (needs `SELLM_PLAN=llm` and an LLM key on the final machine for
   `idx_blamed`; without the planner P01 plays 0.969, i.e. ~80.0), `amiads_branch` `sellm2` 76.4,
   `omars_branch@0466bcf` 75.4 (a subset of jonathans_branch). On this evidence jonathans_branch is
   the strongest; it also carries this branch's runner fixes.
2. **Sun 08:00 data release** (group B, Omar): `scripts/sync`, `uv run arena data`,
   `uv run python -m sellm.intel build`, `check`, `verify` (must PASS), read new letters/news for signal
   wording (`material covered`, cash, capacity), commit `sellm/dossiers` on `main`; the chosen branch
   merges `main`. Then replay the practice cases on the chosen version to see what the rebuild changed.
3. Then `scripts/preflight` and the rehearsal on the final machine; final command
   `nohup uv run python -m sellm.runner --set final --agent sellm > runs/logs/final.out 2>&1 &`
   (one loop per case is the default). Nobody plays practice/sandbox on the key during the final.
- Open questions: how the hedge and dismissal signals look in the Sunday data for the hidden pool;
  whether 3-bidder RFQs stay inside 8 minutes under load (jonathans_branch's J10 drops a far-behind
  bidder for that reason; the runner closes 90 s before the cap).

## 10. Repository handoff

- `omars_branch` (tracks `origin/omars_branch`); validated version `0466bcf`, tags
  `best-omars_branch-75.4-runner` (`0466bcf`) and `best-omars_branch-75.4` (`f473d97`, agent only).
  Reference before this session: `a5b363c` (= behaviour of `@7a49c38`, 72.9).
- Restore: `git switch -c restore-<hash> <hash>`; bring back with `git revert` or a merge; never
  `git reset --hard` over pushed work, never force-push. Turn a rule off by removing it from `KNOBS`;
  the old runner loops with `--per-thread`.
- Shared files (`docs/`, `runs/`) live on `main`: switch, `scripts/sync`, change, commit, sync, switch
  back, `git merge main` (take `main`'s `runs/labels.json` on conflict).
