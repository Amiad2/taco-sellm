# PLAN - how three people get the best agent running by Sunday 12:00

Status: proposed Sat 15:10 by Jonathan (with Claude Code). **Decided Sat 17:41 (Omar): the three
groups and their tasks (section 3, rebalanced 17:45) and the dossier schema (section 10).** Owners
are open: claim a group in `docs/STATUS.md`. Change this file when the team changes the plan, and
log the change as a `[decision]`.

## 1. Where the points are

The final ranks the mean score per case, on hidden cases with suppliers we have not met. So the
agent must be good on average and must never throw a case away. Points come from three places:

1. **Structure of the deal - arithmetic, no persuasion needed.** Cover the whole horizon, start the
   new price late, pick the cheap payment term, Incoterm, ppm and chargeback, keep the must-haves.
   Evidence: sandbox D01 went from 0.20 to 0.79 only because the LLM agent asked for 24 months
   instead of 12 and a later start. On P01 the start date is worth more than two euros of price.
2. **Price close to what the supplier would really accept.** That needs a target per case (its
   cost, its margin, how far it moved in the past) and enough rounds used well. On D01 the agent
   accepted after 4 of 10 rounds and left 8,580 on the table.
3. **Not losing the supplier.** Tone, a real trade for every ask, arguments whose figures check
   out, and for strategic suppliers a price that leaves them a sustainable margin.

Everything in 1 is code and transfers to any hidden case. Most teams will leave it to the LLM.
We do it in code first.

## 2. The agent we build

Four parts with fixed interfaces, so three people can build in parallel without editing the same
files. Our code lives in `sellm/` next to `arena_kit/`; the kit is untouched except for
`pull_first` and the `--agent sellm` registration, and `sellm` is in the wheel.

| Part | Does | Interface |
|---|---|---|
| **Calculator** `Calculator` in `sellm/lab/strategies.py` (exists, lab-tuned) | For a case and a standing offer: enumerate term sheets over `term_options`, price each with `total_cost`, say what each lever is worth to us, guard must-haves and coverage, set a target and a walk-away value, estimate the supplier's margin for the relationship term | `decide(case, threads)`; `plan(case, sid, events)` per thread |
| **Intel** `sellm/intel.py` (B) and **claims** `sellm/claims.py` (C) | Dossiers built once for **all 46 detailed suppliers**, cached as files, plus a case overlay for any supplier at session open (section 10). The citable facts and the argument bank per supplier and part, with figures computed in code and checked against `facts.json` | `dossier(supplier_id, part_ids, case, opening) -> dict`; `citable_for(package, supplier_id, part_ids) -> [..]`; `arguments(case, supplier_id, dossier) -> [{sentence, ids}]` |
| **Negotiator** behind `make_agent` in `sellm/agent.py` (registered as `--agent sellm`; today it returns the Calculator) | The round plan and the e-mail. Code decides the term sheets and which arguments are allowed; the LLM chooses among them and writes. Falls back to the calculator's move, never to the naive agent | `make_agent(package) -> agent with decide(case, threads) -> {supplier_id, message}` |
| **Runner and measurement** `sellm/runner.py`, `scripts/pull-runs` | All threads of an RFQ in parallel, a round budget from the time left in the wave, logs to a file, resumes after a crash. Saves every session of the team (transcript, trace, breakdown) to `runs/` so nobody replays a case to see what happened | `uv run arena run ... --agent sellm` |

## 3. Groups and their tasks (decided Sat 17:41)

Three groups, one person each, each with its own agent sessions. Claim one in `docs/STATUS.md`.
Each group owns its files; the groups meet only at four interfaces: `make_agent` with its
`fallback` (`sellm/agent.py`), `dossier()`, `citable_for()` and `arguments()` (section 10).
Rebalanced Sat 17:45: three tasks moved to C (see "Why this split" below).

**Priorities**, by effect on the final score:

1. **Never lose a case** (C). Every case weighs the same; a crash, a timeout or the wave cap scores
   no deal. P05 twin in the lab: threads one at a time 0.04-0.13, one loop per thread 0.12-0.48.
