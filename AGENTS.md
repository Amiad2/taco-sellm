# AGENTS.md - how every agent works in this repo

You are one of several AI agents (and humans) working on this repo at the same time, from different
machines, with no shared memory except this repo. **The repo is the team's memory.** Anything you
learn, decide or change that is not committed, logged and pushed does not exist for the others.
These rules apply to every session, whether or not the prompt mentions them.

The project: team **sellm**'s buyer agent for the Tacto Negotiation Arena. **Code freeze and Live
Final: Sunday 11 Oct 2026, 12:00 CEST.** Everything about the challenge is in `docs/CONTEXT.md`.

## 1. Start of every session, before anything else

1. `scripts/sync` - get the team's latest state (pull --rebase, push). Do it again whenever you
   come back to the work after a pause.
2. Read `docs/STATUS.md` - where we are, who is working on what, what is next - and `docs/PLAN.md`
   for the workstream your task belongs to.
3. Read the newest entries of `docs/LOG.md` - `scripts/session-start` prints both.
4. Read `docs/CONTEXT.md` if it is not already in your context, and `docs/LEARNINGS.md` and
   `runs/BASELINE.md` and `experiments/RESULTS.md` before you touch negotiation behaviour. Before you play a case, read its
   earlier sessions in `runs/` instead of replaying it.
5. If the task you were given overlaps something under "In progress" in `docs/STATUS.md`, say so to
   your human before you start.

In Claude Code a SessionStart hook runs `scripts/session-start` for you and `CLAUDE.md` loads this
file and `docs/CONTEXT.md`. In any other tool, do the steps by hand.

## 2. The work loop

1. **Claim** - add a line under "In progress" in `docs/STATUS.md` (who, what, which files), commit
   and `scripts/sync`. Now the others know.
2. **Change** - small steps. Keep `uv run pytest` and `uv run ruff check .` green.
3. **Log** - `scripts/log "[type] title" "detail" ...` (section 3).
4. **Commit** - code and its log entry in the same commit, with a message that says what and why.
5. **Push** - `scripts/sync`. It rebases on the team's work and pushes.
6. When the task is done, remove your claim from `docs/STATUS.md`, update the rest of that file and
   put durable findings into `docs/LEARNINGS.md`.

**Commit and push after every working step, at least every 30 minutes of work, and always before
you stop or hand back to your human.** Unpushed work is the main way two agents end up building the
same thing or breaking each other. The one exception: do not push a state that breaks the tests or
the runner on `main`; finish the step or stash it, and say so.

### Pull before every run

**Before every run against the arena - one case, a full run, a probe, the final rehearsal - the
checkout must contain everything the team has pushed.** Otherwise the run measures an outdated
agent, the score is credited to the wrong code, and quota is spent on something a teammate already
fixed. This holds every time, not only at the start of a session: teammates push while you work.

It is built in, so it cannot be forgotten:

- `uv run arena play ...` and `uv run arena run ...` call `scripts/pull-first` before they open a
  session. If teammates pushed, it pulls (rebase, autostash) and **starts the command again on the
  new code**. If the pull hits a conflict, the run does not start: resolve it, then start again.
- `scripts/pull-runs` and `experiments/sandbox_probes.py` do the same.
- **Any new script or runner that opens arena sessions must call
  `arena_kit.cli.pull_first()` first**, or `scripts/pull-first` from a shell.
- On a branch it pulls that branch only (`origin/<branch>`); `main` reaches your branch through
  `git merge main` (section 4).
- Read its one-line report: it names the commit the run uses and how many of your own commits and
  files are not pushed. A run on unpushed code cannot be reproduced by anyone else, so push first
  when the result matters.
- Exceptions, both deliberate: `arena-sim` on localhost never pulls. `arena run --set final` only
  reports and never pulls, because the final must run the frozen commit; pull by hand before
  starting it. `ARENA_NO_PULL=1` switches the check off.
- If origin cannot be reached it warns and runs the local code. Then say so in the `[run]` entry.

### Every result names its commit

So that a better earlier version can always be found and restored, **every result says which commit
produced it**: each `[run]` entry, each scoreboard line in `docs/STATUS.md`, each results table in
`experiments/` and each lab report carries the short hash and the branch, e.g. `omars_branch@680799f`
(`git branch --show-current`, `git rev-parse --short HEAD`; `scripts/pull-first` prints the commit
before every run).

