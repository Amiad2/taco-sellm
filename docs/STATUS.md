# STATUS - where we are right now

Keep this file short and true. Edit it in place; history belongs in `docs/LOG.md`.
Last updated: 2026-10-10 22:00 CEST by Jonathan (Claude Code).

## Now

- Repo is set up on the official starter kit; tests pass (31 passed, 1 skipped).
- Team key works: team **sellm**, active. `uv run arena me` is the source of truth for quota and best scores.
- **OpenAI works with the kit's LLM agent** (`LLM_PROVIDER=openai`, model `gpt-6.1-sol`, Sat 15:00): D01 scored 0.786 against 0.200 for the naive agent, no `LLM failed` in the log. Each machine needs the values in its own `.env`; `llm_from_env` was not changed.
- The kit's LLM agent is the baseline to beat: **61.5** over the 10 hosted cases (`runs/BASELINE.md`).
- **`--agent sellm` plays the negotiator with the cost calculator** (`sellm/negotiator.py`, `sellm/calculator.py`, group A, Sat 21:15; no LLM, e-mails from a template). Every move is a pure function of case and threads. The first ask is the package the calculator prices cheapest at the expected end price (long term; payment days by the dossier's cash_pressure: late for 'low', the quoted days or faster for 'medium'/'high', two equal-cost offers for an unknown supplier); each step is sized from the thread; it accepts a final offer and walks away only when the alternative is better. **Practice, all 10 cases: 72.4 (baseline 61.5)**, with one checked fact per e-mail from `sellm/claims.py` and the dossier's signals setting how deep it opens. Sandbox with the earlier version: D01 0.920, D02 0.530. `uv run python -m sellm.calculator P08` prints a case's sheet. The old Calculator knobs stay in `sellm/agent.py` as `CALC_KNOBS`.
- **The final runner is `sellm/runner.py`** (group C, Sat 21:15): one loop per thread, the waves, closing before the cap, resume after a crash, a deadline per move, holding e-mails for threads left waiting, logs in `runs/logs/`. Final: `nohup uv run python -m sellm.runner --set final --agent sellm > runs/logs/final.out 2>&1 &`; measured runs: `--set sandbox|practice --cases ...`. On the 10 hosted cases it plays exactly what the kit runner plays (identical replies), and it fixes the RFQ problems: no refused accept, attachments that the arena holds behind another reply no longer block the case. Check a machine with `scripts/preflight`.
- Every session the team plays is saved in full under `runs/` by `scripts/pull-runs`. **Quota (checked Sat 21:58): limit 450, used 101, left 349; a session frees up 24 h after it was played** - the limit was raised from 200.
- Sandbox probes (33 free sessions) show how suppliers react: only the first sheet can be accepted, a final offer is final, the supplier mirrors the size of our concessions, RFQ threads need their own loops. Rules for the agent: `experiments/RESULTS.md` section 5.
- **Lab** (`sellm/lab/`, Sat 17:45; guide `sellm/lab/README.md`): test any agent locally, free, no quota. `scripts/lab play P01`, `scripts/lab compare naive calc`, `scripts/lab search 60` (background), `scripts/lab stress calc`, `scripts/lab status`. Scenarios: twins of our 15 played suppliers (families of plausible variants), the 9 unplayed practice case files with their real suppliers, and invented ones (all 7 types, all fields, 8 supplier archetypes, 12 edge cases). Simulated clock: 20-60 s replies, 60-s timeouts with re-issued offer IDs, 8-min wave cap; `--mode parallel` (one loop per thread) or `sequential` (the kit's `play()`). Backtest: 0.79 % mean error on 237 real replies; kit LLM agent 59.8 in the lab vs 61.5 in the arena (`runs/lab/BACKTEST.md`, `VALIDATION.md`). **Found: the kit's sequential `play()` times RFQ threads out and can crash on a stale offer ID; the final runner needs one loop per thread.**
- **Dossiers (group B, Sat 18:40)**: `sellm.intel.dossier(supplier_id, parts, case=, opening=, package=)` serves the 46 built dossiers (`sellm/dossiers/`, committed) plus the case overlay; strangers get a dossier from the case alone. `uv run python -m sellm.intel show 70130` prints one; `uv run python -m sellm.intel verify` runs checks V1-V10 (all PASS). Schema and rules: `docs/PLAN.md` section 10.
- Team memory is in place: `AGENTS.md`, `docs/CONTEXT.md`, this file, `docs/LEARNINGS.md`, `docs/LOG.md`.

## In progress (claim before you start, remove when done)

| Who | What | Files | Since |
|---|---|---|---|
| Amiad (Claude Code) | **Group C - Runner, arguments, measurement, final** (`docs/PLAN.md` section 3). Done: `sellm/runner.py` v1.2 (fake-arena tests, sandbox, one full practice run), `sellm/claims.py` (argument bank, dossiers rebuilt), `scripts/preflight`, README run section. Open: in P05 the runner scored 0.665 twice against the kit runner's 0.769 (the arena counts parallel messages as late, `[finding]` Sat 21:25) - next is a one-message-in-flight option; then the Sunday checklist, rehearsal on Jonathan's machine, submission text (`[handoff]` Sat 21:25). Also keeps the lab; the clone loop is paused | `sellm/runner.py`, `tests/test_runner.py`, `sellm/claims.py`, `tests/test_claims.py`, `scripts/preflight`, `sellm/lab/`, `scripts/lab`, `runs/lab/`, README run section | Sat 20:50 |
| Amiad (Claude Code) | **Playbooks (Sat 21:35, until about 01:00)**: per-case negotiator knob sets that reach 0.95+ in the lab (engine, then OpenAI suppliers), confirmed on practice with at most 25 sessions (no parallel run with Jonathan: I ask first), then a test of selecting a playbook from the dossier vs. one merged set on invented suppliers. Lab only until then; does not change `sellm/negotiator.py` | `sellm/lab/playbooks.py`, `runs/lab/playbooks/` | Sat 21:35 |
| Omar (Claude Code) | **Group B - Data**: built and verified (S0-S12). Open: the human check of the signals against blind labels (V11), the Sunday 08:00 rebuild. No arena calls | `sellm/intel/` (package), `sellm/dossiers/`, `tests/test_intel.py` | Sat 17:48 |
| Jonathan (Claude Code) | **Group A - Negotiation**: negotiator v1.1 is in (`[change]` Sat 20:35). Next: confirm on practice P07, P01, P02 (up to 10 sessions, each logged), then LLM wording as an opt-in experiment, reading the supplier's standard sentences. Plays the free sandbox itself | `sellm/negotiator.py`, `sellm/writer.py`, `sellm/llm.py`, `sellm/agent.py`, `tests/test_negotiator.py`, `experiments/ab_sandbox.py` | Sat 18:16 |

## Next up

**Jonathan: read the [handoff] of Sat 20:30 in docs/LOG.md** - the lab's supplier model changed at 20:03 (lowball
penalty), so earlier lab numbers are superseded; a comparison of the negotiator, the Calculator and Amiad's clone is
waiting for you to run.

**Group C (Amiad): the runner is in** - `sellm/runner.py`, see Now. Use it for every measured run of a case with several suppliers: the kit's `arena run` still serves one thread at a time (2 timeouts in P05 at 21:06).

**Decided Sat 17:41** (`docs/PLAN.md`): three groups with their tasks, priorities and the skills
they need (**section 3**: A negotiation, B data, C runner, arguments, measurement and final; C took
over the per-move deadline from A and the argument bank and research from B at 17:45),
and the **dossier and mini-dossier schema** (**section 10**: fields, frozen core fields, rules,
signal vocabulary). Build against section 10; add fields freely, rename core fields only by decision.

1. Each person claims one group in the table above: A Jonathan, B Omar, C Amiad.
   **For group A:** the stub is in. Code against
   `from sellm.intel import dossier; d = dossier(supplier_id, case["parts"], case=case, opening=threads, package=package)`.
   **It now serves real values** (Sat 18:37): the 46 built dossiers in `sellm/dossiers/` plus the case
   overlay (contact name, stated cost drivers checked against the index, quote-PDF terms, RFQ rivals'
   offers, case facts). For strangers it builds from the case alone. Never raises, ~1 ms per call.
   Try `uv run python -m sellm.intel show 70130`. Fields: `docs/PLAN.md` section 10.
2. Baseline and the sandbox probes H1-H3 are done (`runs/BASELINE.md`, `experiments/RESULTS.md`). Next probes: H12-H15 in `experiments/RESULTS.md` section 6 (H12, H13, H15 are free), then H4-H7 on practice cases, one session each.
3. Then follow the timeline in `docs/PLAN.md` section 4.
4. **Sunday 08:00, group B** (about 15 min, before our 11:00 freeze): `scripts/sync`; `uv run arena data`; `uv run python -m sellm.intel build`; `check` shows which dossiers changed; `verify` must PASS; read the new letters and news (`signals-report`) and add signal patterns for new wording; commit `sellm/dossiers` with a `[change]` log entry; `scripts/sync`.

## Scoreboard

**Full practice run with `--agent sellm` at 21:58 (@cdd9cf8: calculator, argument bank, dossier signals; no LLM, kit runner): mean 72.4** - 67.7 before the bank, baseline 61.5. At or above the baseline in 9 of 10 cases (P07 0.747 against 0.779). 36 cited facts verified, 3 duplicate, 0 contradicted; no timeout, no failed lookup. Every case scored exactly what the review session's arms had predicted (`experiments/PRACTICE-ARMS.md`). Still weak: P18 0.47, P02 0.53, P08 0.55. Details: `docs/LOG.md` Sat 22:00.

Generated, do not keep by hand: `runs/README.md` (per case `C_open`, `C_best`, our best, every
session). Baseline of the kit's LLM agent on all 10 hosted cases, Sat 15:27: **mean 61.5**.
Weakest: P02 0.105, P18 0.377, P08 0.433, P10 0.570. Analysis and hypotheses: `runs/BASELINE.md`.

## Decisions

- **Groups: A Jonathan, B Omar, C Amiad** (Sat 20:50). **The Live Final runs on Jonathan's machine** (MacBook; decided by Amiad Sat 20:45): the runner and the pre-flight must work on macOS, Jonathan starts the final.
- Work on `main`, small commits, `scripts/sync` after each one (`AGENTS.md`).
- **Pull before every run.** `arena play`, `arena run`, `scripts/pull-runs` and the probe scripts call `scripts/pull-first` themselves and restart on the new code; new runners must call `arena_kit.cli.pull_first()` (`AGENTS.md` section 2).
- Docs and logs are written in English: the jury and tum.ai read the repo.
- Our code lives in `sellm/` (lab in `sellm/lab/`, the agent's entry point `sellm/agent.py`); `arena_kit/` stays the kit except for `pull_first` and the `--agent sellm` registration.
- **LLM: OpenAI `gpt-6-sol`** for development and the final (`LLM_PROVIDER=openai`, `LLM_MODEL=gpt-6-sol` in every `.env`; decided Sat 17:50, Omar). Earlier runs (D01 0.786, baseline 61.5) are logged as `gpt-6.1-sol`: whoever ran them, check which model your `.env` had and log it.

## Open questions (need a human)

- Whose LLM key for the final, and is there budget for an hour of parallel play? (Model decided: `gpt-6-sol`.)
- Which agent plays the final? Proposed: `sellm` replaces `llm` only if its mean is higher in lab, sandbox and one full practice run including the hold-out cases P04, P10, P18. **Met by the negotiator v1.2 (Sat 21:10): 67.5 against 61.5, P04, P10, P18 above the baseline; needs the team's yes.**
- How do the final score and the jury score combine for places 1-3? Ask at the Tacto desk.
- When does Tacto go offline on Saturday night?