2. **Structure of the deal in code** (A). D01 went from 0.20 to 0.79 on contract length and start
   date alone; on P01 the April start is worth more than EUR 2.40 of price.
3. **Price towards the floor** (A, with B's floor estimate). The kit LLM agent closed 1-31 % above
   the floor; the room is largest in P10, P18, P08.
4. **Tone and wording** (A). FAQ P01 recording: ultimatum instead of appreciation, about EUR 13,700
   a year worse.
5. **Checked arguments** (C). Moved the supplier in P01, P03, P11, D02, not in P02, P04, P10, P18; a
   wrong figure is `contradicted` and costs trust.
6. **Depth of the dossier** (B). Indirect: it tells A which trade the supplier wants, e.g. payment
   days for a supplier short of cash.

**A - Negotiation** (`sellm/agent.py`; the Calculator in `sellm/lab/strategies.py` together with
the lab's owner). Read `experiments/RESULTS.md` section 5 first.

1. The negotiator behind `make_agent`: code decides term sheets, target, walk-away and which
   arguments are allowed; the LLM chooses among them, writes the e-mail and reads the reply
   (questions such as "Which figures is that based on?", signals). It never writes a number or an
   ID that code did not give it.
2. `make_agent` returns the negotiator with an attribute `fallback`: an agent whose `decide` uses
   no LLM (the Calculator). C's runner calls it when the negotiator is too slow or fails.
3. Levers beyond price: cover the horizon, start date, payment days; price every sheet the supplier
   sends by C; take its second package by sending it back as our sheet.
4. Use the dossier: `economics.cost_of_money` and `parts.<part>.floor_estimate` instead of the
   global `guess_rate` and `floor_guess`; signals choose the trade (section 10); the relationship
   term in `stabilise` and `secure_supply`; `arguments()` for what may be cited.
5. Test each change: `scripts/lab stress sellm.agent:make_agent` PASS, then the lab tournament.
   Sandbox and practice runs go through C's measurement.

Note Sat 18:16 (A, Jonathan): until C's measurement exists, A plays the free sandbox itself
(`experiments/ab_sandbox.py`), because only real supplier bots can judge wording, and confirms on
practice with at most 10 sessions, each logged. The negotiator also carries its own LLM time limit
and logs every fallback; that complements C's per-move deadline and does not replace it.

Needs: a feel for procurement and negotiation, prompt engineering, Python, the cost function
(`docs/CONTEXT.md` section 5).

**B - Data** (`sellm/intel.py`, `sellm/dossiers/`).

0. First, within the hour: a stub `dossier()` that returns the section 10 schema with empty
   values, so A can code against it.
1. The dossier builder: one command, all 46 detailed suppliers, exactly the schema of section 10,
   deterministic, no LLM, no network. `citable` comes from C's `citable_for()`; leave it `[]` until
   that lands.
2. The signal rules (section 10 table) over documents, news, quote remarks and history notes,
   each signal with its evidence IDs and an excerpt; and the derived fields (`cost_of_money`,
   `cash_pressure`, `archetype`, `floor_estimate`).
3. The case overlay (mini-dossier) at session open from the case file and the opening e-mails,
   with the same signal rules; never raises for a supplier we have no data on.
4. Sunday 08:00: `uv run arena data`, rebuild, commit; read the new letters, news and memo and add
   signal rules if they bring new wording.

Needs: SQL, careful reading of texts, procurement sense, precision.

**C - Runner, arguments, measurement, final** (`sellm/runner.py`, `sellm/claims.py`,
`scripts/pull-runs`, README, slides). Work in this order; priority 1 first.

1. RFQ runner: one loop per thread; re-read the thread before every accept (after a timeout the
   offer ID changes, and the old ID is a 422 that crashes the kit's `play()` and loses the case);
   accept or hold a thread at `final_offer` inside its 60 s. Prototypes: `play_lab(mode='parallel')`
   in the lab, `h3_par` in `experiments/sandbox_probes.py`.
2. Waves: all cases of a wave in parallel (at most 10 sessions), a round budget from
   `seconds_left`, close 90 s before the cap, resume after a crash, log to a file.
3. *(from A)* Deadline per move, around any agent: `decide` runs in a worker; target 15 s, hard
   40 s. Too slow or an exception: `agent.fallback.decide`, or, without a fallback, a holding
   message without a term sheet to the same thread (it restarts the clock and keeps the standing
   offer, `docs/CONTEXT.md` section 8). Every fallback is logged with case, round and reason, so a
   failing LLM is never silent.
4. *(from B)* `sellm/claims.py`: `citable_for(package, supplier_id, part_ids)` fills the dossier's
   `citable` (section 10: index windows the arena accepts, should-cost matched on part and
   supplier, scorecard means, PO pairs, forecast changes, letter + contract notice, rival quotes
   marked private), and `arguments(case, supplier_id, dossier)` turns them into sentences, each
   checked with `sellm/lab/claims.py`: at most 3 per e-mail, each ID once per case, a letter and
   its contract as one argument.
5. *(from B)* Research, offline from `runs/` and `total_cost`: which data unlock P08, P18, P10
   (`C_best` 6-19 % below the current price), and which arguments got "it holds and we took it
   into account". Results go to `docs/LEARNINGS.md`.
6. Measurement: every agent version through lab, sandbox and one full practice run;
   `scripts/pull-runs`; keep the quota (at least 40 for Sunday).
7. Final machine (Tacto advises a cloud VM), LLM key and rate limits for an hour of 10 parallel
   cases; pre-flight 09:00, rehearsal 10:00.
8. Submission: README, commit hash, approach text. Slides: C builds the skeleton and picks the
   replay to walk through; each group writes the slide about its own part.

Needs: Python concurrency (threads, asyncio), robust error handling, ops (VM, logs), care with
figures (item 4), organisation; for the slides, presenting.

**Why this split.** Moved to C are tasks with their own file and an interface already fixed in
section 10: the deadline wraps any agent and touches only the runner; `citable_for()` and
`arguments()` have a fixed input and output; the research is offline. They stay where they are when
they share one piece of logic: the negotiator and the Calculator's use of the dossier are one
decision (two people in the same function would collide), and the dossier builder, the case overlay
and the signal rules are one schema with the same extraction rules (split, they would be written
twice). C's code is front-loaded: the runner (items 1-3) by Sat 20:30, then items 4-5. **If the
runner is late, items 4 and 5 go back to B.**

**Order and dependencies.** A, B and C depend only on section 10 and the `fallback` attribute, not
on each other's progress. The runner plays any `make_agent`. Integration at Sat 20:30 (section 4).

**Still to agree as a team** (proposed defaults in brackets): which agent plays the final (`sellm`
replaces `llm` only if its mean is higher in lab, sandbox and one full practice run including the
hold-out cases P04, P10, P18); whose LLM key and what budget (the model is decided: `gpt-6-sol`); the final machine and who is on duty
(nobody else uses the key during the final); quota per group; default policies (accept a
`final_offer`, warm tone and no ultimatum, never close worse than the cheapest opening, walk away
only to a better alternative).

## 4. Timeline (CEST)

| When | Milestone |
|---|---|
| Sat 15:30 | **Baseline** (done, see `runs/README.md`): kit LLM agent on all 10 hosted cases and on D02. We then know `C_open` and `C_best` of every case and can score any term sheet offline |
| Sat 17:41 | Groups and the dossier schema decided (sections 3 and 10); `runs/` in the repo; `--agent sellm` registered |
| Sat 19:00 | Each part works alone: calculator offline, dossiers for the practice suppliers, runner on `arena-sim` |
| Sat 20:30 | Agent v1 integrated, plays D01 and D02 without errors; **full practice run 1** |
| Sat 23:00 | v2 after reading the replays; **full practice run 2**. Slides skeleton. Then sleep |
| Sun 08:00 | Data release: `uv run arena data`, rebuild dossiers, one sanity run |
| Sun 09:00 | Pre-flight on the final machine and network |
| Sun 10:00 | **Rehearsal**: all 10 hosted cases in parallel, every case done inside 6.5 minutes |
| Sun 11:00 | Our own freeze: no behaviour changes after this. README, approach text, slides, commit hash |
| Sun 11:30 | Runner started and logging; checklist in `docs/CONTEXT.md` section 12 |
| Sun 12:00 | Live Final |

## 5. Quota budget (199 sessions left, no refill before the final)

| Use | Sessions |
|---|---|
| Baseline now | 10 |
| Full runs of a new agent version (run 1, run 2, one spare) | 30 |
| Single-case experiments, each testing one stated hypothesis | 80 |
| Sunday: sanity run after the data release, pre-flight, rehearsal | 25 |
| Reserve | 54 |

Rules: `AGENTS.md` section 5. Every run is logged with the quota left. A practice session without
a hypothesis written down first is a wasted session.

## 6. How we test

1. **Offline first.** With `C_open` and `C_best` known, `total_cost` gives the score of any term
   sheet for free. Most of part 1 above is tested this way.
   **Lab** (`sellm/lab/`, decided Sat 16:00): a local simulator of the suppliers, so whole
   negotiations can be played for free and by the thousand. Twins of the suppliers we have played,
   each calibrated so that the best package it would accept costs exactly the case's `C_best`, plus
   invented suppliers on generated cases against overfitting. A tournament runner plays strategy
   variants against all of them and reports mean, worst case and the held-out cases. The lab is
   only as good as its model of the suppliers: it is backtested against our real sessions, and a
   strategy that wins there is a hypothesis until the sandbox or one practice case confirms it.
   Good for structure (levers, accept timing, final offers, several sheets, RFQ) and robustness;
   weak for wording and tone.
2. **Sandbox for behaviour** (free, real supplier bots): Does pushing on after `agreed` work or
   backfire? How many rounds until `final_offer`? Does an RFQ thread time out while we wait on
   another? What does a cost-breakdown request return? Which opening gets the largest first move?
3. **Practice to confirm**, one case at a time, then a full run per agent version.
4. **Read the trace, not the back office.** `GET /v1/sessions/{sid}` has the supplier's reasons per
   move. The back office only shows who asked whom ("My call: counter.") and is not worth parsing.

## 7. Risks

- **Time in the final.** A round takes about 30 s including the supplier's reply; a wave gives
  about 6.5 usable minutes. Ten rounds do not fit, and an RFQ with three suppliers handled one after
  another fits even less. The runner needs parallel threads and a round budget.
- **Overfitting.** Up to a third of the hidden cases combine supplier and case types practice never
  shows. No rule may mention a practice case or supplier by name; everything is driven by the case
  file, the dossier and the calculator.
- **Silent LLM failure.** Today a failed call plays the naive move. Our fallback must be the
  calculator's best move, and the runner must log every fallback.
- **A wrong figure costs trust.** Arguments come from the argument bank only; the LLM may not
  write a number or an ID that code did not give it.
- **One machine, one key.** Decide the final machine today (open question in `docs/STATUS.md`).

## 8. Data access, timing and overfitting (decided Sat 15:20)

**No vector database, no embeddings.** The data is small and keyed by ID: all 208 letters, e-mails
and notes together are 46 KB; everything written about one supplier is at most about 500 tokens;
reading it by `supplier_id` takes 0.1 ms. Similarity search would add a dependency, latency and
wrong hits and solve a problem we do not have. Instead:

- **Dossier cache**: one command builds a file per supplier from SQL plus the full text of its
  documents; no LLM summary (the texts are short enough to pass whole). Runtime is a dictionary
  lookup by the case's `suppliers` and `parts`. Sunday 08:00: `uv run arena data`, run the command
  again, commit. Schema: section 10.
- **Optimal values are computed, never retrieved.** The best term sheet depends on the case's
  rates, options and must-haves, which are new in every hidden case. The calculator derives it from
  the case file in milliseconds. Storing "what worked on P01" and looking it up is overfitting.
- **A supplier with no dossier must still work**: hidden cases carry `facts` that exist only in
  the case file. The agent builds a minimal dossier from those at the start of the case.

**Where the time goes.** The 60-second clock starts when the session opens and runs per thread.
Case files are readable before that (`GET /v1/cases?set=final` once the wave has started), so all
preparation happens **before** `POST /v1/sessions`: dossier lookup, plan, argument bank, and one
planning call to the LLM if we want one. Inside the session a move is the calculator (milliseconds)
plus one LLM call for the wording. Budget: 15 s per move as the target, 40 s as the hard deadline
after which the calculator's move is sent without the LLM. Nothing in a move may search or summarise.

**Guards against overfitting** (the hidden set includes combinations practice never hosts):

- No practice case ID, supplier ID or supplier name anywhere in code or prompts. Review for it.
- The calculator must handle **every** negotiable field. `incoterm` is negotiable in no practice
  case, `tooling_eur` in one, `effective_date` in two; the final may use any of them.
- Dry-run the whole pipeline (prepare, plan, first message) on all 19 practice case files, not only
  the 10 hosted ones. `P06` (rfq + stabilise) and `P13` (price_increase + leverage) are
  combinations that are never hosted, which is what the final will look like.
- Property tests on generated case files: random negotiable sets, options, must-haves and goals.
  Every proposed sheet has exactly the negotiable fields, values from `term_options`, keeps the
  must-haves and has a finite C.
- Hold out 3 of the 10 hosted cases (P04, P10, P18): never look at them while tuning, play them
  only in full runs. If the held-out mean falls behind the others, we are overfitting.
- Judge a change by the mean over cases, never by one case.

## 9. Not doing

- No vector database or embedding search (section 8).
- ~~No supplier simulator of our own~~: reversed Sat 16:00 (Amiad), see section 6 and `docs/LOG.md`.
  It replaces practice sessions only for screening; confirmation still happens in sandbox and practice.
- No tuning on a single practice case until it scores 1.0: the final cases are different ones.
- No changes to `arena_kit/` beyond registering our agent, so upstream fixes stay easy to take.

## 10. The dossier and the mini-dossier (schema decided Sat 17:41)

One schema for both. The **dossier** is built offline for each of the 46 detailed suppliers. The
**case overlay** is added at session open from the case file and the opening e-mails; for a
supplier we have no data on it is the whole dossier (the mini-dossier). Fixed now so A and B build
against the same thing. A better data point found later costs little: add the field, run the
builder again.

**Change rule.** Fields marked `*` are read by code (calculator, argument bank): their names and
meaning are frozen for `schema_version` 1. Any field may be added at any time. Renaming or removing
a `*` field needs a `schema_version` bump and a `[decision]` in the log.

**Interface** (`sellm/intel.py`):

- `uv run python -m sellm.intel build` writes `sellm/dossiers/<supplier number>.json` for every
  detailed supplier plus `index.json`. Deterministic (sorted keys, no LLM, no network), under 10 s,
  **committed**, so the final machine needs no rebuild. Rebuild and commit after the Sunday release.
- `dossier(supplier_id, part_ids, case=None, opening=None, package=None) -> dict`: the stored
  dossier restricted to `part_ids` (parts it does not supply are built live from the package), with
  the case overlay merged in. `opening` is the threads dict as in `decide(case, threads)` (a thread
  may be a list or `{"messages": [...]}`); `package` a DataPackage or its path, default
  `$ARENA_DATA`. Never raises; for an unknown supplier it returns the overlay alone
  (`coverage: "case_only"`). A blocked old vendor record whose company lives on under a detailed
  record of the same name is mapped to it (in the data: `sup:71999` -> `sup:70210`), with a warning.
  About 1 ms per call once the package is loaded (the first call loads it, about 0.1 s).
- `citable` is filled by `sellm.claims.citable_for(package, supplier_id, part_ids)` (group C); the
  builder and the overlay call it. `arguments(case, supplier_id, dossier)` (group C) turns it into
  sentences for the negotiator.
- Units as in the data: prices per the part's `price_unit`; yearly rates as fractions (0.09);
  percentages as numbers (9.5).

**Fields** (`*` = read by code, frozen)

| Field | Content | Source |
|---|---|---|
| `schema_version`*, `supplier_id`*, `coverage`* | `1`; `sup:...`; `full` (detailed supplier), `thin` (vendor master and spend only), `case_only` | |
| `built_from` | package version, Sunday release merged, case ID of the overlay | |
| `identity` | name, country, category, legal_form, founded, owner_type, group_parent, staff, turnover_eur (or band), equity_ratio_pct, credit_index now and 12 months ago, vda63_grade, abc_class, supplier_since | `suppliers`, `supplier_intel` |
| `standard_terms`* | payment_days, skonto_days, skonto_pct, incoterm, lead_time_days | `suppliers`; in a case the quote PDF wins |
| `economics.cost_of_money`* | its yearly cost of money, and `cost_of_money_basis` (text) | rule below |
| `economics.cash_pressure`* | `low`, `medium`, `high` | rule below |
| `economics.archetype`* | `family`, `group`, `job_shop`, `monopolist`, `trader`, `other` (the lab's names) | rule below |
| `economics.our_share_of_turnover_pct` | our spend in the last fiscal year / its turnover: how much it needs us | `spend_cube`, `supplier_intel` |
| `economics.our_spend_eur` | per fiscal year | `spend_cube` |
| `economics.we_pay_late_days` | mean days we paid after the due date (paying on time is a cheap gift) | `invoices` |
| `signals`* | list of `{kind, strength 1-3, evidence: [IDs], excerpt}`, `kind` from the table below | documents, news (not `noise`), quote remarks, history notes; in a case also briefing, trigger doc, quote e-mail and PDF remarks |
| `contract` | id, valid_to, notice_days, price_basis, payment_days, incoterm, index clauses `{id, series, material_share, deadband_pct}` | `contracts`, `contract_clauses` |
| `parts.<part>` | description, category, material_group, uom, `price_unit`*, quota_pct, tooling_owner, planned_lead_time_days | `parts`, `sourcing` |
| `parts.<part>.current_price`* | price, valid_from | `price_conditions` |
| `parts.<part>.history` | per event: date, type, asked_pct, settled_pct, note; plus `mean_give_pct` (asked minus settled) and `below_full_cost` | `negotiation_history` |
| `parts.<part>.should_cost`* | id, unit_cost, plant_specific, cost_base, confidence_pct, material/conversion/overhead EUR | `should_cost`, matched on part **and** supplier (rule below) |
| `parts.<part>.floor_estimate`* | value, low, high, basis | rule below |
| `parts.<part>.drivers` | per cost-driver series: weight, last month, change over 6 and 12 months, the two `idx:` IDs of each window | `cost_drivers`, `index_values` |
| `parts.<part>.forecast` | latest `fc:` ID, volume next 12 months, change_pct | `forecasts` |
| `parts.<part>.alternatives`* | other approved suppliers and rival quotes `{supplier_id, quote_id, unit_price, date}`. **Buyer-private**: never in an e-mail unless the strategy cites it on purpose | `sourcing`, `quotes` |
| `performance` | latest scorecard (id, otd_pct, ppm, colour), mean of the last 4 quarters with their IDs, trend, supplier-caused complaints in 12 months, overdue 8D | `scorecards`, `quality_notifications` |
| `citable`* | list of `{ids, kind, figure, unit, about, statement, helps_buyer, private}`: every fact the argument bank may use, with the figure the arena checks (`docs/CONTEXT.md` section 7) | `citable_for()` over `facts.json`; in a case also its `facts` and `refs` |
| `documents` | id, date, kind, subject, author, full text | `documents`, `correspondence/` |
| `news` | id, date, topic, headline, `noise` flag | `news` |
| `profile_text` | at most 120 words, written from the fields by a template (no LLM) | |
| `market_news` (added Sat 18:36) | market news without a supplier that match the categories of its parts (power, labour, castings, steel, copper ...): context only, not citable | `news` with no supplier |
| `own_quotes` (added) | its past quotes `{quote_id, part_id, date, unit_price, price_unit, lead_time_days, payment_days, incoterm, remarks}` | `quotes` |
| `contact` (added, overlay) | `{name, role, company, address}` from the opening e-mail: the name above the "Role, Company" signature line | opening e-mail |
| `stated_drivers` (added, overlay) | each "<series> rose x % in twelve months and is y % of our cost" in the opening e-mail: `{series, direction, stated_change_pct, cost_share_pct, true_change_12m_pct, ids_12m, matches}` (matches: within 0.5 points of the index) | opening e-mail, `facts.json` |
| `opening_offer` (added, overlay) | `{offer_id, terms, stated, standard, fixed, validity_days, missing_fields}` from the first term sheet and the quote PDF | opening e-mail |
| `case_facts` (added, overlay) | the case's own `facts`, as a dict by ID (a list is converted) | case file |
| `warnings` (added) | what could not be read or built; empty normally | |

**Rules for the derived fields.** Initial rules; calibrate them in the lab and change them only in
the builder.

- `should_cost`: the row whose `supplier_id` is this supplier (`cost:310012-70110` for Brandlhuber,
  not `cost:310012`, which is Wimbacher's plant); else the generic row without a supplier. Another
  supplier's plant estimate is never this supplier's should-cost and is not cited to it.
- `floor_estimate`: plant-specific should-cost, value = unit_cost, band = its `confidence_pct`
  (floors came out within 3-5 % of it, `docs/LEARNINGS.md`); generic German should-cost times the
  country factor (AT, CH 1.05; CZ, PL, HU 0.825; TR 0.75; CN 0.7), band 15 %; none: null, and the
  calculator falls back to a share of the opening.
- `cost_of_money`: with skonto terms, `skonto_pct / 100 * 360 / (payment_days - skonto_days)` (2 %
  at 10 days instead of 30 is 0.36); else archetype `job_shop` or `cash_short` strength 2 or more:
  0.25 (P05's Czech job shop measured about 0.35); else group 0.065 (P02, P08), family 0.09 (D01),
  founder or private 0.10; plus 0.05 if the credit index is 300 or more or rose 20 points or more in
  12 months. The skonto rate is measured, so it gets no surcharge (calibrated Sat 18:30).
  The credit index is higher-is-worse (groups 147-178; the two cash-short skonto suppliers rose to 302
  and 343).
- `cash_pressure`: `high` with skonto terms or `cash_short` strength 2 or more; `medium` with an
  equity ratio under 25 %, a credit index of 250 or more, or a rising credit index; else `low`.
- `archetype`: `group` if the owner type is group; else `job_shop` if staff < 80 or cash pressure is
  high; else `family` if family-owned; else `trader` for raw material or a quote remark "supply from
  stock"; `monopolist` overrides when
  `capacity_tight` or `list_price_fixed` is signalled and the part has no alternative; else `other`.
- `citable`: only what the arena accepts (an `idx` pair is one series, at most 12 months apart,
  ending within the last 12 months of the data). Every entry is checked with `sellm/lab/claims.py`
  at build time: 0 `contradicted`. Facts that help the supplier (a rising index) stay in with
  `helps_buyer: false`, so A knows what the supplier may cite.

**Signal kinds** (`signals[].kind`, frozen vocabulary: add kinds, do not rename). Strength is
min(3, distinct pieces of evidence): one per text, one per structured condition; a news item found by
its topic and by its words counts once. Noise news and market news never count. Rules and patterns:
`sellm/intel/signals.py` (calibrated Sat 18:30 against all 46 suppliers' texts).

| Kind | Evidence in the data | What it means for us |
|---|---|---|
| `cash_short` | "Could you pay our invoices within 10 days?", liquidity, "the bank", skonto terms, quote remark "Payment within 10 days requested", news `credit_downgrade`, `credit_watch`, `short_time_work`. A low equity ratio is not evidence here; it raises `cash_pressure` to `medium` | trade faster payment for price; it values payment days at its high cost of money; do not squeeze its margin |
| `wants_volume` | "focus on customers with volume", idle shop floor, news `free_capacity`, "accepted below full cost to keep the volume" | a longer contract, full-need coverage or a bundle buys price |
| `capacity_tight` | news `allocation`, `full_order_book`, `big_order`, `chip_shortage` | secure volume and lead time first; price moves little |
| `list_price_fixed` | "head-office directive", "list conditions" in quote remarks; "no room on price this year: head office has frozen all price reductions" | do not fight the list price; move payment, start date, freight, chargeback |
| `material_hedged` | "material covered until ..." | index arguments are weak until then; ask for a later start or a fixed price |
| `partnership` | past favours and the reciprocity asked for ("kept supplying at the old price ... expects partnership in return"), "long-standing", "for generations". Read from the text, not the subject: "Visit by the owner" notes are often about something else, and the vendor-master date is 1996-01-01 for 36 of 46 suppliers | appreciation and reciprocity; never an ultimatum |
| `margin_floor` | "cannot sign anything that lowers our margin"; a part priced at or below its plant-specific should-cost (e.g. Wimbacher 310012 at 0.97) | the price is near its floor; trade terms, not price |
| `quality_problem` | latest scorecard amber or red, ppm above 1,500, an overdue 8D (each condition counts once), 8D/complaint/defect in its texts | lever for ppm commitment and chargeback; cite `sc` and `qn` |
| `delivery_problem` | latest on-time delivery below 75 % (9 of 46; below the 95 % target are 43 of 46, which says nothing); strength 2 below 65 %, 3 below 55 % | cite OTD; ask for a lead-time commitment |
| `ownership_change` | news `new_owner`, `succession`, `restructuring`, `refocus` | new decision makers, risk that it walks; be clear and fair |
| `approval_ladder` | owner type group or a group parent, "head office", "price changes above 2 % need the approval of their pricing committee" | expect a round on hold before a bigger move; be patient |
| `price_claim` | a letter with `asked_pct` and stated reasons; in the opening e-mail "<series> rose x % in twelve months and is y % of our cost" | check each stated cost driver against its index; cite the ones that fell |
| `informal_costing` (added Sat 18:30) | "works from his own spreadsheet, last updated two years ago", "had not followed his material and energy prices closely since the 2022 peak; his office manager does the costing" | the supplier does not track its own costs: one verified index figure can disarm it ("we didn't know that"); bring exactly one strong figure |

**The case overlay** (mini-dossier): at session open, before the first move, under 100 ms, no LLM.

- `identity` from the vendor master if the ID is known (also the about 400 suppliers known only by
  name, category and spend), else the name from the opening e-mail.
- `standard_terms` from the quote PDF (`arena_kit.docs.standard_terms`), overriding stored values.
- `signals` from the briefing, the trigger doc, the quote e-mail and PDF remarks, and any `doc:` or
  `news:` in the case's `facts`.
- `citable` from the case's `facts` (a dict keyed by ID like `facts.json`, as the Calculator already
  reads it; accept a list too) and its `refs`.
- `should_cost` and `floor_estimate` from a `cost:` fact of the case.
- `alternatives` from `buyer.alternative` and, in an RFQ, the other suppliers' offers (their
  `offer:` IDs are citable in the session).
- Merge: lists are united by ID; scalar values from the case win.
- `alternatives` entries from the case carry a `kind`: `buyer_alternative` (our alternative quote,
  marked on the existing entry if the quote is already listed), `current_contract`, `rfq_rival`
  (another bidder's opening offer with its `offer_id`). All are buyer-private.

**Checks**: every detailed supplier gets a dossier; two builds are byte-identical;
`dossier()` on an unknown supplier and on every case file in `sellm/lab/cases/` returns the schema
without raising (B's tests). 0 `contradicted` in `citable` and in every sentence `arguments()`
offers (C's tests).