- The commit must be pushed and the working tree clean when the run starts; commit and push first.
  A hash that exists only on one laptop cannot be restored by anyone.
- Label the sessions with it: `scripts/pull-runs --label "<agent and model> <branch>@<hash>"`.
- To go back: find the hash of the better result in `docs/LOG.md` or `runs/README.md`, look at or
  test it with `git switch -c restore-<hash> <hash>`, and bring it back onto your branch with
  `git revert` of the later commits or by merging the restore branch. Never `git reset --hard` over
  pushed work.
- Mark a version worth keeping with a tag:
  `git tag -a best-<branch>-<score> <hash> -m "<run and result>" && git push origin best-<branch>-<score>`.

## 3. The log (`docs/LOG.md`)

Append-only, newest at the bottom, written with `scripts/log`, never edited by hand except to fix
a wrong fact (then log the correction too).

```bash
scripts/log "[run] P01 with llm agent: 0.71" \
  "commit omars_branch@680799f (pushed, clean tree)" \
  "replay https://arena.tacto.ai/replay/<sid>" \
  "moved effective_date to April; supplier accepted after cost-breakdown question" \
  "quota left 187"
```

Write an entry whenever one of these happens. Start the title with its type:

| Type | When |
|---|---|
| `[change]` | you changed how the agent, runner or tooling behaves |
| `[run]` | you played practice or sandbox sessions: cases, agent version, **the commit as `<branch>@<hash>`**, scores, replay links, quota left. **Then run `scripts/pull-runs --label "<agent and model> <branch>@<hash>"` and commit `runs/`**, so everyone has the full sessions |
| `[finding]` | you learned something about a supplier, the API, the scoring or the data |
| `[decision]` | a choice was made that others must follow, and why |
| `[blocker]` | something is broken or blocked, and what you tried |
| `[handoff]` | you stop with work unfinished: the state, what is next, where the traps are |

Write for a teammate who was not there: what, why, the result, and what follows from it. Include
numbers, case IDs, replay links and file names. Do not log typos or formatting.

Each file has one job. Do not mix them:

| File | Holds | Changes |
|---|---|---|
| `docs/CONTEXT.md` | facts about the challenge: rules, scoring, API, data, kit | rarely; when the brief, FAQ or data changes |
| `docs/STATUS.md` | the present: state, claims, next steps, scoreboard, decisions | constantly; keep it short and true |
| `docs/PLAN.md` | the plan: where the points are, the parts of the agent, workstreams, timeline, quota budget | when the team changes the plan |
| `docs/LEARNINGS.md` | what works and what fails in negotiations, with evidence | when a replay teaches something |
| `docs/LOG.md` | history: what happened when, by whom | append only |
| `runs/` | every session the team played, in full (`.md` readable, `.json` raw), the index `runs/README.md` and analyses such as `runs/BASELINE.md` | generated by `scripts/pull-runs`; analyses by hand |

## 4. Git

- **Each team member builds an independent version of the agent on an own branch** (decided Sun
  01:20; Omar: `omars_branch`), listed in `docs/STATUS.md` under Decisions. The team picks the best
  version by its measured results (`<branch>@<hash>`, section 2) and merges it into `main` **before
  our freeze at 11:00** (official freeze 12:00): the Live Final runs `main`.
- Your agent code and its experiments live on your branch. What the whole team reads stays on
  `main`: `AGENTS.md`, `docs/` (CONTEXT, STATUS, PLAN, LEARNINGS, LOG) and `runs/`. Change those on
  `main` (`git switch main`, `scripts/sync`, change, commit, `scripts/sync`, `git switch <your
  branch>`), and bring `main` into your branch regularly with `git merge main`.
- `scripts/sync` and `scripts/pull-first` work on the branch you are on: they pull and push
  `origin/<that branch>`, not `main`. Push a new branch once with `git push -u origin <branch>`.
- Small commits. `scripts/sync` before you start and after every commit.
- Never force-push, never rewrite pushed history, never `git reset --hard` over work you did not write.
- On a rebase conflict: keep both sides' intent, run the tests, continue. `docs/LOG.md` merges by
  itself (`merge=union` in `.gitattributes`); if entries end up interleaved, leave them.
- Never commit `.env`, keys, `data/` or `.venv/`. Check `git status` before `git add`.

## 5. Things the whole team shares

