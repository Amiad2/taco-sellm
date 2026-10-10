# STATUS - where we are right now

Keep this file short and true. Edit it in place; history belongs in `docs/LOG.md`.
Last updated: 2026-10-10 20:50 CEST by Amiad (Claude Code).

## Now

- Repo is set up on the official starter kit; tests pass (31 passed, 1 skipped).
- Team key works: team **sellm**, active. `uv run arena me` is the source of truth for quota and best scores.
- **OpenAI works with the kit's LLM agent** (`LLM_PROVIDER=openai`, model `gpt-6.1-sol`, Sat 15:00): D01 scored 0.786 against 0.200 for the naive agent, no `LLM failed` in the log. Each machine needs the values in its own `.env`; `llm_from_env` was not changed.
- The kit's LLM agent is the baseline to beat: **61.5** over the 10 hosted cases (`runs/BASELINE.md`).
- **`--agent sellm` plays the negotiator** (`sellm/negotiator.py`, group A, Sat 20:35; no LLM yet, e-mails from a template): every move is a pure function of case and threads, the first ask takes coverage and the non-cash levers, each step is sized from the thread (gap, rounds left, the share of our steps the supplier gives back), it accepts a final offer and walks away only when the alternative is better. **Real sandbox: D01 0.920 (n=4; kit LLM 0.786, lab-best Calculator 0.789), D02 0.530 (n=4; kit LLM 0.47).** Lab (Amiad's recalibrated suppliers, 204 stress scenarios x 2): 52.8 against 45.8 for the Calculator knobs; 0 crashes, 0 broken must-haves, 0 refused moves with one loop per thread. **Not yet played on a practice case.** The old Calculator knobs stay in `sellm/agent.py` as `CALC_KNOBS`. Evidence: `experiments/RESULTS.md` section 7.
- Every session the team plays is saved in full under `runs/` by `scripts/pull-runs`. **Quota (checked Sat 20:40): limit 450, used 21, left 429; a session frees up 24 h after it was played** - the limit was raised from 200.
- Sandbox probes (33 free sessions) show how suppliers react: only the first sheet can be accepted, a final offer is final, the supplier mirrors the size of our concessions, RFQ threads need their own loops. Rules for the agent: `experiments/RESULTS.md` section 5.
- **Lab** (`sellm/lab/`, Sat 17:45; guide `sellm/lab/README.md`): test any agent locally, free, no quota. `scripts/lab play P01`, `scripts/lab compare naive calc`, `scripts/lab search 60` (background), `scripts/lab stress calc`, `scripts/lab status`. Scenarios: twins of our 15 played suppliers (families of plausible variants), the 9 unplayed practice case files with their real suppliers, and invented ones (all 7 types, all fields, 8 supplier archetypes, 12 edge cases). Simulated clock: 20-60 s replies, 60-s timeouts with re-issued offer IDs, 8-min wave cap; `--mode parallel` (one loop per thread) or `sequential` (the kit's `play()`). Backtest: 0.79 % mean error on 237 real replies; kit LLM agent 59.8 in the lab vs 61.5 in the arena (`runs/lab/BACKTEST.md`, `VALIDATION.md`). **Found: the kit's sequential `play()` times RFQ threads out and can crash on a stale offer ID; the final runner needs one loop per thread.**
- **Dossiers (group B, Sat 18:40)**: `sellm.intel.dossier(supplier_id, parts, case=, opening=, package=)` serves the 46 built dossiers (`sellm/dossiers/`, committed) plus the case overlay; strangers get a dossier from the case alone. `uv run python -m sellm.intel show 70130` prints one; `uv run python -m sellm.intel verify` runs checks V1-V10 (all PASS). Schema and rules: `docs/PLAN.md` section 10.
- Team memory is in place: `AGENTS.md`, `docs/CONTEXT.md`, this file, `docs/LEARNINGS.md`, `docs/LOG.md`.

## In progress (claim before you start, remove when done)

| Who | What | Files | Since |
|---|---|---|---|
| Amiad (Claude Code) | **Group C - Runner, arguments, measurement, final** (`docs/PLAN.md` section 3): `sellm/runner.py` first (one loop per thread, waves, closing before the cap, resume, per-move deadline, log file), then a full practice run through it (up to ~25 practice sessions tonight), `sellm/claims.py`, pre-flight and rehearsal on Jonathan's machine, submission. Also keeps the lab. The clone loop is paused | `sellm/runner.py`, `tests/test_runner.py`, `sellm/claims.py`, `tests/test_claims.py`, `scripts/preflight`, `sellm/lab/`, `scripts/lab`, `runs/lab/`, README run section | Sat 20:50 |
| Omar (Claude Code) | **Group B - Data**: built and verified (S0-S12). Open: the human check of the signals against blind labels (V11), the Sunday 08:00 rebuild. No arena calls | `sellm/intel/` (package), `sellm/dossiers/`, `tests/test_intel.py` | Sat 17:48 |
| Jonathan (Claude Code) | **Group A - Negotiation**: negotiator v1.1 is in (`[change]` Sat 20:35). Next: confirm on practice P07, P01, P02 (up to 10 sessions, each logged), then LLM wording as an opt-in experiment, reading the supplier's standard sentences. Plays the free sandbox itself | `sellm/negotiator.py`, `sellm/writer.py`, `sellm/llm.py`, `sellm/agent.py`, `tests/test_negotiator.py`, `experiments/ab_sandbox.py` | Sat 18:16 |

## Next up

**Jonathan: read the [handoff] of Sat 20:30 in docs/LOG.md** - the lab's supplier model changed at 20:03 (lowball
penalty), so earlier lab numbers are superseded; a comparison of the negotiator, the Calculator and Amiad's clone is
waiting for you to run.

**Group C: Amiad (Sat 20:50); the final needs its runner (C's priority 1, in progress).** With the kit's sequential `play()` the negotiator has a refused accept in 6 of 408 lab negotiations (RFQ: a timeout replaced the offer ID; the kit would crash there). With one loop per thread: none. `experiments/ab_sandbox.py:play_case` is such a loop (re-reads the thread before an accept, survives 409/422, one timeout in 20 real RFQ threads) and can become `sellm/runner.py`; it still lacks the wave handling and the closing before the cap of `arena_kit.play.play_waves`.

From the lab (Amiad): **the final runner needs one loop per thread** - the kit's `play()` times RFQ
threads out in the lab as in the sandbox, and a stale offer ID after a timeout is a 422 that crashes
it. Before any arena run of `--agent sellm`: `scripts/lab stress sellm.agent:make_agent` must PASS.
Then confirm the lab's best knobs in the free sandbox (D01, D02) before spending practice quota.

**Decided Sat 17:41** (`docs/PLAN.md`): three groups with their tasks, priorities and the skills
they need (**section 3**: A negotiation, B data, C runner, arguments, measurement and final; C took
over the per-move deadline from A and the argument bank and research from B at 17:45),
and the **dossier and mini-dossier schema** (**section 10**: fields, frozen core fields, rules,
signal vocabulary). Build against section 10; add fields freely, rename core fields only by decision.

1. Each person claims one group in the table above. Group C is still open.
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

**Full practice run with `--agent sellm` (negotiator v1.1, no LLM, kit runner), Sat 20:35: mean 53.2 - below the baseline's 61.5.** Better on P01, P02, P05, P10, P18; lost on P04 (0.000 against 0.810) and P08 (0.152 against 0.433), where the baseline asked for the running contract's 60 days and a 24/36-month term and the negotiator kept the quoted 30 days and 12 months. `--agent llm` stays the agent to beat. Details: `docs/LOG.md` Sat 20:45.

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
- Which agent plays the final? Proposed: `sellm` replaces `llm` only if its mean is higher in lab, sandbox and one full practice run including the hold-out cases P04, P10, P18.
- How do the final score and the jury score combine for places 1-3? Ask at the Tacto desk.
- When does Tacto go offline on Saturday night?
