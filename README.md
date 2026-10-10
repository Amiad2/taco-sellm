# taco-sellm - Tacto Negotiation Arena

Our buyer agent for the Tacto Negotiation Arena (EHL Grand Finale 2026). Built on the official
starter kit (`arena_kit/`, MIT); the original kit README is in [KIT-README.md](KIT-README.md),
the brief and API docs are in [brief/](brief/).

## Run

Needs Python 3.12 and [uv](https://docs.astral.sh/uv/).

```bash
cp .env.example .env     # set ARENA_API_KEY and the LLM: LLM_PROVIDER=openai, LLM_MODEL=gpt-6-sol, LLM_API_KEY
uv sync --all-extras
uv run arena data        # unpacks data/package (gitignored)
uv run arena me          # team + practice quota
uv run arena play case:D01 --agent sellm -v               # sandbox: free, real supplier bots
uv run arena play case:P01 --agent llm -v
uv run arena run --set final --agent llm --parallel 10   # Live Final, start before 12:00
```

Agents: `naive` and `llm` are the kit's examples; `llm` is the baseline to beat (61.5 on the 10
hosted cases). `sellm` is ours: `sellm/agent.py`, for now the lab's numbers-only Calculator. The
final command switches to `--agent sellm` only once it beats `llm`.

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
