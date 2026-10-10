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

## 2026-10-10 14:51 CEST · Jonathan @ MacBook-Pro-von-Jonathan
**[finding] How to test without spending practice quota**
- Sandbox D01/D02 run against Tacto's real supplier bots and do not use the practice quota (verified: arena me unchanged after a D01 run).
- arena-sim is plumbing only: its supplier concedes a fixed 2 % per sheet and only checks that cited IDs exist.
- Offline total_cost scores any term sheet for free. Table of which option to use for what: docs/CONTEXT.md section 9, rule in AGENTS.md section 5.
- Trap: the kit's LLMAgent silently plays the naive move when the LLM call fails (wrong model name, bad key, 45 s timeout). Run with -v and look for 'LLM failed'.

## 2026-10-10 14:51 CEST · Jonathan @ MacBook-Pro-von-Jonathan
**[decision] Team LLM provider is OpenAI**
- Jonathan is wiring LLM_PROVIDER=openai (LLM_MODEL, LLM_API_KEY in .env). Claim is in docs/STATUS.md. Do not edit arena_kit/agents/llm.py until it is released there.

## 2026-10-10 14:56 CEST · Jonathan @ MacBook-Pro-von-Jonathan
**[change] Entire enabled for Claude Code (local checkpoints, no session push)**
- Installed Entire CLI 0.11.4 (checksum verified) and ran: entire enable --agent claude-code --skip-push-sessions --telemetry=false.
- Committed: .entire/settings.json, .entire/.gitignore, Entire's hooks merged into .claude/settings.json next to our session-start and stop-check (both kept).
- Not shared by git: Entire's git hooks in .git/hooks. Every teammate must install the CLI and run 'entire enable' once (AGENTS.md section 7).
- push_sessions=false on purpose: transcripts may contain keys and this repo is read by the jury. Changing it is a team decision.

## 2026-10-10 15:02 CEST · Jonathan @ MacBook-Pro-von-Jonathan
**[run] Sandbox D01 with the kit's LLM agent on OpenAI: 0.786 (naive 0.200), quota unchanged**
- Sat 15:00, session bb64095ce8935924, replay https://arena.tacto.ai/replay/bb64095ce8935924, model gpt-6.1-sol, no 'LLM failed' in the -v log.
- Deal with sup:DEMO-F1 at 50.80, 30 days, 24 months, effective 2027-02-01. c_open 448,811, c_deal 417,205, c_best 408,624.
- Price steps 51.90 -> 51.10 -> 50.90 -> 50.80 over 4 rounds; supplier refused 60-day payment. No data IDs cited (claim_results empty).
- Round time 24-34 s including the supplier reply. Quota still 199 left (sandbox).

## 2026-10-10 15:02 CEST · Jonathan @ MacBook-Pro-von-Jonathan
**[change] OpenAI provider is working; claim in STATUS released**
- LLM_PROVIDER=openai, LLM_MODEL=gpt-6.1-sol, LLM_API_KEY in taco-sellm/.env (values were in the old negotiation-arena-kit/starter-kit/.env and were copied over; the old file can be deleted).
- arena_kit/agents/llm.py was not changed. Smoke test of llm_from_env returned in 2.1 s.

## 2026-10-10 15:13 CEST · Jonathan @ MacBook-Pro-von-Jonathan
**[change] Proposed team plan in docs/PLAN.md (not yet agreed)**
- Three workstreams: A numbers and strategy (calculator + negotiator), B data and arguments (dossiers for all 46 suppliers + checked argument bank), C arena, measurement and final (runner, runs/, rehearsal, submission).
- Timeline to Sun 12:00 and a budget for the 199 sessions (10 baseline, 30 full runs, 80 experiments, 25 Sunday, 54 reserve).
- Proposes a separate package sellm/ for our code. Owners are open: claim a workstream in docs/STATUS.md.

## 2026-10-10 15:13 CEST · Jonathan @ MacBook-Pro-von-Jonathan
**[finding] 24 of 46 detailed suppliers appear in no practice case; the back office is thin**
- The 19 practice cases use 22 detailed suppliers. The other 24 have about 4 documents each: likely the hidden cases' suppliers, so dossiers should cover all 46.
- negotiation_history has notes per supplier and part, e.g. Brandlhuber on part:310010: 'accepted below full cost to keep the volume'.
- GET /v1/sessions/{sid}/backoffice only shows who asked whom ('My call: counter.'). The supplier's reasons are in the session trace.

