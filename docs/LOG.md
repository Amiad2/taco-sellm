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

## 2026-10-10 15:59 CEST · Jonathan @ MacBook-Pro-von-Jonathan
**[run] Sandbox probes H1-H3 plus follow-ups H8, H10, H11: 33 free sessions**
- Sat 15:42-15:57 on D01 and D02 with experiments/sandbox_probes.py. Practice quota unchanged at 189. All sessions under runs/sandbox/, labelled 'probe <name>'.
- Results and the rules that follow: experiments/RESULTS.md. Short form in docs/LEARNINGS.md.

## 2026-10-10 15:59 CEST · Jonathan @ MacBook-Pro-von-Jonathan
**[finding] Only the first term sheet can be accepted; a final offer is final**
- Accepting an alternative's ID: 422 'not a standing offer in this session' (4 of 4). Sending its terms back as our sheet: supplier answers 'agreed', then accept (2 of 2).
- After final_offer: a lower-price push lost the deal once in two; trade, later start and a holding message left the offer unchanged. Nothing was gained in 8 sessions.
- A holding message without a term sheet keeps a final offer alive and restarts the 60 s clock.

## 2026-10-10 15:59 CEST · Jonathan @ MacBook-Pro-von-Jonathan
**[finding] The supplier mirrors the size of our concessions, not our opening level**
- D01, 20 scripted sessions, same terms: first counter always 51.50 whatever we opened with. Then it gave back 0.6-0.85 of each of our steps and said final_offer at our 6th message.
- Steps 0.05 -> final 51.40 (score 0.68); 0.15 -> 50.86 (0.77); 0.30 -> 50.63 (0.82); 0.40 -> 50.23 (0.89). Opening at 49.00 instead of 50.00 with the same steps: no change.
- Policy: open low, about five large steps, never shrink the steps early. Measured on one demo supplier; confirm on a practice supplier (H14: P07, 1 session).

## 2026-10-10 15:59 CEST · Jonathan @ MacBook-Pro-von-Jonathan
**[finding] RFQ: one loop per thread, and never leave a thread at final_offer waiting**
- Kit play() on D02: 2 timeouts per session. One loop per thread: 0. Replies take 30-59 s, so rounds in lockstep still break the other thread's clock.
- A supplier at final_offer left for over a minute withdrew when we came back to accept. A timeout is counted when the session is next touched; the follow-up carries a new offer ID.
- Citing the rival's offer by ID is 'verified'. An early 'agreed' means the ask was too high: C_best in D02 is 156,739, best closed about 186,000.

## 2026-10-10 16:08 CEST · Jonathan @ MacBook-Pro-von-Jonathan
**[decision] Pull before every run; built into the run commands**
- Rule from Jonathan: whenever teammates have pushed, their commits must be pulled before a new run starts, so no run measures an outdated agent.
- Built in: 'arena play', 'arena run', scripts/pull-runs and experiments/sandbox_probes.py call scripts/pull-first. It fetches; if origin is ahead it pulls (rebase, autostash) and restarts the command on the new code; on a conflict the run does not start.
- New runners or scripts that open arena sessions must call arena_kit.cli.pull_first() first. Exceptions: arena-sim on localhost never pulls; 'arena run --set final' only reports (the final runs the frozen commit); ARENA_NO_PULL=1 switches it off.
- Tested with two clones: teammate pushes -> pulled and restarted on the new code; nothing new -> starts directly; conflicting local commit -> run refused. Rule text: AGENTS.md section 2.

## 2026-10-10 16:22 CEST · Amiad @ fedora
**[change] Lab v1: local twins of the suppliers we played, and a backtest against our real sessions**
- sellm/lab/: LocalTable (the kit's RemoteTable interface: kit play() and any agent run unchanged, no HTTP, no clock, no quota), SupplierThread (the supplier's decision), Persona (value, floor, dynamics), ClaimChecker (cited data by the published rules), twins.json (15 suppliers of the 12 cases in runs/, incl. D02).
- Commands: 'uv run python -m sellm.lab play P01 [--agent llm]', 'twins', 'calibrate' (rebuild twins.json after new sessions are pulled), 'backtest [--fit]'. tests/test_lab.py: 28 tests, 1.3 s.
- Supplier model: accepts a package when its cash value to the supplier (kit supplier_value at its cost of money, plus lever premiums read from its alternative sheets) reaches its floor; first counter a fixed share of (opening - floor), then gives back a share of each of our steps up to a per-round limit that shrinks, final_offer after its patience, may walk when pushed after final_offer (Jonathan's probes, experiments/RESULTS.md).
- Report for the team: runs/lab/BACKTEST.md. Not yet: strategy tournament, invented suppliers.

## 2026-10-10 16:22 CEST · Amiad @ fedora
**[finding] A supplier's floor is its full cost in value terms; C_best pins it down**
- Calibrating the floor so the cheapest acceptable package costs exactly C_best gives P01 full cost 129.91 (at 8 % cost of money); the arena's relationship charge of 813 on our P01 deal at 133.70 implies 129.95. Two independent routes, 4 cents apart.
- Floors vs should-cost where a plant-specific estimate exists: P02 363.96 vs 374.95, P03 397.46 vs 403.21, P10 25.64 vs 24.31 - within the estimate's own error of about 5 %.
- How far above the floor the kit LLM agent closed (value terms): P01 2 %, P02 2 %, P04 1 %, P11 4 %, P07 8 %, P08 10 %, P18 20 %, P10 31 %. That is the room our strategy has to win; it is largest in P10, P18, P08.
- Lever prices from suppliers' alternative sheets: payment days at 6.4-6.6 % a year (P02, P08), 9.3 % (D01), about 35 % for the Czech job shop in P05 (16 days = 0.50); lead time 0.15 EUR per unit per day (P10); 1,200 ppm tighter about 1.4 EUR per unit (P11).

## 2026-10-10 16:22 CEST · Amiad @ fedora
**[finding] Backtest: real suppliers give back little per round, whatever our step**
- 233 real supplier replies (13 practice + 33 sandbox sessions) replayed into the twins: mean error 0.95 % of the opening value per reply, status right in 210 of 233. Good on D01, P01, P04, P07, P08 (<= 0.6 %); weak on P05 (8 %) and P10 (3.3 %), one session each.
- Best global fit: first counter 35 % of (opening - floor), then mirror 0.5 of our step, but at most 0.4 % of the opening per round, final_offer at our 6th message. Most twins sit at the grid's lowest limit: the per-round limit, not the mirror, is what binds when our steps are large.
- So the first counter and the number of rounds decide most of the outcome; a bigger step only helps up to that limit. To be tested in the tournament, then on one practice case.

## 2026-10-10 16:32 CEST · Amiad @ fedora
**[change] Lab v2: invented suppliers, a rule-based strategy with knobs, and a tournament runner**
- sellm/lab/invent.py: scenarios with suppliers drawn from the data package (name, country, standard terms, credit index -> cost of money, scorecard ppm) on mutated cases: any goal, 2-4 negotiable fields of 10 (incoterm and tooling included), must-haves, alternatives, RFQs with 2-3 suppliers; random economics and dynamics in the ranges the backtest found.
- sellm/lab/strategies.py: Calculator, a numbers-only buyer with 14 knobs (structure keep/buyer/joint, floor estimate, opening, steps and their shape, sheets per mail, after final_offer accept/hold/push, claims none/cost/bank, tone, ...). Uses only the case file, the thread and the data package, so it can play the arena too. Never accepts a deal worse than the cheapest opening (that scores 0).
- sellm/lab/tournament.py + CLI: 'python -m sellm.lab compare naive calc', 'python -m sellm.lab search --minutes 60' (successive halving over random knob sets, then mutations of the best). Reports in runs/lab/<time>-<mode>/report.md (mean, twins, invented, held-out P04/P10/P18, worst 10 %, crashes, broken must-haves, deals worse than the opening); raw rows .jsonl.gz are git-ignored.
- Claim checker fixed after comparing with the arena: a letter and a contract are one argument across the whole e-mail; a letter cited again is 'duplicate'. Backtest now opens all RFQ threads first (rival offers are citable). Mean error 0.79 %, status 218/237.
- Smoke run (runs/lab/20261010-1630-compare-smoke): Calculator default 48.7 vs kit naive 36.4 over 12 twins + 60 invented; naive broke a must-have 10 times.

## 2026-10-10 16:32 CEST · Amiad @ fedora
**[finding] Lab validation: the kit agents score in the lab about what they scored in the arena**
- Same agent in lab and arena (runs/lab/VALIDATION.md). Naive: P01 0.590 vs 0.583, D01 0.235 vs 0.200. Kit LLM (gpt-6.1-sol, one run each): practice mean 59.8 in the lab vs 61.5 in the arena; within 0.03 on D01, P01, P03, P07, P08; off by 0.12-0.31 on P04, P05, P10, P11.
- Data that moved a real supplier ('it holds and we took it into account'): notice period P01, volume change P03, quality record P11, rival quote D02. No effect: notice period P02, volume change P04 and P10, delivery record P18. Verified is not convincing, as the brief says.
- Use: rank strategy variants by the mean over many scenarios; do not read one case's lab score as a prediction; confirm winners in the sandbox, then on practice.
- LLM spend for this check: about 60 calls on Amiad's key.
## 2026-10-10 16:38 CEST · Omar Homsi @ omar-Yoga-7-2-in-1-14AKP10
**[change] Ignore .idea/, set up uv on a new machine**
- Added .idea/ (local PyCharm project metadata) to .gitignore so it stops showing as uncommitted noise.
- New machine (omar): uv was not installed; installed via the official standalone installer into ~/.local/bin, then uv sync --all-extras and uv run arena data.
- No code or behaviour change; arena_kit untouched.

## 2026-10-10 16:45 CEST · Amiad @ fedora
**[run] Lab search, 10 min: best Calculator variant 54.5 vs kit naive 38.7 (lab only, no arena)**
- Sat 16:32-16:44, 'python -m sellm.lab search --minutes 10 --invented 150 --start 64 --seeds 2', commit 8309fc4. 27,800 negotiations on 12 twins + 150 invented scenarios, 8 cores. No arena calls, no LLM, no quota.
- Best: mean 54.5 (twins 60.4, invented 54.0, P04/P10/P18 58.4, worst tenth 9.1); 0 crashes, 0 broken must-haves. Kit naive in the same run 38.7 (twins 22.3). Report: runs/lab/20261010-1632-search-first/report.md.
- The top 12 agree on: structure=joint (cheapest terms for us at the same value to the supplier, guessing its cost of money at 20 %), 8 planned steps, open from 85 % of its opening (not from should-cost: that opening is too close and makes the steps small), accept a final offer, one new checked figure per round (claims=bank), 2-3 sheets per e-mail. Tone and asking for a breakdown make no difference in the lab (it reads keywords only).
- Per twin, best variant: D01 0.90, P03 0.89, P04 0.81, P07 0.81, P11 0.81, P01 0.71, P10 0.63, P05 0.48, D02 0.36, P08 0.35, P18 0.31, P02 0.18. Weak where the kit LLM agent was weak too (P02, P18, P08).
- Caveat: P04/P10/P18 were in the search set, so they are not a true hold-out yet; and the winner exploits the lab's mirror model. Next: confirm in sandbox D01/D02 (needs the arena key on Amiad's machine), true hold-out in the search, twins as families of plausible variants.

