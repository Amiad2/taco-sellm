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