- **Practice quota: about 200 sessions in total until the final, for all of us together.** It is
  "per rolling 24 hours", and sessions used on Saturday afternoon free up only after the final.
  Before any practice run: `uv run arena me`. Play single cases, not the whole set, unless a full
  rehearsal is planned in `docs/STATUS.md`. Log every `[run]` with the quota left. Keep at least 40
  sessions for Sunday (pre-flight and one full rehearsal).
- **Free first** (details and a table in `docs/CONTEXT.md`, section 9): score term sheets offline
  with `arena_kit.total_cost`; test plumbing on `arena-sim`; **test agent behaviour against real
  supplier bots in the sandbox (`case:D01`, `case:D02`) - it does not use the practice quota**
  (verified). `arena-sim`'s supplier is a script and says nothing about strategy.
- **Silent LLM fallback**: if the LLM call fails, the kit agent plays the naive move without
  error. Run LLM agents with `-v` and check for `LLM failed` before trusting a score.
- **One API key, 10 open sessions, 10 calls per second, for all of us.** Two parallel runs from two
  machines can starve each other: check `docs/STATUS.md` before a parallel run.
- **LLM spend** is each developer's own key. Do not loop expensive models over the full case set.
- **Only one machine runs the Live Final.** Which one is in `docs/STATUS.md`.

## 6. Rules of the competition that code must never break

- The agent **must not call** `/v1/events`, `/v1/events/stream`, `/screen`, `/v1/screen`,
  `/leaderboard`, `/v1/leaderboard`, `/results` or `/v1/results`. Reading the live feed during the
  final is forbidden. Humans may look at them; the agent's code path may not.
- No human in the loop during the Live Final: nothing in the final runner may wait for input.
- No second API key, no attacks on the service or other teams.
- No commits after the freeze (Sun 12:00). The submitted commit hash is what runs.

## 7. Where things are

| Path | What |
|---|---|
| `docs/` | the team's memory (section 3) |
| `brief/` | the official brief, API docs and submission guide. Source of truth |
| `arena_kit/` | the official starter kit (client, runner, cost function, example agents, simulator). Upstream: github.com/tacto-ai/negotiation-arena-kit |
| `tests/` | the kit's contract tests against `arena-sim` |
| `data/package/` | the data package. Not in git: `uv run arena data` |
| `scripts/` | `sync`, `log`, `pull-first`, `pull-runs`, `session-start`, `stop-check`, `lab` (the lab from a shell, background runs) |
| `runs/` | all sessions played, with transcripts, supplier reasons, cost breakdowns and offline analysis |
| `sellm/` | our code: `agent.py` (what `--agent sellm` plays), `lab/` (local supplier simulator, tournament, stress test; guide `sellm/lab/README.md`) |
| `experiments/` | probe scripts and their results: `RESULTS.md` says how the suppliers react and which rules follow |
| `KIT-README.md` | the kit's own README with worked examples |

New machine: `uv sync --all-extras`, `cp .env.example .env`, put in the team's `ARENA_API_KEY`
(from a teammate, never through git) and your own LLM key, `uv run arena data`, `uv run arena me`.
No `uv` yet: `curl -LsSf https://astral.sh/uv/install.sh | sh` (installs to `~/.local/bin`; on
Ubuntu/Debian `pip install uv` is refused by the system Python, PEP 668). This matters for the
final machine too.

**Entire** (session checkpoints, installed Sat 14:55, CLI 0.11.4) is enabled in this repo for Claude
Code: `.entire/settings.json` and its hooks in `.claude/settings.json` are committed, but its git
hooks live in each clone's `.git/hooks`. On every machine run once, after pulling:
`curl -fsSL https://entire.io/install.sh | bash` (adds `~/.local/bin`, put it on your `PATH`), then
`entire enable --agent claude-code --skip-push-sessions --telemetry=false`. Without it the Claude
Code hooks stay silent except for one "Entire CLI is not installed" notice at session start; nothing breaks.
**Session logs are not pushed** (`push_sessions: false`): transcripts can contain keys and internal
prompts, and this repo goes to the jury. Do not turn that on without the team deciding it in
`docs/STATUS.md`. `docs/LOG.md` stays the shared memory; checkpoints are the per-session detail.

## 8. Before you stop

- `git status` is clean and `scripts/sync` succeeded, or you told your human exactly what is not
  pushed and why.
- Your claim in `docs/STATUS.md` is removed or updated; "Next up" is true.
- Unfinished work has a `[handoff]` entry.
- Report to your human in plain words what changed, what was verified and what is still open.