## 2026-10-10 16:50 CEST · Omar Homsi @ omar-Yoga-7-2-in-1-14AKP10
**[finding] Supplier prose is not fact-checked; only term sheets, documents and our own facts.json are**
- brief/api.md: quote PDFs, cost breakdowns, 8D reports, delivery schedules and order confirmations are rendered from the supplier's structured state, never written by an LLM, byte-stable - their figures bind.
- The e-mail body's reasoning (why it raised the price, what it mentions in passing) is in-character colour: 'cheaper engineering variants a supplier mentions are information, not binding terms,' and identical messages need not get identical replies.
- Our own facts.json is the one checked ground truth for what we cite, with documented quirks from data/package/KNOWN_ISSUES.md (should_cost error 5-15%, sup:71999=sup:70210, stale PO prices, OTD depends on which of 3 dates, ppm jumpy on small lots) - these are deliberate realism, not bugs to fix.
- Consequence for the argument bank (workstream B): build claims only from facts.json-checked IDs, never repeat a supplier's stated reason as if it were verified.
- Added to docs/LEARNINGS.md under General.

## 2026-10-10 16:58 CEST · Amiad @ fedora
**[change] Lab v3 part 1: a clock, timeouts, the wave cap, and supplier archetype behaviours**
- sellm/lab/table.py: clock=True simulates time. Replies take 20-60 s; a thread left more than 60 s gets a timeout when the session is next touched (our message refused with 409, offer re-issued under a new ID, patience drops, a final offer may be withdrawn, three in a row end the thread); wave_cap_s ends the session without a deal, as the Live Final's 8 minutes.
- play_lab(table, agent, mode='sequential'|'parallel'): sequential plays like the kit's play() (each reply awaited, so other threads' clocks run), parallel is one loop per thread. Closes with the kit's closing_move 90 s before the cap. A 422 is counted in the result instead of crashing; strict=True raises as the kit's play() would.
- Found with it: in an RFQ played one thread at a time, a timeout on thread B replaces B's offer ID while we wait for A; accepting B's old ID is a 422, which crashes the kit's play() and loses the case. P05 twin: sequential 5-7 timeouts and 0.04-0.13, parallel 0-1 timeouts and 0.12-0.48. Our final runner needs one loop per thread and must re-read a thread before accepting.
- Supplier behaviours added (persona fields): noise per concession, approval ladder (one round on hold, then the step), no_bid, walking after an ultimatum (tone_walk), withdrawing when left at final_offer, 'Which figures is that based on?', delivery schedule and 8D report attachments, an optional LLM reader of our e-mails (sellm/lab/reader.py llm_reader). Twins can vary within a family of plausible parameters (Persona.ranges, vary=True).
- Fixed: a term sheet may use the supplier's standard value even when it is not in term_options (brief/api.md, Terms). All 21 practice and sandbox case files are now in sellm/lab/cases/ (read with GET /v1/cases, no session, quota still 189).

