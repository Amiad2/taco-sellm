# STATUS - where we are right now

Keep this file short and true. Edit it in place; history belongs in `docs/LOG.md`.
Last updated: 2026-10-10 17:30 CEST by Omar (Claude Code).

## Now

- Repo is set up on the official starter kit; tests pass (31 passed, 1 skipped).
- Team key works: team **sellm**, active. `uv run arena me` is the source of truth for quota and best scores.
- **OpenAI works with the kit's LLM agent** (`LLM_PROVIDER=openai`, model `gpt-6.1-sol`, Sat 15:00): D01 scored 0.786 against 0.200 for the naive agent, no `LLM failed` in the log. Each machine needs the values in its own `.env`; `llm_from_env` was not changed.
- The kit's LLM agent is the baseline to beat: **61.5** over the 10 hosted cases (`runs/BASELINE.md`).
- **Our agent is registered** (Sat 17:30): `uv run arena play|run ... --agent sellm` plays `sellm/agent.py`, the single entry point for whoever builds the negotiator. For now it is the lab's numbers-only Calculator with the best knobs of the first lab search: on the 10 practice twins it scores 59.8 in the lab, the same as the kit LLM agent there (59.8). **Not shown to beat `--agent llm`**, never played on the arena. `sellm` is in the wheel, so a non-editable install (VM, container) runs it too.
- Every session the team plays is saved in full under `runs/` by `scripts/pull-runs`. Quota left: 189.
- Sandbox probes (33 free sessions) show how suppliers react: only the first sheet can be accepted, a final offer is final, the supplier mirrors the size of our concessions, RFQ threads need their own loops. Rules for the agent: `experiments/RESULTS.md` section 5.
- **Lab** (`sellm/lab/`, Sat 16:50): twins of the 15 suppliers of our 12 played cases, each calibrated to its case's `C_best`; the kit's `play()` and any agent run against them locally, free and in milliseconds (`uv run python -m sellm.lab play P01`). Backtest against all 233 real supplier replies: mean error 0.95 % of the opening value, status right in 210/233; weak on P05 and P10 (`runs/lab/BACKTEST.md`). Tournament runner is next.
- Team memory is in place: `AGENTS.md`, `docs/CONTEXT.md`, this file, `docs/LEARNINGS.md`, `docs/LOG.md`.

## In progress (claim before you start, remove when done)

| Who | What | Files | Since |
|---|---|---|---|
| Amiad (Claude Code) | **Lab**: a local supplier simulator (twins of the 11 suppliers we have played, calibrated to each case's `C_best`, plus invented suppliers) and a tournament runner to test buyer strategies without quota. Backtested against our real sessions before anyone trusts it. No arena calls | `sellm/lab/`, `tests/test_lab.py`, `runs/lab/` | Sat 16:00 |
## Next up

The plan is in `docs/PLAN.md`: three workstreams (A numbers and strategy, B data and arguments,
C arena, measurement and final), a timeline and the quota budget. It is **proposed, not yet agreed**.

1. Team: read `docs/PLAN.md`, agree or change it, and each claim a workstream in the table above.
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

## Open questions (need a human)

- Which machine runs the Live Final, and is it a cloud VM or a laptop?
- Which LLM and whose key for the final; is there budget for an hour of parallel play?
- Who takes workstream A, B and C?
- How do the final score and the jury score combine for places 1-3? Ask at the Tacto desk.
- When does Tacto go offline on Saturday night?
