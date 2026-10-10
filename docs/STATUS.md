# STATUS - where we are right now

Keep this file short and true. Edit it in place; history belongs in `docs/LOG.md`.
Last updated: 2026-10-10 15:45 CEST by Jonathan (Claude Code).

## Now

- Repo is set up on the official starter kit; tests pass (31 passed, 1 skipped).
- Team key works: team **sellm**, active. `uv run arena me` is the source of truth for quota and best scores.
- **OpenAI works with the kit's LLM agent** (`LLM_PROVIDER=openai`, model `gpt-6.1-sol`, Sat 15:00): D01 scored 0.786 against 0.200 for the naive agent, no `LLM failed` in the log. Each machine needs the values in its own `.env`; `llm_from_env` was not changed.
- No agent of our own exists yet; the kit's LLM agent is the baseline to beat.
- Team memory is in place: `AGENTS.md`, `docs/CONTEXT.md`, this file, `docs/LEARNINGS.md`, `docs/LOG.md`.

## In progress (claim before you start, remove when done)

| Who | What | Files | Since |
|---|---|---|---|
| Jonathan (Claude Code) | Baseline: kit LLM agent (OpenAI `gpt-6.1-sol`) on all 10 hosted cases, 10 sessions; `scripts/pull-runs` and `runs/` with every session in full | `runs/`, `scripts/pull-runs` | Sat 15:45 |

## Next up

The plan is in `docs/PLAN.md`: three workstreams (A numbers and strategy, B data and arguments,
C arena, measurement and final), a timeline and the quota budget. It is **proposed, not yet agreed**.

1. Team: read `docs/PLAN.md`, agree or change it, and each claim a workstream in the table above.
2. Baseline (workstream C): kit LLM agent on all 10 hosted cases (10 sessions) and on sandbox `D02`. Needs a human's go because it spends quota.
3. Then follow the timeline in `docs/PLAN.md` section 4.

## Scoreboard (best per hosted practice case)

| Case | Best | Agent | C_open | C_best | Replay |
|---|---|---|---|---|---|
| P01 | 0.583 | kit naive | 1,153,780 | 1,096,816 | https://arena.tacto.ai/replay/a4159c31bf9b86d8 |
| P02 | - | | | | |
| P03 | - | | | | |
| P04 | - | | | | |
| P05 | - | | | | |
| P07 | - | | | | |
| P08 | - | | | | |
| P10 | - | | | | |
| P11 | - | | | | |
| P18 | - | | | | |

Practice board total (mean of the ten, unplayed = 0): 5.8.

## Decisions

- Work on `main`, small commits, `scripts/sync` after each one (`AGENTS.md`).
- Docs and logs are written in English: the jury and tum.ai read the repo.

## Open questions (need a human)

- Which machine runs the Live Final, and is it a cloud VM or a laptop?
- Which LLM and whose key for the final; is there budget for an hour of parallel play?
- Where does our own agent code live? `docs/PLAN.md` proposes a separate package `sellm/` next to the kit. Confirm or change.
- Who takes workstream A, B and C?
- How do the final score and the jury score combine for places 1-3? Ask at the Tacto desk.
- When does Tacto go offline on Saturday night?
