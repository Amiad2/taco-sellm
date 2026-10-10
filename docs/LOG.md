# LOG - what happened, when, by whom

Append-only, newest at the bottom. Write entries with `scripts/log "[type] title" "detail" ...`
and commit them with the change they describe. Types: `[change]`, `[run]`, `[finding]`,
`[decision]`, `[blocker]`, `[handoff]`. Rules: `AGENTS.md`, section 3.

## 2026-10-10 14:43 CEST · Jonathan @ MacBook-Pro-von-Jonathan
**[change] Repo set up on the official starter kit**
- Sat 14:02: copied starter-kit/ from github.com/tacto-ai/negotiation-arena-kit into the repo root, plus brief/ and LICENSE; first commit 44ee219.
- The kit's own README is KIT-README.md. data/ and .env are gitignored: run 'uv run arena data' and fill .env on every machine.
- uv sync --all-extras and uv run pytest pass (31 passed, 1 skipped).

## 2026-10-10 14:43 CEST · Jonathan @ MacBook-Pro-von-Jonathan
**[run] P01 with the kit's naive agent: 0.583**
- Sat 14:13, session a4159c31bf9b86d8, replay https://arena.tacto.ai/replay/a4159c31bf9b86d8
- Deal with sup:70110 at 135.40, 60 days, effective 2026-11-01. c_open 1,153,780, c_deal 1,120,579, c_best 1,096,816.
- Four price-only rounds (137.30, 136.50, 135.90, 135.40). effective_date was never negotiated.
- Quota left 199.

## 2026-10-10 14:43 CEST · Jonathan @ MacBook-Pro-von-Jonathan
**[finding] The practice quota does not refill before the final**
- It is 200 sessions per rolling 24 h. 'uv run arena me' shows resets_at 2026-10-11 14:13 CEST, after the Live Final (Sun 12:00).
- So what is left now is the team's total budget until the final. Rules for spending it: AGENTS.md, section 5.

## 2026-10-10 14:43 CEST · Jonathan @ MacBook-Pro-von-Jonathan
**[finding] On P01 the effective date and payment days are worth more than the price steps**
- Computed offline with arena_kit.total_cost: 134.50 at 30 days costs 1,109,624 from January and 1,093,501 from April.
- Each 30 days of payment term is worth about 7,500. Table in docs/LEARNINGS.md.
- The kit's naive and LLM agents also leave out the relationship term of stabilise and secure_supply cases (no supplier estimate passed to total_cost).

## 2026-10-10 14:43 CEST · Jonathan @ MacBook-Pro-von-Jonathan
**[change] Team memory and working rules for all agents**
- AGENTS.md (rules, imported by CLAUDE.md), docs/CONTEXT.md (brief, API, FAQ, data and kit condensed), docs/STATUS.md, docs/LEARNINGS.md, docs/LOG.md.
- scripts/sync (pull --rebase + push), scripts/log (this log), scripts/session-start and scripts/stop-check (Claude Code hooks in .claude/settings.json).
- docs/LOG.md merges with merge=union (.gitattributes), so parallel entries from two machines do not conflict.
- Next: see 'Next up' in docs/STATUS.md.

## 2026-10-10 14:49 CEST · Jonathan @ MacBook-Pro-von-Jonathan
**[run] Sandbox D01 with the kit's naive agent: 0.200, quota unchanged**
- Sat 14:49, session b395491ef29942ff, replay https://arena.tacto.ai/replay/b395491ef29942ff
- Deal with sup:DEMO-F1 at 50.90, 30 days, 12 months, effective 2026-12-01. c_open 448,811, c_deal 440,757, c_best 408,624.
- Verified: 'uv run arena me' shows used 1 / left 199 before and after, so the sandbox does not touch the practice quota.
- The naive agent left contract_months at 12 although the horizon is 2 years, so half the need is uncovered at the fallback price.
