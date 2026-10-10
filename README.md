# taco-sellm - Tacto Negotiation Arena

Our buyer agent for the Tacto Negotiation Arena (EHL Grand Finale 2026). Built on the official
starter kit (`arena_kit/`, MIT); the original kit README is in [KIT-README.md](KIT-README.md),
the brief and API docs are in [brief/](brief/).

## Run

Needs Python 3.12 and [uv](https://docs.astral.sh/uv/).

```bash
cp .env.example .env     # set ARENA_URL, ARENA_API_KEY, ARENA_DATA=data/package; for an LLM agent also
                         # LLM_PROVIDER=openai, LLM_MODEL, LLM_API_KEY (values never in git)
uv sync --all-extras
uv run arena data        # unpacks data/package (and data/release-sunday from Sun 08:00; gitignored)
uv run arena me          # team + practice quota
scripts/preflight        # everything the final needs, plus one free sandbox case through the runner
```

The Live Final runs through our runner, `sellm/runner.py` (start it before 12:00; it polls until wave 1
opens, plays every case of a wave in parallel, closes each case before the wave's cap and stops after
wave 5; run the same command again after a crash and it resumes the running sessions):

```bash
nohup uv run python -m sellm.runner --set final --agent sellm > runs/logs/final.out 2>&1 &
```

Measured runs use the same runner: `uv run python -m sellm.runner --set sandbox --cases D01 D02
--repeat 3` (free) or `--set practice --cases P01 P05` (quota). Logs: `runs/logs/<time>-runner-<set>.log`
(every move) and `.jsonl` (one row per case). `uv run arena play case:D01 --agent sellm -v` plays one case
with the kit's runner.

Agents (`--agent`): `sellm` is ours (`sellm/agent.py` -> `sellm/negotiator.py`: the price path and the
term sheets from code, data arguments from `sellm/claims.py`, supplier dossiers from `sellm/intel/`);
`naive` and `llm` are the kit's examples (`llm` scored 61.5 on the 10 hosted cases). Which one the
final runs is decided in `docs/STATUS.md`.

## Working on this repo (humans and agents)

Several people and AI agents work here in parallel. Read [AGENTS.md](AGENTS.md) first: it is the
working protocol (sync, claim, log, commit, push). The team's memory lives in `docs/`:

| File | What |
|---|---|
| [docs/CONTEXT.md](docs/CONTEXT.md) | the challenge condensed: rules, scoring, API, data, kit |
| [docs/STATUS.md](docs/STATUS.md) | where we are now, who works on what, what is next |
| [docs/LEARNINGS.md](docs/LEARNINGS.md) | what works in negotiations, with evidence |
| [docs/LOG.md](docs/LOG.md) | history, appended with `scripts/log` |

```bash
scripts/sync                                   # pull --rebase + push
scripts/pull-first                             # get the team's latest code; arena play/run call it themselves
scripts/log "[finding] title" "detail" ...     # add a log entry, then commit it with the change
scripts/session-start                          # print the team's live state
```

## Final submission

- Commit hash run in the final: _TODO_
- Approach: _TODO_
