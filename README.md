# taco-sellm - Tacto Negotiation Arena

Our buyer agent for the Tacto Negotiation Arena (EHL Grand Finale 2026). Built on the official
starter kit (`arena_kit/`, MIT); the original kit README is in [KIT-README.md](KIT-README.md),
the brief and API docs are in [brief/](brief/).

## Run

Needs Python 3.12 and [uv](https://docs.astral.sh/uv/).

```bash
cp .env.example .env     # set ARENA_API_KEY and your LLM key (ANTHROPIC_API_KEY)
uv sync --all-extras
uv run arena data        # unpacks data/package (gitignored)
uv run arena me          # team + practice quota
uv run arena play case:P01 --agent llm -v
uv run arena run --set final --agent llm --parallel 10   # Live Final, start before 12:00
```

## Final submission

- Commit hash run in the final: _TODO_
- Approach: _TODO_