## 2026-10-10 17:16 CEST · Omar Homsi @ omar-Yoga-7-2-in-1-14AKP10
**[change] Our agent is registered: --agent sellm plays sellm/agent.py**
- arena_kit/cli.py: --agent choices naive|llm|sellm (AGENTS); sellm -> sellm.agent.make_agent(package), one fresh agent per case. sellm/agent.py is the single entry point: whoever builds the negotiator replaces make_agent, nobody needs to touch cli.py again.
- For now make_agent returns the lab's Calculator with the best knobs of runs/lab/20261010-1632-search-first/report.md #1 (structure joint, 8 steps, open 10% below, 3 sheets, claims bank, accept final offer), tone warm instead of neutral (tie in the lab; FAQ P01 shows tone matters). On the 10 practice twins that is 59.8 in the lab, equal to the kit LLM agent there. Not played on the arena; README keeps --agent llm for the final until sellm beats it.
- pyproject.toml: [tool.hatch.build.targets.wheel] packages = [arena_kit, sellm]. Before, a non-editable install (Dockerfile, a VM with uv sync --no-editable) shipped only arena_kit, so --agent sellm would fail with ImportError on the final machine. Checked: the built wheel contains sellm/ (36 files).
- Verified without quota: tests/test_sellm_agent.py plays all 3 arena-sim cases with and without the data package; the real CLI against a local arena-sim: S01 0.824, S02 0.829, S03 0.728 (scripted supplier, plumbing only). uv run pytest 68 passed, 1 skipped; ruff clean.
- README run section: OpenAI env vars (the team's provider), the sellm agent, which agent the final runs.

## 2026-10-10 17:18 CEST · Amiad @ fedora
**[change] Lab v3 part 2: families, scenarios for anything the final may bring, stress test, train/test tournament, scripts/lab**
- Twins are families now: backtest --fit records per parameter the values that explain the real replies within 15 % of the best fit (sellm/lab/twins.json ranges); runs draw a member per seed. P18's per-round limit, for one, is anything from 0.2 % to 2 % - the data cannot tell.
- invent.py v2: the 9 unplayed practice case files (P06, P09, P12-P17, P19) with their real suppliers from the data (vendor master terms, scorecard ppm, cost of money from the credit index, floor from the plant's should-cost, opening from the trigger letter's asked price), plus invented cases of all 7 types, 1-7 negotiable fields, must-haves of every operator, 8 supplier archetypes from the brief (family, group with approval ladder, cash-short job shop, near-monopolist, trader, quality, capacity, generous) and 12 edge cases (opening breaks a must-have, walking away is best, short round limits, no_bid bidder, case-only facts, prices per 100, three years, single order, falling index, all fields, price only, current contract). 120 scenarios in 3 s.
- tournament.py v2: train pool (twins without P04/P10/P18 + generated) and an unseen test pool (held-out twins + fresh generated); search tunes on train and ranks its best on test; time checked between batches of 400; progress.log live; report broken down by case type, goal, archetype and edge case; counts crashes, 422s, broken must-haves, deals worse than the opening, below-alternative endings, wave-cap endings and timeouts; any agent as 'module:Class' (e.g. sellm.agent:make_agent).
- stress.py: an agent on twins + every edge case + generated scenarios, sequential and parallel, verdict FAIL on any crash, 422, broken must-have or worse-than-opening deal. Calculator v2 knobs: adaptive steps, learn from the supplier's pick, hold a finished thread in an RFQ (all off by default; sellm/agent.py unchanged).
- scripts/lab: search/compare/stress in the background with nohup, status, stop, play; guide sellm/lab/README.md. 'validate' compares lab and arena for the naive agent for free (D01 0.239 vs 0.200, P01 0.590 vs 0.583) and the kit LLM agent with --llm. Tests: 40 in tests/test_lab.py, all 74 green.

## 2026-10-10 17:18 CEST · Amiad @ fedora
**[finding] Lab: the first search's knobs hold on scenarios they were never tuned on**
- Same knobs as sellm/agent.py (from runs/lab/20261010-1632-search-first) against the Calculator default, on the 12 twin families + 80 freshly generated scenarios, clock on, one loop per thread, 2 seeds: 58.6 vs 52.3. Adaptive steps (58.2) and learning from the supplier's pick (58.2) added nothing; both 57.3.
- Preliminary weak spots of the Calculator (small smoke runs, 1-2 seeds, read as pointers): raw_material and rfq cases, cases with 5-7 negotiable fields, near-monopolists and groups with an approval ladder, short round limits (4-6), prices per 100 pieces. A real search will say more.
- No search was run after these changes (Amiad's instruction: build the environment first, no runs yet); no arena calls, quota still 189.

## 2026-10-10 17:28 CEST · Amiad @ fedora
**[finding] The lab ranks strategies as the arena did: Jonathan's five D01 step probes, replayed closed-loop**
- experiments/RESULTS.md section 3 (open at X, fixed step, accept when the supplier stops saying open) replayed on the D01 twin family, 40 members each: 0.678 / 0.747 / 0.762 / 0.842 / 0.881 against the sandbox's 0.68 / 0.75-0.80 / 0.75-0.82 / 0.79-0.86 / 0.88-0.90. Same order, every level inside the arena's range.
- Before the probes were part of the fit the lab gave the biggest steps only 0.831: its per-round limit was too tight, which would have biased searches toward small steps. Fit now: backtest loss + 10 x the probes' mean score gap. Mean error per real reply 0.77 %, status right in 217/237.
- One demo supplier: it shows the lab can rank, not that every twin does. 'python -m sellm.lab validate' prints this table and the naive agent's lab vs arena scores (free).

## 2026-10-10 17:28 CEST · Amiad @ fedora
**[change] Lab: standard errors and paired tests in reports, an LLM reader option, Calculator prices the relationship term**
- Reports show Test +- SE and pair #1 with the runners-up and baselines on the same test scenarios ('+8.8 +- 4.0 points, clearly better' / 'not distinguishable'): a difference under two SE is noise.
- --reader llm: the lab's suppliers read our e-mails with an LLM (LAB_READER_MODEL or LLM_MODEL, cached per text) instead of keywords; costs calls, off by default.
- Found with the lab and fixed in the Calculator (so in sellm/agent.py): it ignored the relationship term in stabilise/secure_supply cases and could close a deal that the term made worse than the opening (score 0): 2-4 of 324 negotiations. It now prices the term with its own floor estimate (should-cost, else floor_guess of the opening's value) for choosing and for the alternative check, and refuses only deals that are surely worse than the opening (C without the term). C_open follows the arena: the cheapest opening that keeps the must-haves, else the cheapest opening (P11 confirms it: 817,578 is its must-have-breaking opening). Result on 162 scenarios x 2: 0 worse-than-opening deals.
- Invented suppliers' floors now sit within 12 % of the part's should-cost where one exists, as the data package says real estimates do. Stress verdict: FAIL on crashes, 422s and broken must-haves; a deal worse than the opening is a warning (it scores 0 like walking away without an alternative).

## 2026-10-10 17:30 CEST · Amiad @ fedora
**[finding] Lab: capping planned steps at the round limit costs points (tested, not adopted)**
- Idea: with a round limit of 4-6, plan fewer, bigger steps. Paired test on the same 40 short-round scenarios x 2 seeds, sellm/agent.py knobs: 54.2 without the cap, 49.3 with it, -4.9 +- 0.5 points.
- Why: our price rises faster and meets the supplier sooner, at a higher level. Staying low until the rounds run out and then taking its standing offer is better under the mirror-and-limit dynamics the backtest supports.
- A plausible change the lab refuted in a minute; the code keeps a comment at Calculator.ask.

## 2026-10-10 17:36 CEST · Amiad @ fedora
**[change] Lab UI: start, watch, tune, extend and export runs in the browser (scripts/lab ui)**
- sellm/lab/ui.py: a local page on 127.0.0.1:8765 (FastAPI from the kit's sim extra, one HTML page, no build step). Start search/compare/stress with every option; knobs as JSON, as a table of all 14 Calculator knobs, or loaded from any run's best.json.
- Runs tab: live progress, rendered report, stop, 'extend' (more minutes, seeds, scenarios), 'use #1 knobs', 'stress-test #1', '#1 as sellm/agent.py KNOBS' (a block to paste), exports report.md / best.json / rows.csv / run.zip. Play tab: one negotiation with its transcript.
- Runs are their own processes (start_new_session) and survive the UI; commands are built as argument lists from an allowlist, paths are confined to runs/lab. compare --knobs now applies to calc only. Test: test_ui_serves_runs_exports_and_refuses_bad_input.

## 2026-10-10 17:41 CEST · Omar Homsi @ omar-Yoga-7-2-in-1-14AKP10
**[decision] Groups A/B/C with tasks, and the dossier schema (docs/PLAN.md sections 3 and 10)**
- Section 3: three groups without names - A negotiation (negotiator behind make_agent, time budget, levers, uses the dossier), B data and arguments (stub dossier() first, builder, case overlay, argument bank, Sunday rebuild), C runner, measurement, final (RFQ one loop per thread + re-read before accept, waves, measurement, final machine, submission). Each with the skills it needs, priorities by effect with evidence, and what is still to agree (which agent plays the final, LLM key, machine, quota, default policies).
- Section 10: one schema for dossier and mini-dossier. Core fields frozen for schema_version 1 (supplier_id, coverage, standard_terms, economics.cost_of_money/cash_pressure/archetype, signals, parts.*.price_unit/current_price/should_cost/floor_estimate/alternatives, citable); every other field may be added anytime. Builder: one command, deterministic, no LLM, committed. dossier(supplier_id, part_ids, case, opening) never raises; unknown supplier -> case overlay only.
- Rules grounded in the data: cost_of_money from skonto terms first (2 %/10 d vs 30 d = 0.36; 4 detailed suppliers have skonto), else job_shop 0.25 (P05 Czech shop ~0.35), group 0.065, family 0.09; floor from plant-specific should-cost, else generic DE x country factor; 12 signal kinds mapped to the trade each implies (e.g. cash_short -> payment days for price), from documents, news topics (noise excluded), quote remarks ('head-office directive', 'Payment within 10 days requested', 'Material covered until March 2027') and history notes.
- Example of what a final-pool supplier looks like: sup:70130 Wimbacher (in no practice case) asks three times for faster payment, has idle shifts, 'the bank is watching', and says 'I cannot sign anything that lowers our margin' -> cash_short + margin_floor + wants_volume: trade payment days and volume, not price.

## 2026-10-10 17:41 CEST · Omar Homsi @ omar-Yoga-7-2-in-1-14AKP10
**[finding] Calculator's should-cost lookup can take another plant's estimate (latent, no practice case affected)**
- sellm/lab/strategies.py looks up cost:<part number>. For two parts the package has one estimate per plant: cost:310012 is Wimbacher's (sup:70130), Brandlhuber's is cost:310012-70110; cost:350010 is sup:70510's, sup:70520's is cost:350010-70520.
- So a hidden case with Brandlhuber on part 310012 would get Wimbacher's cost as its floor, and citing it to Brandlhuber is not about this supplier. No practice or sandbox case uses these parts (checked all 21 case files).
- Fix (lab owner's file, not touched): read parts.<part>.should_cost from dossier() once B delivers it - the schema matches on part and supplier (docs/PLAN.md section 10).

## 2026-10-10 17:45 CEST · Omar Homsi @ omar-Yoga-7-2-in-1-14AKP10
**[decision] Rebalanced the groups: three tasks with a fixed interface moved to C**
- Moved to C: the per-move deadline from A (15 s target, 40 s hard, around any agent in the runner; falls back to make_agent's new 'fallback' attribute, else a holding message without a term sheet; every fallback logged), citable_for() and arguments() from B (sellm/claims.py), and the research on P08/P18/P10 from B.
- Kept together: A's negotiator and the Calculator's use of the dossier (one decision logic); B's builder, case overlay and signal rules (one schema, the same extraction rules). C's code is front-loaded: runner by Sat 20:30, then arguments and research; if the runner is late, the argument bank and the research go back to B.
- Slides: C builds the skeleton and picks the replay; each group writes the slide about its own part. Details: docs/PLAN.md section 3; interfaces in sections 2 and 10.

## 2026-10-10 17:45 CEST · Omar Homsi @ omar-Yoga-7-2-in-1-14AKP10
**[finding] What the data package says about suppliers (now in docs/CONTEXT.md section 13)**
- Skonto terms on 4 detailed suppliers (sup:70210, 70350 2 %/10 d; 70280 3 %/10 d; 70230 2 %/14 d; all vs 30 d) give the cost of money directly: 2 % for 20 days is 36 %/year. Note: P05's Czech shop (sup:70240, ~35 % measured) has no skonto terms.
- Signals sit in quote remarks ('head-office directive', 'Payment within 10 days requested', 'Material covered until March 2027') and news topics (allocation, credit_watch, short_time_work, free_capacity, succession, ...; 10 items are 'noise').
- Should-cost: 22 plant-specific, 6 generic DE; two parts have one estimate per plant (cost:310012 vs cost:310012-70110, cost:350010 vs cost:350010-70520). 34 of 55 parts have more than one approved supplier. 17 suppliers amber/red in 2026Q3. We pay some suppliers up to ~19 days late. Index clauses in only 4 contracts. No practice case file carries 'facts'.
- Also documented: running arena-sim by hand (its 'practice sessions left' is the sim's own counter, not our quota; CONTEXT section 9) and installing uv on a machine without it (pip install is refused on Ubuntu; AGENTS.md section 7).
## 2026-10-10 17:46 CEST · Amiad @ fedora
**[run] Lab search from the UI, 1 minute: inconclusive (Amiad's trial of the UI)**
- Sat 17:42, 'search --minutes 1' from scripts/lab ui, commit 20449e8. Time ran out in the first round (1,488 of its negotiations unplayed), so the ranking is noise: #1 vs the Calculator default +1.3 +- 0.7 points on 83 test scenarios, 'not distinguishable'. All variants beat the kit naive agent by about 29 points.
- A signal worth following: some variants make refused moves (422) - structure=keep 14 times, the default twice - which crash the kit's play() in the arena. To check with a stress test.
- Changed: a search now starts with about 25 variants per minute (at most --start) so the first round can finish, and its report is marked INCONCLUSIVE when it does not. Report: runs/lab/20261010-174243-search/report.md.

## 2026-10-10 17:49 CEST · Jonathan @ MacBook-Pro-von-Jonathan
**[finding] --agent sellm as registered is not ready for a real supplier: first e-mails checked offline**
- Checked offline (no arena call): make_agent() from sellm/agent.py at 49dfc05 on the opening e-mails saved in runs/, i.e. what it would send as its first message.
- D01: asks 40.11 against the supplier's 52.90 and a current price of 48.60 (17 % below what we pay today). The body says 40.47, the sheet 40.11: text and term sheet disagree.
- P01: asks 105.06-105.78 against 138.55, current price 126.53, plant-specific should-cost 132.64 - 21 % below the supplier's estimated full cost, in a 'stabilise' case, with the earliest start date.
- P10: one of its three sheets is 2.98 per unit for 12 months (opening 32.20): the 'same cost to us' alternative solves for a price that offsets the uncovered second year. A real supplier reads that as a mistake or an insult.
- The e-mail is one template line ('We propose EUR x per unit on the terms attached'), salutation 'Dear Sir or Madam' although the contact is named in the opening e-mail.
- Why it matters: the lab's suppliers cannot be offended and read keywords only; the arena's read the whole e-mail and react to tone, trust and manipulation (brief section 2). These knobs won in the lab because nothing there punishes them. Before any practice session: play it in the sandbox (free) and bound the asks.

## 2026-10-10 17:50 CEST · Omar Homsi @ omar-Yoga-7-2-in-1-14AKP10
**[decision] LLM for development and the final: OpenAI gpt-6-sol**
- Every .env: LLM_PROVIDER=openai, LLM_MODEL=gpt-6-sol, LLM_API_KEY. Written into docs/STATUS.md (Decisions), docs/CONTEXT.md section 9, docs/PLAN.md section 3 and the README run section.
- Open: earlier runs are logged as gpt-6.1-sol (D01 0.786, baseline 61.5, lab validation), while this machine's .env already had gpt-6-sol. Whoever ran them: check which model your .env had and log it, so the baseline is compared on the same model.
- Still open: whose key and what budget for an hour of 10 parallel cases in the final.

## 2026-10-10 17:58 CEST · Omar Homsi @ omar-Yoga-7-2-in-1-14AKP10
**[change] Corrected wrong times in PLAN, STATUS and CONTEXT**
- I had written times by hand that were later than the clock (18:30, 18:50, 19:00, 19:05, 18:20, 17:25, 17:30). Replaced with the commit times: agent registered 17:16, groups and dossier schema decided 17:41, rebalanced 17:45, group B claimed 17:48, LLM decided 17:50, data facts checked 17:40, arena-sim checked 17:15.
- No content changed. The timeline row 'Sat 19:00 Each part works alone' is the original plan and stays.

## 2026-10-10 18:11 CEST · Omar Homsi @ omar-Yoga-7-2-in-1-14AKP10
**[change] CONTEXT section 14: --agent now also offers sellm**
- The line said the choices naive|llm are hard-coded in cli.py; since 17:16 AGENTS in cli.py lists naive, llm and sellm (sellm.agent.make_agent).

## 2026-10-10 18:14 CEST · Amiad @ fedora
**[change] Lab: LLM suppliers - an LLM plays each supplier inside the calibrated engine's limits (--supplier llm)**
- sellm/lab/llm_supplier.py, as the brief describes the arena: hard limits from the engine (floor, its usual move this round, approval, patience), and inside them an LLM that knows the company from the data package (register facts, archetype, cost of money, its letters, call and meeting notes, news, past renewals) and the whole thread reads our e-mail and decides counter / agree / final offer / hold / walk away, the price, a variant, documents, and writes the e-mail. Code computes every number and renders sheets and documents.
- Bounds: price between half and 125 % of the calibrated move (+ room for verified data); it cannot stand still when we moved, agree far below its usual ask, say final earlier than one round before its patience, or walk away unprovoked. A failed call uses the engine's reply and counts llm_fail in results and reports. Answers cached in runs/lab/llm-cache/ (git-ignored).
- Everywhere: play/compare/search/stress/validate/backtest take --supplier llm; the UI has a supplier choice in Start and Play; LLM runs use 24 worker processes. Tests with a fake LLM: limits kept, no unprovoked walk-away, failures counted (78 tests green).

## 2026-10-10 18:14 CEST · Amiad @ fedora
**[finding] LLM suppliers match the arena about as well as the engine, once their moves are bounded**
- Closed loop (runs/lab/VALIDATION.md): kit naive agent P01 0.554 (arena 0.583, engine 0.590), D01 0.235 (0.200, 0.239); D01 step probes 0.652/0.707/0.716/0.774/0.814 - the arena's order, levels 0.03-0.07 below (6 members each, SE about 0.03). Replay of the 237 real replies: 0.87 % mean error, status 190/237 (engine 0.77 %, 217/237, but fitted on them).
- Without bounds the LLM played its own idea of the supplier and was far too hard: it held still on the naive agent's first lowball (naive P01 0.096 vs 0.583), while the real Brandlhuber answered with a first counter. The numbers must come from the calibrated dynamics; the LLM varies them, reads and writes.
- In character without being told: the LLM Brandlhuber wrote 'The 14-day payment term is essential for this offer', as the real one did in our practice session. LLM spend for building and validating: about 1,300 calls on Amiad's key.

## 2026-10-10 18:15 CEST · Amiad @ fedora
**[finding] Model check (answer to the 17:50 decision): Amiad's lab runs used gpt-6.1-sol; .env now follows the team**
- The lab's kit-LLM validation (59.8 vs 61.5) and the LLM-supplier validation ran with LLM_MODEL=gpt-6.1-sol on Amiad's key. Both gpt-6-sol and gpt-6.1-sol answer on that key (1.1 s and 1.6 s for a ping).
- Amiad's .env now has LLM_MODEL=gpt-6-sol (team decision) and LAB_SUPPLIER_MODEL=gpt-6.1-sol, so the lab's suppliers keep the model they were validated with; agents use the team's model. To validate the suppliers on gpt-6-sol: set LAB_SUPPLIER_MODEL=gpt-6-sol and run 'python -m sellm.lab validate --supplier llm' (about 200 calls).

## 2026-10-10 18:16 CEST · Jonathan @ MacBook-Pro-von-Jonathan
**[decision] Group A (negotiation) is Jonathan's; A measures in the sandbox itself until group C exists**
- Claimed in docs/STATUS.md. Files: sellm/negotiator.py, writer.py, llm.py, reading.py, sellm/agent.py, tests/test_negotiator.py, experiments/ab_sandbox.py. sellm/lab/strategies.py stays Amiad's: A subclasses the Calculator and does not edit it.
- Deviation from docs/PLAN.md section 3 (noted there): sandbox runs do not wait for C's measurement, because the lab cannot judge wording and C has no owner. Practice: at most 10 sessions for A before the team's full run, each logged.
- The negotiator gets its own LLM time limit and fallback logging, in addition to the per-move deadline planned for C's runner.
- Group C (runner with one loop per thread, argument bank, measurement, final machine) still has no owner and holds priority 1.

## 2026-10-10 18:16 CEST · Jonathan @ MacBook-Pro-von-Jonathan
**[finding] Correction of my 17:49 entry: body and term sheet of --agent sellm do agree**
- Wrong in that entry: 'the body says 40.47, the sheet 40.11'. I had read a truncated output. On D01 the main sheet is 40.47 (the body's figure) and 40.11 is one of the two variant sheets.
- What stands, recomputed in full: first asks of 40.47 (D01, opening 52.90, current 48.60), 105.06 (P01, opening 138.55, current 126.53), 24.63 (P10), 4.35 (P07), 281.28 (P02); planned path on D01 40.47, 43.08, 44.86, 46.43, 47.86, 49.21, 50.49, 51.72, 52.90.
- The 'same cost to us' variants give absurd sheets wherever contract_months is negotiable: 24.76 for 12 months on D01, 1.52 on P07, 2.98 on P10 (the price that offsets an uncovered second year). Calculator._variants; for the lab's owner.
- Baseline model, answering Omar's 17:50 question: every arena run from Jonathan's machine so far (D01 0.786, the baseline of 61.5, all probes with an LLM) used LLM_MODEL=gpt-6.1-sol.

## 2026-10-10 18:20 CEST · Omar Homsi @ omar-Yoga-7-2-in-1-14AKP10
**[change] Intel S1: stub dossier() for group A**
- sellm/intel/schema.py: schema v1 names, enums (coverage, cash_pressure, archetype, 13 signal kinds incl. informal_costing), empty_dossier(); sellm/intel/__init__.py: dossier(supplier_id, part_ids, case, opening, package) returns the full section 10 schema with 'no data' defaults and never raises.
- Defaults are the rules' outcome for a supplier without data: cost_of_money 0.10, cash_pressure low, archetype other; parts get an empty section each.
- tests/test_intel.py: every field of the contract, odd inputs never raise, < 5 ms per call. Next: validator, extraction, builder (S2-S9).

## 2026-10-10 18:21 CEST · Omar Homsi @ omar-Yoga-7-2-in-1-14AKP10
**[change] Intel S2: schema validator**
- sellm/intel/schema.py validate(d) -> list of readable errors: required and unknown keys at every level, enums, cost_of_money in (0, 1], signal kinds/strength/evidence sorted and unique, floor band order, alternatives buyer-private, standard_terms source, finite numbers everywhere.
- tests/test_intel.py: the stub is valid; 14 deliberate breaches are each reported.

## 2026-10-10 18:23 CEST · Omar Homsi @ omar-Yoga-7-2-in-1-14AKP10
**[change] Intel S3: extraction layer over the data package**
- sellm/intel/extract.py Source: read-only SQL with limit 1,000,000 (DataPackage.query stops at 200 rows by default), index series from facts.json, and the Sunday release's documents and news, which DataPackage puts into its ID index only (release-sunday/data/*.csv), not into SQLite - a SQL-only builder would miss Sunday's letters.
- tests/intel_fixture.py: a small package with the real columns and every trap (two plant estimates for one part, skonto, noise news, market news, price per 100, a Sunday release). Tests: fixture, simulated release, and on the real package 46 suppliers, all 5,400 PO lines, 7 documents for sup:70130, 7 market news.

## 2026-10-10 18:26 CEST · Omar Homsi @ omar-Yoga-7-2-in-1-14AKP10
**[change] Intel S4-S5: part and supplier sections of the dossier**
- sellm/intel/derive.py (rules) + assemble.py (sections): current price, history (mean asked/settled/give, below_full_cost), should-cost matched on part AND supplier, floor estimate (plant: +-confidence; generic: x country factor, +-15 %), price/should-cost, index windows 6/12 months with their idx IDs, latest forecast, buyer-private alternatives; identity, vendor-master terms, contract with index clauses, scorecard latest/mean of 4 quarters/trend, complaints in 12 months, documents, news with noise flag, category-matched market news, own quotes, spend, share of turnover (band midpoint when no turnover is filed), payment delay.
- Checked on the real package: all 46 build in 0.23 s and validate; parts 90, documents 208, news 32 (no market news in a supplier's news). Golden: sup:70110 part 310012 -> cost:310012-70110 (347.27, ratio 1.1031), sup:70130 310012 -> cost:310012 (370.21, ratio 0.9702: priced below its cost), shares 6.68/4.87/9.05 %, late 2.8/3.7/19.4 days, sup:70130 OTD mean 87.83, ppm 1147.5, trend better, part 310010 PPI-D351 -3.72 % over 12 months but +6.63 % over 6.
- Signals and the derived economics (cost of money, cash pressure, archetype) come next (S6).

## 2026-10-10 18:29 CEST · Amiad @ fedora
**[run] Lab loop cycle 0-1: champion stress test FAIL (3 refused moves, sequential only); challenger rel_estimate=max rejected**
- Champion = sellm/agent.py KNOBS. Stress (engine, 204 scenarios x 2, runs/lab/20261010-182433-stress-champion): mean 58.4 sequential / 58.8 parallel; 3 x 422 only with the kit's sequential play() (stale offer IDs after RFQ timeouts: group C's runner must re-read before accepting); 5 deals worse than the opening and 6 below the alternative, all in stabilise/secure_supply cases.
- Cause: the Calculator underrates the relationship term (its supplier cost estimate is too low), so it takes deals the true term makes worse than walking away (X71-002: estimated 1,266,308, true 1,339,289, alternative 1,281,528). Weakest: monopolist 42, trader 43, capacity 47, falling_index 51.
- Challenger rel_estimate=max (full cost = max of should-cost and 0.97 x its lowest offer) everywhere: REJECT, -3.5 +- 1.1 points paired on 163 test scenarios (runs/lab/*-challenge-*). Next to try: the cautious estimate only in the check against the alternative (accept() in strategies.py).
- New tools: 'python -m sellm.lab challenge <knobs>' (champion vs champion+change, paired on the test pool, ADOPT/TIE/REJECT); 'search --around champion' (local search from our agent's knobs). New knobs rel_estimate/rel_margin, default off - sellm/agent.py unchanged. No practice quota used (189 left).

## 2026-10-10 18:30 CEST · Jonathan @ MacBook-Pro-von-Jonathan
**[run] Reality check: --agent sellm (Calculator, lab-best knobs) on the real sandbox D01 scores 0.789, four times**
- Sat 18:18-18:22, experiments/ab_sandbox.py --case D01 --arms calc --repeat 4 (commit 29e2d11, one loop per thread, no LLM). Free, quota still 189. Sessions under runs/sandbox/D01, label 'ab calc'.
- All four identical: asks 40.47, 43.08, 44.86 (plus variant sheets 24.76/29.98/33.54 for 12 months); supplier 52.20, 51.30, then final_offer 50.60 after our 3rd message; deal 50.60, 30 days, 24 months, from 2026-12-01; score 0.789. The kit LLM agent scored 0.786 there.
- The supplier's words on the first ask: 'your proposed prices are unfortunately far below a feasible level for our production and cannot be accommodated', later 'remains well below our operational limits'.
- Scripted on the same case, same day (experiments/sandbox_probes.py h13): open 47.00, steps 0.60 -> finals 49.90, 49.80, scores 0.944, 0.957, final_offer after our 6th message. Open 46.00, steps 0.80 -> 0.944, 0.914, final_offer after the 5th.

## 2026-10-10 18:30 CEST · Jonathan @ MacBook-Pro-von-Jonathan
**[finding] A lowball opening costs rounds and a worse first counter; a moderate path reaches 0.95 on D01**
- Opening 18 % below the supplier's floor (40.47 against about 49.65): first counter 52.10-52.20 instead of 51.50, and final_offer after our 3rd message instead of the 6th. Openings 5-7 % below the floor (47.00, 46.00) showed neither.
- Per round the supplier gave more when our step was huge (0.90, 0.70 against steps of 2.6 and 1.8), but two rounds of that are worth less than five rounds of 0.3-0.5: the rounds are the scarce thing.
- Step-size curve on D01 now, same terms, final price / score: 0.05 -> 51.40 / 0.68; 0.15 -> 50.86 / 0.77; 0.30 -> 50.63 / 0.82; 0.40 -> 50.23 / 0.89; 0.60 -> 49.85 / 0.95; 0.80 -> 50.00 / 0.93. C_best corresponds to about 49.65.
- For the lab (Amiad): the twins do not punish an opening far below the floor, which is why floor_guess 0.85 with open_below 0.10 won the search. The four 'ab calc' sessions and the h13 probes are pulled; calibrating on them should teach the lab the penalty. Until then lab-best knobs are not arena-best.
- Also seen: the Calculator closes when its rising ask meets the supplier's falling price (accept_gap 0.01), while the scripts stayed 0.30 below the supplier until it said final_offer. And its 'joint' structure kept the earliest start date.
- Group A therefore builds the negotiator's price path on this curve (open a few percent below the floor estimate, steps of about 1.2 % of the price, never close the gap ourselves) instead of the lab-tuned knobs. One demo supplier: to be confirmed on practice suppliers.
## 2026-10-10 18:30 CEST · Omar Homsi @ omar-Yoga-7-2-in-1-14AKP10
**[change] Intel S6: signals and the economics they drive; section 10 calibrated**
- sellm/intel/signals.py: text rules over documents, non-noise news and quote remarks, plus data rules (skonto, news topics, group, below-cost price, letters with asked_pct, scorecard colour/ppm/overdue 8D, OTD). Strength = min(3, distinct evidence). Then cash_pressure, archetype and cost_of_money (derive.py).
- Calibrated against all 46 suppliers' texts and written into docs/PLAN.md section 10: delivery_problem at OTD < 75 % (below 95 % is true for 43 of 46); quality thresholds; new kind informal_costing ('own spreadsheet', 'had not followed his material and energy prices'); the skonto rate is measured, so no credit surcharge; trader also for 'supply from stock'. Removed false positives: the subject 'Visit by the owner' alone made partnership, 'board' matched 'Control board HB smart', 'no room on price ... head office has frozen all price reductions' is list_price_fixed, not margin_floor. A news item matched by topic and words counts once.
- Golden values hold: sup:70130 cash_short 3, ownership_change 1, job_shop, 0.25; sup:70110 partnership 2, informal_costing 2, family, medium, 0.09; skonto 0.36/0.54/0.45/0.36; sup:70510 group 0.065; noise never a signal (sup:70230, sup:70160); quality_problem 17 = the 17 amber/red suppliers, delivery_problem 9. 43 intel tests.

## 2026-10-10 18:32 CEST · Omar Homsi @ omar-Yoga-7-2-in-1-14AKP10
**[change] Intel S7-S9: profile text, canonical JSON, CLI; 46 dossiers built and committed**
- sellm/intel/render.py profile_text (template, 68-104 words, no LLM); serialize.py canonical JSON (sorted keys, floats rounded to 6 places, NaN refused); build.py build_all/write_all + index.json, calls group C's sellm.claims.citable_for when it exists; __main__.py: build | check | show <id> | signals-report | verify.
- uv run python -m sellm.intel build: 46 dossiers + index.json in 0.40 s, 716 KB, all valid; check rebuilds in a temp folder and compares byte by byte: identical. tests/test_intel.py 48 tests incl. 'the committed dossiers are current'.
- Try: uv run python -m sellm.intel show 70130. Next: the case overlay, so dossier() serves these files (S10).

## 2026-10-10 18:37 CEST · Omar Homsi @ omar-Yoga-7-2-in-1-14AKP10
**[change] Intel S10: the case overlay; dossier() now serves the 46 dossiers**
- sellm/intel/overlay.py + dossier(supplier_id, part_ids, case, opening, package): stored dossier (cached, ~1 ms per call; first call loads the package, ~0.1 s), parts restricted to the case and missing ones built live, case facts (cost: facts set should-cost and floor, doc:/news: facts become texts), briefing and trigger document as signal sources, buyer's alternative and RFQ rivals' opening offers as buyer-private alternatives, and from the opening e-mail: standard terms from the quote PDF, the opening offer, the contact (name above the 'Role, Company' line), the supplier's stated cost drivers checked against the index.
- A blocked old vendor record is mapped to the living company by name, from the data (sup:71999 -> sup:70210), not by a hard-coded ID. Fixed on the way: the package cache keyed by id() could return a freed package's data; part_ids now only accepts part: strings (a dict's keys had become parts).
- Checked: all 21 case files x their suppliers; all 15 saved opening e-mails (standard terms equal arena_kit.docs.standard_terms, contact role, offer ID); P01: Thomas Brandlhuber, Owner; LCI-C 2.7 vs index 2.66 and PPI-C241 6.5 vs 6.54 both match; P05: each bidder sees its 2 rivals' offer IDs; a stranger with cost: facts as dict or list gets should-cost and floor; 200 garbage inputs never raise; p95 < 100 ms. New fields documented in docs/PLAN.md section 10. 57 intel tests.

## 2026-10-10 18:39 CEST · Omar Homsi @ omar-Yoga-7-2-in-1-14AKP10
**[change] Intel S11-S12: citable_for hook tested; 'verify' runs checks V1-V10, all PASS**
- build.py and overlay.py call group C's sellm.claims.citable_for(package, supplier_id, part_ids) once it exists (tested with a stand-in module; if it raises, the build goes on with a warning). Until then citable stays [].
- sellm/intel/verify.py, 'uv run python -m sellm.intel verify': V1 static (no network/LLM code, no practice IDs or names in the package code, ruff), V2 schema 46/46, V3 two builds identical and the committed files current, V4 completeness (suppliers 46, parts 90, documents 208, news 32, no market news leaked, 0.62 MB), V5 every supplier and part recomputed with plain SQL (0 wrong), V6 every ID in the dossiers exists in the package and index windows are valid, V7 the golden tests, V8 overlay on 89 case x supplier calls (p95 2.2 ms), V9 a simulated Sunday release (a new letter lands in its supplier's dossier only and drives cash_short), V10 consumer fields on the hosted cases. RESULT: PASS in 3 s.
- Also: the lab-calibrated floors of P01, P02, P03, P10 lie within 10 % of floor_estimate (test). The wheel ships all 47 dossier files. 63 intel tests.

## 2026-10-10 18:40 CEST · Omar Homsi @ omar-Yoga-7-2-in-1-14AKP10
**[handoff] Group B: dossiers built and verified; human label check and Sunday rebuild open**
- Done: sellm/intel (schema, extraction incl. the Sunday release rows, parts/supplier sections, signals, economics, profile text, canonical JSON, CLI, case overlay, verify). 46 dossiers committed in sellm/dossiers. 'uv run python -m sellm.intel verify' -> V1-V10 PASS; 63 intel tests; uv run pytest 141 passed.
- For group A (Jonathan): d = dossier(supplier_id, case['parts'], case=case, opening=threads, package=package). Use d['economics']['cost_of_money'] instead of guess_rate, d['parts'][p]['floor_estimate']['value'] (None -> fall back), signals for the trade (docs/PLAN.md section 10 table), d['contact']['name'] for the salutation, d['stated_drivers'] (matches False = the supplier's claimed rise is wrong; also check falling series in parts[p]['drivers']), alternatives with kind rfq_rival for RFQs. Never raises, ~1 ms. The Calculator's own cost:<part> lookup can take another plant's estimate; parts[p]['should_cost'] does not.
- For group C (unclaimed): the build and the overlay call sellm.claims.citable_for(package, supplier_id, part_ids) as soon as it exists; format in docs/PLAN.md section 10 (citable). verify V6 then checks every entry with the lab's ClaimChecker.
- Open: V11 (Omar labels the 24 final-pool suppliers blind, then local/compare_labels.py gives precision/recall per signal kind); Sunday 08:00 rebuild (STATUS Next up 4). Data facts found on the way are in docs/CONTEXT.md section 13.

## 2026-10-10 18:59 CEST · Jonathan @ MacBook-Pro-von-Jonathan
**[change] --agent sellm now plays sellm/negotiator.py (v1, no LLM): a stateless negotiator with a bounded price path**
- Why: the lab-best Calculator knobs score 0.789 on the real sandbox D01 (entry 18:30). The new negotiator scores 0.869, 0.909, 0.909, 0.889 (mean 0.894) on D01, 0 timeouts, final_offer after our 6th message; kit LLM agent there: 0.786. Sessions in runs/sandbox/D01 (label 'ab nego-template'), table experiments/results/2026-10-10-s1-d01-nego.json.
- What it does: every move is a pure function of case + threads (our earlier asks are read from the thread, nothing is counted in the object), so a second call for the same state returns the same move, a fresh agent resumes after a crash, and agent.fallback is the agent itself. Path: open a few percent below a target price, concede in equal visible steps, never close the last gap ourselves, accept a final_offer, send its cheaper alternative sheet back to get 'agreed', walk away only when the alternative is the better deal. All in our total cost C.
- E-mails come from sellm/writer.py (template: greets the person who signed, one checked argument per e-mail with figure next to its ID). No LLM call yet: LLM wording will be an opt-in experiment (SELLM_WRITER=llm), it is off in the lab and by default.
- Files: sellm/negotiator.py, sellm/writer.py, sellm/agent.py (make_agent(package, writer=None, **knobs); the old Calculator knobs stay as CALC_KNOBS), tests/test_negotiator.py (11 tests replaying all 63 real sessions in runs/), experiments/ab_sandbox.py (A/B runner, one loop per thread, labels sessions).
- NOT finished: lab stress still shows weaknesses I am fixing now (2 refused accepts in parallel RFQ after a timeout replaced the offer ID; absurd price when it changes the contract length; relationship cost under-estimated when the supplier's opening margin is below the sustainable margin). D02/RFQ not yet played on the real sandbox with it. Do not start a practice run with --agent sellm before the next [change] entry from group A.
- Amiad: sellm/lab/strategies.py is untouched; 'calc' stays the lab reference. To compare: scripts/lab compare calc sellm.agent:make_agent

## 2026-10-10 20:03 CEST · Amiad @ fedora
**[finding] Lab recalibrated with the lowball penalty: it now predicts the negotiator it was not tuned on (0.891 vs 0.869-0.909 on D01)**
- Answer to Jonathan's 18:30 finding (the twins did not punish an opening far below the floor, so lowball knobs won lab searches): supplier model changed in sellm/lab/bot.py + persona.py. An offer more than 6 % below the floor gets a smaller first counter (lowball_first, fitted 0.6 on D01) and costs one extra unit of patience per e-mail; concessions are mirror * step / (1 + step / (cap * opening)) and decay per round, instead of a hard cap (D01: steps 0.15 / 0.6 / 2.6 got about 0.13 / 0.4 / 0.9).
- Refit on 307 real replies (incl. the new ab calc / ab nego / h13 sessions) plus closed-loop D01 targets for 8 strategies with arena scores: mean error 0.72 % (was 0.77), status 254/307.
- Closed loop on D01 (runs/lab/VALIDATION.md): lab-best Calculator lowball 0.717 (arena 0.789; the lab used to say about 0.90), open 46.00/steps 0.80 0.902 (0.914-0.944), open 47.00/0.60 0.873 (0.944-0.957), and the negotiator v1, kept out of the fit: 0.891 against 0.869-0.909. Moderate scripts still underrated by 0.04-0.07.
- So lab results from before this commit that favoured lowball openings (runs/lab/20261010-1632-search-first and the CALC_KNOBS) are superseded; searches from now on punish lowballs. Also new: Calculator knob alt_check=cautious (default off), a lowball test; 153 tests green.

## 2026-10-10 20:22 CEST · Amiad @ fedora
**[change] Lab: the clone agent of Amiad's other agent is in the repo; search and challenge any agent's knobs**
- sellm/lab/clone_agent.py (CloneAgent): written by another agent on Amiad's machine (Sat 18:46-18:54), a Calculator subclass that adds sellm.intel dossiers (cost_of_money, floor_estimate), signal-driven opening (capacity_tight/margin_floor/monopolist/trader: open 3.5 % below; wants_volume/informal_costing: 10 %), and an opening bound of 23 % below the supplier's standing offer. Experimental, never played on the arena; sellm/agent.py does not use it.
- Edited by me (Claude Code, Amiad): lint, a decide() override removed that never fired (it read res['term_sheets'], the move keeps them under res['message']; the Calculator's take_alternative does that job), new knob open_guard (default None = old behaviour). Its runs of 18:46-18:54 (runs/lab/2026...-clone*) were on the supplier model before the 20:03 recalibration.
- Tooling: 'search --agent <agent>' and 'challenge --agent <agent> <knobs>' work for any agent with knobs (sellm/lab/spaces.py: the Calculator's and the negotiator's knob spaces); new Calculator knobs keep_below and alt_check (defaults keep the old behaviour, except keep_below 0.001 replaces a hard-coded 0.999 factor).

## 2026-10-10 20:22 CEST · Amiad @ fedora
**[run] Clone feedback loop, engine suppliers: the clone is behind the plain Calculator on the recalibrated lab; ablation running**
- Baseline (runs/lab/20261010-200703-compare-clone-baseline, twins + 60 train + 100 test generated, 2 seeds, one loop per thread, wave cap 480 s): Calculator default 48.2 +- 3.0, negotiator v1 47.2, clone 45.7 (paired -2.6 +- 0.9 vs the Calculator). The other agent's +2.4 for the clone (18:53) was measured before the lowball penalty and does not hold. Clone weak spots: D02 0.0 (its 'joint' structure asks for EXW and 14 days, near zero-sum levers, and ends worse than the opening), 101 no-deals.
- Cycle 1 (challenge vs the clone, 163 test scenarios x 2): rel_estimate should_cost + alt_check cautious -1.1 +- 0.5 REJECT; open_guard 0.05 +0.5 +- 0.7 tie; keep_below 0.006 +0.0 (never triggers: it accepts when the supplier reaches its ask); structure buyer -1.1 +- 0.7 tie.
- Ablation (each clone deviation reset to the Calculator default): adaptive false +1.2 +- 0.3 ADOPT; use_should_cost false -0.9 +- 0.3 REJECT; steps 5, shape 1.0, sheets 1, accept_gap 0.002, open_below 0.03, floor_guess 0.88 still running. Next: clone v4 from the adopted resets, then confirmed against LLM suppliers (--supplier llm). No practice quota used (189).

## 2026-10-10 20:22 CEST · Amiad @ fedora
**[handoff] For Jonathan (group A): what the lab changed since 18:59, and a comparison to run**
- Your files are untouched: I did not edit sellm/agent.py, sellm/negotiator.py, sellm/writer.py or tests/test_negotiator.py. I changed only lab files: sellm/lab/bot.py, persona.py, twins.json (supplier model, pushed 20:03), strategies.py (new Calculator knobs, off by default), tournament.py, __main__.py, spaces.py (tooling), clone_agent.py (the clone, see above).
- Important for your lab numbers: since d1b07a8 (20:03) the twins punish lowball openings and concessions saturate with the step (your 18:30 finding). Lab results from before that commit, yours and mine, are superseded. On the new lab your negotiator v1 is predicted at 0.891 on D01 (arena 0.869-0.909) without being in the fit.
- Please compare, with the current lab: 'uv run python -m sellm.lab compare sellm.agent:make_agent calc sellm.lab.clone_agent:CloneAgent' (about 1 minute, engine) and the same with '--supplier llm --test 40 --seeds 1' (LLM suppliers, about 600 OpenAI calls). Ours: Calculator 48.2, negotiator 47.2, clone 45.7, all within noise of each other; the negotiator wins on twins 60.7, stabilise 55.2, rfq 47.8, and has 11 deals worse than the opening and 1 refused move in 400 (the relationship term).
- Also for you: 'scripts/lab stress sellm.agent:make_agent' and 'python -m sellm.lab challenge --agent sellm.agent:make_agent "{...}"' test changes of the negotiator's knobs against its defaults; search --agent sellm.agent:make_agent --around champion searches them. Ideas from the clone worth a challenge on your side: dossier cost_of_money and floor_estimate instead of guesses (Omar's 18:40 handoff).
## 2026-10-10 20:24 CEST · Jonathan @ MacBook-Pro-von-Jonathan
**[change] Negotiator v1.1: first ask takes coverage and non-cash levers, steps sized from the thread, RFQ close fixed**
- Real sandbox, template e-mails, no LLM: D01 0.935 0.921 0.921 0.905 (mean 0.920; v1 0.894, kit LLM 0.786, Calculator knobs 0.789). D02 0.535 0.535 0.535 0.514 (mean 0.530; v1 0.448, kit LLM 0.47). 0 crashes. Table and findings: experiments/RESULTS.md section 7; rows experiments/results/2026-10-10-s1*.json; sessions pulled into runs/sandbox.
- 1) First ask: its cash terms as quoted (payment days, Incoterm, tooling, chargeback), every other field where our C is lowest at its opening price; C decides the coverage (it prices uncovered need at the fallback). Payment days move only where the dossier's cost of money is far from ours (gain over 0.3 % of C at equal worth to the supplier). After its answer we ask on whichever structure it has quoted that is cheapest for us.
- 2) No fixed step any more: step = gap to its price / (rounds left x (1 + share of our steps it has given back so far)), horizon 5 of our messages. Reason: the foundry gives back half a step, the job shop all of it and asked for 'bigger steps'; fixed steps were fitted to D01.
- 3) RFQ: the close takes the cheapest valid standing offer whatever its status (one session had closed on an 'agreed' bidder at 15.10 while 14.70 stood); asks to a bidder are capped at what beats the best other offer; a waiting thread gets at most two holding e-mails, then we close.
- 4) Its cheaper alternative sheet is sent back as ours when we are done asking, not only at final_offer.
- Overfitting check (the warning from the challenge desk): the prior on where a deal can end is two numbers (0.945 of the opening with a relationship term, 0.88 without; P04, P10, P18 not used) and only sets the first ask. Sensitivity in the lab, same 204 scenarios x 2 seeds: target share 0.82 -> 49.4, default -> 52.8, 0.94 -> 54.0; opening 3 % below target -> 53.2, 6 % -> 52.8, 10 % -> 50.3. Calculator with the lab-best knobs: 45.8. So the result does not hang on these numbers.
- Open: not played on a practice case yet; sequential play() still gets refused accepts in RFQ (6 of 408 in the lab) - a runner question, see STATUS; LLM wording not built (a specific appreciation sentence gave +0.016 on D01, within noise).

## 2026-10-10 20:24 CEST · Jonathan @ MacBook-Pro-von-Jonathan
**[finding] What the real suppliers showed tonight: they price in value, answer the sheet worth most to them, and differ in how much of a step they give back**
- Details with numbers: experiments/RESULTS.md section 7 and docs/LEARNINGS.md (new section at the top of the sandbox part).
- For the lab (Amiad): (a) D01's first counter is the same in arena_kit.cost.supplier_value for three start dates (51.30 Dec, 51.50 Feb, 51.80 Apr): the real supplier charges for effective_date exactly as supplier_value does. (b) Mirror share: foundry about 0.45, job shop about 1.0 with explicit 'bigger steps' texts. (c) In all 5 real cases with a relationship term the opening carries none, and real final offers sit near the sustainable margin (D01 3.3-4.0 % against 4 %). The invented lab scenarios draw the opening margin (6-24 %) independently of the sustainable margin (3-10 %), so some openings are already below it and every deal there scores 0 (X71-001/002, X77, X79, X80 in the stress pools). No real case looked like that. (d) Backed out of real results: full cost / opening = 0.909 (D01), 0.938 (P01), 0.899 (P03).
- For everyone: with two or three term sheets the supplier answered the one worth most to it in 65 of 79 replies - a menu does not find our best structure. Citing the rival's standing offer made DEMO-C1 match it at once (claim verified).
- Quota: uv run arena me now shows limit 450, used 11, left 439, resets Sun 14:13 CEST. The limit was 200 this afternoon.

## 2026-10-10 20:32 CEST · Jonathan @ MacBook-Pro-von-Jonathan
**[change] Negotiator: no refused accept under the kit's one-thread-at-a-time runner; cost estimate capped at the opening**
- Before a full practice run that Jonathan asked for (10 hosted cases through 'arena run', the kit's play()).
- 1) In a case with several threads and a runner that does not pass 'focus', the negotiator sends one holding e-mail to the thread it is about to accept. That brings the thread's state up to date (answered at once, or refused as late with the new offer ID), so the accept is no longer a 422 that stops the kit's runner. Lab, 204 stress scenarios x 2: sequential refused moves 6 -> 0, mean 52.5; one loop per thread unchanged (52.8, 0 refused). Cost: one message and one supplier reply before an RFQ close.
- 2) A should-cost estimate that would put the supplier's own opening below the sustainable margin is capped there (P02: the estimate is 1.1 % above the opening price). All 5 real cases with a relationship term had none at the opening; an estimate that is too high would make the agent stop early or prefer the alternative.
- 153 tests green, ruff clean. The note of 18:59 (no practice run with --agent sellm) is lifted.

## 2026-10-10 20:35 CEST · Amiad @ fedora
**[decision] Group C goes to Amiad; the Live Final runs on Jonathan's machine**
- Groups: A Jonathan, B Omar, C Amiad (runner, arguments, measurement, final; docs/PLAN.md section 3). C's order: sellm/runner.py first (one loop per thread, waves, closing before the cap, resume after a crash, per-move deadline with fallback, log file), then measurement, sellm/claims.py, ops, submission.
- Final machine: Jonathan's MacBook (Amiad, Sat 20:45). So the runner and scripts/preflight must run on macOS (no setsid, no GNU-only flags); Jonathan starts the final at 11:30 with the command C hands over; pre-flight 09:00 and rehearsal 10:00 on that machine.
- Practice quota for C tonight: up to about 25 sessions (one full run of the 10 hosted cases through the new runner, plus re-runs), each logged with the quota left. Jonathan plans P07/P01/P02 himself: we agree before running, never two runs at once (10 open sessions per key).

## 2026-10-10 20:35 CEST · Amiad @ fedora
**[run] Clone ablation finished: drop adaptive, use floor_guess 0.88 (+1.2 and +1.5 points each)**
- Each of the clone's deviations reset to the Calculator default, challenged against the clone on 163 unseen test scenarios x 2 seeds (engine, one loop per thread, wave cap 480 s; runs/lab/2026...-challenge-ablation): adaptive false +1.2 +- 0.3 ADOPT; floor_guess 0.88 +1.5 +- 0.7 ADOPT; use_should_cost false -0.9 +- 0.3 and shape 1.0 -0.3 +- 0.1 REJECT; steps 5, sheets 1, accept_gap 0.002, open_below 0.03 tie.
- Not combined or confirmed with LLM suppliers yet.

## 2026-10-10 20:35 CEST · Amiad @ fedora
**[handoff] Clone loop paused (Amiad moves to group C)**
- State: sellm/lab/clone_agent.py v3 trails the plain Calculator on the recalibrated lab (45.7 vs 48.2). Next for whoever picks it up: clone v4 = v3 + adaptive=false + floor_guess=0.88, check 'python -m sellm.lab challenge --agent sellm.lab.clone_agent:CloneAgent "{\"adaptive\": false, \"floor_guess\": 0.88}"', then the same with '--supplier llm --test 40 --seeds 1' (about 600 OpenAI calls).
- Traps: keep_below never triggers for the clone (it accepts when the supplier reaches its ask); its 'joint' structure asks for EXW/14 days in D02 (near zero-sum levers) and ends worse than the opening there (D02 0.0).

## 2026-10-10 20:38 CEST · Jonathan @ MacBook-Pro-von-Jonathan
**[run] All 10 hosted practice cases with --agent sellm (negotiator v1.1 @2dadddb, no LLM, kit runner): mean 53.2, baseline 61.5**
- Asked for by Jonathan to see where we stand. 'uv run arena run --set practice --agent sellm --parallel 8', 3 minutes, 10 deals, 0 crashes, 0 timeouts, 0 refused moves. Quota left 429 of 450. Sessions in runs/practice (label 'sellm negotiator v1.1 @2dadddb, kit runner, no LLM').
- Per case, new against baseline (kit LLM): P01 0.874 / 0.789; P02 0.183 / 0.105; P03 0.855 / 0.903; P04 0.000 / 0.810; P05 0.769 / 0.676; P07 0.720 / 0.779; P08 0.152 / 0.433; P10 0.655 / 0.570; P11 0.710 / 0.710; P18 0.406 / 0.377.
- Cases with a relationship term (P01, P02, P03, P10): 0.642 against 0.592. The others (P04, P05, P07, P08, P11, P18): 0.459 against 0.631.
- Why it lost, read from the transcripts: (1) Structure. In P04 and P08 the baseline asked for the 60 days of the running contract ('ctr:... provides 60 days payment, which we propose retaining') and for 24 or 36 months, and the suppliers gave both ('We agree to reinstate the 60-day payment terms', 'For a 24-month agreement we can offer 4.91'); P08 also took the index clause. The negotiator kept the quoted 30 days and 12 months: at the opening price our C says the fallback is cheaper than a second year, so it never found out that the supplier pays for commitment. P04: the supplier did not move at all (4.96, score 0). (2) Opening. The first ask was 17 % below the supplier's price in the cases without a should-cost; P04, P07 and P08 said final_offer after 3 of our messages, P10 after 1, and P08's first counter was 5.90 against 5.65 in the baseline (asked 5.45).
- What worked: P05 (RFQ, three suppliers) through the kit's sequential runner without a timeout or a refused accept - the holding e-mail before the accept did its job - and closed at 28.50 with 14 days (0.769). P01 0.874 with the should-cost target. P10 0.655: its alternative sheet sent back, 'agreed' at 31.80.
- Not changed yet. P04, P10 and P18 stay control cases: nothing is tuned on them; the structure finding rests on P08, P07 and D01 as well. Until a re-run shows otherwise, --agent llm is the agent to beat.

## 2026-10-10 20:45 CEST · Amiad @ fedora
**[change] sellm/runner.py: the final runner - one loop per thread, waves, closing before the cap, resume, per-move deadline, log file**
- uv run python -m sellm.runner --set final --agent sellm (the Live Final: polls /v1/cases?set=final, starts every case of an open wave once, at most 10 at a time, follows seconds_left incl. extensions, stops after 5 waves); --set practice|sandbox --cases P01 D02 ... [--repeat N] [--label ...] for measured runs. Agents as the kit's (naive, llm, sellm) or module:function. arena_kit/ untouched; only cases, sessions, threads, attachments, me are called (a test checks that no live-feed path is in runner, negotiator, agent).
- Per case, after Jonathan's experiments/ab_sandbox.py:play_case: one loop per thread, re-read after 50 s of silence and before every accept (offer ID changed: decide again), 409/422 survived, walk-away only when no reply is in flight. New: decide() runs on a copy in a worker with a 15 s warning and a 40 s limit (then the agent's own fallback if it has one, else a holding e-mail; a second failure in a row closes the case on what stands with the kit's closing_move); a thread at final_offer left 45 s unanswered gets one holding e-mail; closing at cap - max(90 s, slowest round + 15 s); a 409 'one session per case in the final: <id>' resumes the running session; a case that crashed is resumed once.
- Logs: runs/logs/<time>-runner-<set>.log (every move, timeout, refusal, fallback, close) and one JSON line per case (.jsonl). tests/test_runner.py (8 tests, 13 s, no quota): a fake arena on the lab's LocalTable plays an RFQ where a timeout replaces the offer ID right at the accept (survived, current offer accepted), a slow agent, a broken agent, the cap, a resume and two waves. Not yet run on the real arena.

## 2026-10-10 20:45 CEST · Amiad @ fedora
**[finding] For Jonathan and Omar: the negotiator's first move builds the data index in every thread at once (seconds, maybe more than 60 s in a full wave)**
- Seen in the runner tests with a stack dump: Negotiator.rate() calls sellm.intel.dossier(sid, parts, case, opening) without package=, so sellm.intel._source(None) opens a second DataPackage from $ARENA_DATA and builds its whole ID index (arena_kit/data.py _ids, a cached_property: no lock in Python 3.12). _source has no lock either, so the 1-3 threads of every case started at once each build it: the first move of a P05 took over 2.5 s in a test; with the 10 cases of a wave the first moves could run past the arena's 60 s.
- Fixed on the runner's side (sellm/runner.py warm_up: before the first case it calls dossier() once in the main thread, 0.3 s; run_final and run_cases do it). The kit's 'arena run' does not: there the first wave pays it.
- Suggested in your files (not touched by me): Jonathan, pass package=self.package to dossier() in Negotiator.rate(); Omar, a threading.Lock around the build in sellm.intel._source.

## 2026-10-10 20:49 CEST · Amiad @ fedora
**[change] Runner: one close at a time per case, end_reason filled, session ID in every log line**
- Smoke test on arena-sim (local, no quota; S01-S03 twice each, --agent sellm): 6 of 6 closed, no crash, mean 65.8. It showed that in an RFQ both thread loops decided 'accept the cheapest' at once: one accept went through, the other got a 409 (harmless, but two closes could also pick different suppliers). Now a case allows one accept or walk-away at a time; the second loop sees the case ended. Rerun: 0 refused moves.
- end_reason was None in the rows because the arena puts it on the session, not in the accept reply's result; now taken from the session or the action. runs/logs/ is git-ignored (per-machine logs; sessions go to runs/ with pull-runs).

## 2026-10-10 20:54 CEST · Amiad @ fedora
**[run] Runner v1 on the sandbox: D01 0.935 x3, D02 0.535, 0.514, 0.535 - 6 of 6 closed, no crash, no refused move**
- uv run python -m sellm.runner --set sandbox --agent sellm --cases D01 D02 --repeat 3 --parallel 3 (negotiator v1.1, template e-mails, no LLM; commit 76cb8ce). Free: quota 429 of 450 before and after.
- Against experiments/ab_sandbox.py (same negotiator, Jonathan's case player): D01 0.920 -> 0.935 (n=4 vs 3), D02 0.530 -> 0.528. Sessions in runs/sandbox/, label 'runner v1, sellm (negotiator v1.1)'; e.g. https://arena.tacto.ai/replay/2ddae512980855ac
- The 0.514 run had the one timeout of the batch: the negotiator moved DEMO-C1 for 71 s (15.4 -> 15.1) while DEMO-J1 stood open at 14.70 with nothing sent to it; J1 timed out and came back as final_offer 14.60 (the timeout counts as our last offer). Fixed in the runner, see the next entry.

## 2026-10-10 20:54 CEST · Amiad @ fedora
**[change] Runner: any live thread left unanswered for 42 s gets a holding e-mail (at most 2 per thread), not only one at final_offer**
- The negotiator decides per thread (focus) but may answer with a move for another bidder; the runner then sends nothing on that thread. Before, only a thread at final_offer was guarded; now every live thread is (sellm/runner.py guard_clock, Limits.hold_after 42 s, max_holds 2, never in the last round). The clock is measured from the supplier's last reply or timeout follow-up, not from the runner's own re-reads.
- Test: tests/test_runner.py, an agent that only ever moves the first bidder of P05 while its replies are slow: the other two bidders are held, each at most twice, no crash. Group A (Jonathan): if the negotiator wants a bidder to wait on purpose, it should send its own holding e-mail before 42 s, or the runner does.

## 2026-10-10 21:02 CEST · Amiad @ fedora
**[change] sellm/claims.py: the argument bank - citable_for() fills the dossiers' citable, arguments() ranks sentences for the negotiator**
- citable_for(package, supplier_id, part_ids, case=None): every fact the arena checks for this supplier and parts, one sentence each with the figure next to its IDs - cost-driver indices over 12 and 6 months, its own plant's should-cost (else the generic one; never another plant's), the latest rolling scorecard (OTD and ppm), complaints, first and last order of 24 months, the latest forecast, its news, a letter's notice against the contract's, quotes (case_only, rivals private). 906 entries over the 46 detailed suppliers, all 906 'verified' by sellm/lab/claims.py; 5 ms per call. Money is written with a thousands comma (the checker read 'EUR 1608.32' as 160 and called 7 statements contradicted).
- arguments(case, supplier_id, dossier=None, package=None, used=(), private=False, price=None): the ones that help us, best first by case type (quality: ppm first; capacity: forecast first; else notice letter, falling index, should-cost). Leaves out used IDs, buyer-private facts, quotes the case does not name, and a should-cost or quote at or above price (pass the standing price: P02's should-cost 374.95 is above its asked 370.96, P05's generic 36.87 above every offer). P01 gives: 'Your letter doc:20260911-70110-P01 gives us 51 days of notice, while our agreement ctr:4600070110 requires 90 days.', then PPI-D351 -3.7 %, then cost:310010 EUR 132.64.
- Dossiers rebuilt with 'uv run python -m sellm.intel build' (Omar's builder, unchanged; deterministic): they now carry citable, so test_the_committed_dossiers_are_current needed the rebuild. 'sellm.intel verify': RESULT PASS, V6 citable contradicted none, V8 overlay p95 16 ms. tests/test_claims.py: 7 tests.

## 2026-10-10 21:02 CEST · Amiad @ fedora
**[finding] For Jonathan and Omar: how to use the argument bank**
- Jonathan (negotiator): Negotiator.arguments() today has rival offer, own-plant should-cost and falling 12-month indices. sellm.claims.arguments(case, sid, dossier, used=<IDs already cited>, price=<its standing price>)[0]['sentence'] adds the notice letter (P01: 51 vs 90 days, which moved Brandlhuber in the baseline), forecasts (+10.1 % for P10, verified in practice), scorecards for quality cases and 6-month windows. One per e-mail as now; every sentence is checked.
- Omar (overlay): sellm/intel/overlay.py calls citable_for(src.pkg, sid, parts) without the case, so a hidden case's own facts get no citable entries. citable_for takes case= (its facts win over the package's for the same part, e.g. a cost: fact of the case); passing case=case there would cover them. Your files, not touched.