## 2026-10-10 15:22 CEST · Jonathan @ MacBook-Pro-von-Jonathan
**[decision] No vector RAG: dossier cache by ID, optimal values computed, prep before the session opens**
- Measured: all 208 documents are 46 KB, one supplier's documents at most ~500 tokens, lookup by supplier_id 0.1 ms. Embedding search would only add latency and wrong hits.
- Dossiers are built by one command and looked up by ID; rebuilt after the Sunday 08:00 release. Best term sheets are computed from the case file, never looked up from practice results.
- Timing: case files are readable before POST /v1/sessions, so all preparation happens before the 60 s clock starts. Per move: 15 s target, 40 s hard deadline, then the calculator's move without the LLM.
- Overfitting guards in docs/PLAN.md section 8: no practice IDs in code or prompts, every negotiable field supported (incoterm is never negotiable in practice), dry-runs on all 19 case files incl. P06 and P13, property tests, hold-out P04/P10/P18.

## 2026-10-10 15:35 CEST · Jonathan @ MacBook-Pro-von-Jonathan
**[run] Baseline: kit LLM agent on all 10 hosted cases, mean 61.5**
- Sat 15:27-15:31, 'uv run arena run --set practice --agent llm --parallel 10 -v', kit agent unchanged, OpenAI gpt-6.1-sol. 10 sessions, quota left 189. No LLM failure, no fallback.
- Scores: P01 0.789, P02 0.105, P03 0.903, P04 0.810, P05 0.676, P07 0.779, P08 0.433, P10 0.570, P11 0.710, P18 0.377. All ten closed a deal.
- Every session in full under runs/practice/<case>/ (.md readable, .json raw), index runs/README.md, run log runs/logs/2026-10-10-1527-baseline-kit-llm.log.
- Analysis with 9 findings and 7 hypotheses to test: runs/BASELINE.md. Rules distilled into docs/LEARNINGS.md.

## 2026-10-10 15:35 CEST · Jonathan @ MacBook-Pro-von-Jonathan
**[change] scripts/pull-runs saves every team session into runs/**
- It lists all practice and sandbox sessions of our key (whoever played them) and saves case file, all e-mails, attachment texts, the supplier's reasons, back office, result and cost breakdown.
- It adds an offline analysis per session: value of each lever at the deal, best non-price terms at the deal's price, the price that would reach C_best, and the split of the gap into structure and price.
- After every run: scripts/pull-runs --label "<agent and model>", then commit runs/ (AGENTS.md section 3). STATUS no longer keeps a scoreboard by hand; runs/README.md is generated.

## 2026-10-10 15:35 CEST · Jonathan @ MacBook-Pro-von-Jonathan
**[finding] Baseline: where the kit LLM agent loses points**
- It reads only the supplier's first term sheet: in P10 the ignored alternative (32.00, 54 days) scored 0.647 against the accepted 0.570. Alternatives came in 11 of 12 threads.
- It accepts as soon as the supplier stops moving, after 2-5 of 10 messages.
- P05 (RFQ) handled thread by thread: timeouts on two threads, the cheapest bidder withdrew.
- Claims: 8 verified, 8 duplicate (same ID cited again), none in P05, P07, P08. Suppliers asked for data in P03, P04, P05, P10.
- Where a plant-specific should-cost exists, the price at C_best is 0.98-1.16 times should-cost; in P10 we closed at 1.38 times.
- Open: in P08, P18 and P10 C_best lies 6-19 % below the current price and we do not know which fact unlocks it.

## 2026-10-10 15:52 CEST · Amiad @ fedora
**[decision] Build a local supplier simulator (lab) after all; PLAN.md section 9 reversed**
- Why: 189 practice sessions must last until the final, and screening strategy variants (levers, accept timing, moves after final_offer, several sheets, RFQ) needs hundreds of full negotiations. Sandbox has only 2 cases and 3 demo suppliers.
- Why it can work: the real suppliers' reasons in our traces are templated ('it holds, but it does not change our calculation', 'Without movement from your side we cannot move either'), i.e. an engine with hidden numbers plus LLM prose, which a model can approximate.
- What: sellm/lab/ - an in-process table with the RemoteTable interface (kit play() and every agent run unchanged, no clock, no HTTP), twins of the 11 suppliers we played calibrated so the best acceptable package costs exactly the case's C_best, invented suppliers on generated cases, a tournament runner, reports in runs/lab/.
- Guard: lab results are hypotheses. The lab is backtested against our 13 real sessions first; winners are confirmed in sandbox D01/D02, then on single practice cases. arena_kit/ stays untouched; the lab makes no arena calls.
- Owner: Amiad (Claude Code), claimed in docs/STATUS.md.
- Setup trap on this machine, worth checking on yours: arena_kit load_env takes the FIRST value of a duplicated key in .env. With the Anthropic block of .env.example left in, LLM_PROVIDER=anthropic wins and, with an empty ANTHROPIC_API_KEY, every LLM call fails silently into the naive move. Comment out the block you do not use.
