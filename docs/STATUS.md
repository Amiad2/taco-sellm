# STATUS - where we are right now

Keep this file short and true. Edit it in place; history belongs in `docs/LOG.md`.
Last updated: 2026-10-10 14:50 CEST by Jonathan (Claude Code).

## Now

- Repo is set up on the official starter kit; tests pass (31 passed, 1 skipped).
- Team key works: team **sellm**, active. `uv run arena me` is the source of truth for quota and best scores.
- Only the kit's naive agent has played so far. No agent of our own exists yet.
- Team memory is in place: `AGENTS.md`, `docs/CONTEXT.md`, this file, `docs/LEARNINGS.md`, `docs/LOG.md`.

## In progress (claim before you start, remove when done)

| Who | What | Files | Since |
|---|---|---|---|
| - | - | - | - |

## Next up (in this order unless a human says otherwise)

1. Baseline: run the kit's LLM agent on sandbox `D01` and `D02` (free), read the replays, write the findings to `docs/LEARNINGS.md`.
2. Verify the RFQ clock: does a sequential `play()` cause timeouts on the other threads? Test in `D02`.
3. Supplier dossiers: per supplier, mine notes, letters, news, scorecards, price history, should-cost and cost drivers into a cached brief the agent gets before round 1.
4. Strategy in code: enumerate term sheets over `term_options`, price each with `total_cost`, estimate the supplier's margin for `stabilise` and `secure_supply` cases, let the LLM only choose arguments and wording.
5. Our own agent and runner, wired into `uv run arena play/run`.
6. Baseline all 10 hosted cases once (10 sessions) to learn every `C_open` and `C_best`; score offline from then on.
7. Final rehearsal: all hosted cases in parallel from the final machine, well inside 8 minutes.
8. Submission: README run instructions, approach description, commit hash, slides.

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
- Where does our own agent code live: inside `arena_kit/agents/` or in a separate package next to the kit?
- How do the final score and the jury score combine for places 1-3? Ask at the Tacto desk.
- When does Tacto go offline on Saturday night?
