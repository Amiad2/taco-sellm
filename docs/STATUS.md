# STATUS - where we are right now

Keep this file short and true. Edit it in place; history belongs in `docs/LOG.md`.
Last updated: 2026-10-10 19:05 CEST by Omar (Claude Code).

## Now

- Repo is set up on the official starter kit; tests pass (31 passed, 1 skipped).
- Team key works: team **sellm**, active. `uv run arena me` is the source of truth for quota and best scores.
- **OpenAI works with the kit's LLM agent** (`LLM_PROVIDER=openai`, model `gpt-6.1-sol`, Sat 15:00): D01 scored 0.786 against 0.200 for the naive agent, no `LLM failed` in the log. Each machine needs the values in its own `.env`; `llm_from_env` was not changed.
- The kit's LLM agent is the baseline to beat: **61.5** over the 10 hosted cases (`runs/BASELINE.md`).
- **Our agent is registered** (Sat 17:30): `uv run arena play|run ... --agent sellm` plays `sellm/agent.py`, the single entry point for whoever builds the negotiator. For now it is the lab's numbers-only Calculator with the best knobs of the first lab search: on the 10 practice twins it scores 59.8 in the lab, the same as the kit LLM agent there (59.8). **Not shown to beat `--agent llm`**, never played on the arena. `sellm` is in the wheel, so a non-editable install (VM, container) runs it too.
- Every session the team plays is saved in full under `runs/` by `scripts/pull-runs`. Quota left: 189.
- Sandbox probes (33 free sessions) show how suppliers react: only the first sheet can be accepted, a final offer is final, the supplier mirrors the size of our concessions, RFQ threads need their own loops. Rules for the agent: `experiments/RESULTS.md` section 5.
- **Lab** (`sellm/lab/`, Sat 17:45; guide `sellm/lab/README.md`): test any agent locally, free, no quota. `scripts/lab play P01`, `scripts/lab compare naive calc`, `scripts/lab search 60` (background), `scripts/lab stress calc`, `scripts/lab status`. Scenarios: twins of our 15 played suppliers (families of plausible variants), the 9 unplayed practice case files with their real suppliers, and invented ones (all 7 types, all fields, 8 supplier archetypes, 12 edge cases). Simulated clock: 20-60 s replies, 60-s timeouts with re-issued offer IDs, 8-min wave cap; `--mode parallel` (one loop per thread) or `sequential` (the kit's `play()`). Backtest: 0.79 % mean error on 237 real replies; kit LLM agent 59.8 in the lab vs 61.5 in the arena (`runs/lab/BACKTEST.md`, `VALIDATION.md`). **Found: the kit's sequential `play()` times RFQ threads out and can crash on a stale offer ID; the final runner needs one loop per thread.**
- Team memory is in place: `AGENTS.md`, `docs/CONTEXT.md`, this file, `docs/LEARNINGS.md`, `docs/LOG.md`.

## In progress (claim before you start, remove when done)

| Who | What | Files | Since |
|---|---|---|---|
| Amiad (Claude Code) | **Lab** upkeep and strategy search: suppliers, scenarios, tournament, stress test, the `Calculator` strategy and its knobs. No arena calls | `sellm/lab/`, `scripts/lab`, `tests/test_lab.py`, `runs/lab/` | Sat 16:00 |
| Omar (Claude Code) | **Group B - Data** (`docs/PLAN.md` sections 3 and 10): stub `dossier()` first, then the dossier builder for all 46 detailed suppliers, signal rules and derived fields, the case overlay (mini-dossier), the Sunday rebuild. No arena calls | `sellm/intel.py`, `sellm/dossiers/`, `tests/test_intel.py` | Sat 19:00 |
## Next up

From the lab (Amiad): **the final runner needs one loop per thread** - the kit's `play()` times RFQ
threads out in the lab as in the sandbox, and a stale offer ID after a timeout is a 422 that crashes
it. Before any arena run of `--agent sellm`: `scripts/lab stress sellm.agent:make_agent` must PASS.
Then confirm the lab's best knobs in the free sandbox (D01, D02) before spending practice quota.

**Decided Sat 18:30** (`docs/PLAN.md`): three groups with their tasks, priorities and the skills
they need (**section 3**: A negotiation, B data, C runner, arguments, measurement and final; C took
over the per-move deadline from A and the argument bank and research from B at 18:50),
and the **dossier and mini-dossier schema** (**section 10**: fields, frozen core fields, rules,
signal vocabulary). Build against section 10; add fields freely, rename core fields only by decision.

1. Each person claims one group in the table above. B's first deliverable is a stub `dossier()`
   returning the schema, so A can code against it.
2. Baseline and the sandbox probes H1-H3 are done (`runs/BASELINE.md`, `experiments/RESULTS.md`). Next probes: H12-H15 in `experiments/RESULTS.md` section 6 (H12, H13, H15 are free), then H4-H7 on practice cases, one session each.
3. Then follow the timeline in `docs/PLAN.md` section 4.

## Scoreboard

Generated, do not keep by hand: `runs/README.md` (per case `C_open`, `C_best`, our best, every
session). Baseline of the kit's LLM agent on all 10 hosted cases, Sat 15:27: **mean 61.5**.
Weakest: P02 0.105, P18 0.377, P08 0.433, P10 0.570. Analysis and hypotheses: `runs/BASELINE.md`.

## Decisions

- Work on `main`, small commits, `scripts/sync` after each one (`AGENTS.md`).
- **Pull before every run.** `arena play`, `arena run`, `scripts/pull-runs` and the probe scripts call `scripts/pull-first` themselves and restart on the new code; new runners must call `arena_kit.cli.pull_first()` (`AGENTS.md` section 2).
- Docs and logs are written in English: the jury and tum.ai read the repo.
- Our code lives in `sellm/` (lab in `sellm/lab/`, the agent's entry point `sellm/agent.py`); `arena_kit/` stays the kit except for `pull_first` and the `--agent sellm` registration.
- **LLM: OpenAI `gpt-6-sol`** for development and the final (`LLM_PROVIDER=openai`, `LLM_MODEL=gpt-6-sol` in every `.env`; decided Sat 19:05, Omar). Earlier runs (D01 0.786, baseline 61.5) are logged as `gpt-6.1-sol`: whoever ran them, check which model your `.env` had and log it.

## Open questions (need a human)

- Which machine runs the Live Final, and is it a cloud VM or a laptop?
- Whose LLM key for the final, and is there budget for an hour of parallel play? (Model decided: `gpt-6-sol`.)
- Who takes group A and C (`docs/PLAN.md` section 3)? B: Omar.
- Which agent plays the final? Proposed: `sellm` replaces `llm` only if its mean is higher in lab, sandbox and one full practice run including the hold-out cases P04, P10, P18.
- How do the final score and the jury score combine for places 1-3? Ask at the Tacto desk.
- When does Tacto go offline on Saturday night?
