# CONTEXT - Tacto Negotiation Arena: everything we know

Condensed from `brief/brief.md`, `brief/api.md`, `brief/submission.md`, `KIT-README.md`,
`data/package/*.md`, the kit source and https://arena.tacto.ai/faq (snapshot Sat 2026-10-10 14:30 CEST).
**If this file disagrees with `brief/`, the brief wins** - fix this file and log it. The FAQ is
updated through the weekend: when you re-read it, add what changed here.

This file holds facts about the challenge. What we are doing right now is in `docs/STATUS.md`, what
we found out by playing is in `docs/LEARNINGS.md`, what happened when is in `docs/LOG.md`.

## 1. The challenge in one paragraph

We are team **sellm** in the Tacto track of the EHL Grand Finale 2026 (Garching). We build an **AI
buyer agent** for the fictional pump maker Hollerau Pumpenwerke. It negotiates by e-mail, over an
HTTP API, with Tacto's hosted **supplier bots** and closes the best total deal or walks away. We
practise against 10 hosted cases; on **Sunday 12:00** a Live Final on hidden cases ranks all teams
with no human in the loop. We bring our own LLM; Tacto runs the suppliers. Nothing is deployed: the
agent is a client that calls `https://arena.tacto.ai/v1`.

## 2. Clock (CEST, Europe/Berlin)

| When | What |
|---|---|
| Sat 10 Oct 10:00 | Kickoff; brief, data, kit and practice arena live |
| Sat evening | Tacto goes offline for the night (time announced on Discord) |
| **Sun 11 Oct 08:00** | **Sunday data release** (news, supplier letters, a memo). Run `uv run arena data` again. Hidden cases may cite it; the agent must read it |
| Sun 09:00 | Pre-flight: one practice case through the final setup, on the final machine and network |
| Sun 11:30 | Final checklist (section 12) |
| **Sun 12:00** | **Code and slides freeze, submit on ehl.gg.** Live Final starts: 5 waves, 8 minutes each. The agent must already be running and polling |
| Sun 13:00-14:30 | Top 10 pitch: 5 min + 2 min questions |
| Sun 14:30 / 15:30 / 16:30 | Track winners and finalists / Grand Final pitches / awards |

## 3. How we are ranked

- **Case score** = `clip((C_open - C_deal) / (C_open - C_best), 0, 1)`: the share of the possible
  saving we captured. `C` is the total cost in EUR of the accepted term sheet (section 5).
  - `C_open`: the cheapest opening quote that keeps the must-haves.
  - `C_best`: the cheaper of our alternative and the best package any supplier in the case would
    ever accept with every valid lever applied. Fixed per case and hidden until we have played it.
- **No deal** scores our alternative (0 if the case has none). Some cases are best left without a deal.
- **A broken must-have scores 0. A deal worse than the opening scores 0.**
- **Live Final:** wave score = mean of the wave's case scores x 100 (0-100, one decimal). Points =
  sum of the five waves, max 500. **Every case weighs the same**; EUR saved is a side number and
  does not rank. A case still open at the cap, or never opened, counts as no deal.
- Ties: more deals, then fewer rounds. Top 10 by points pitch to the jury.
- **Practice does not rank.** The practice board shows the mean of our best score per hosted case.
- Places 1-3: the weighting of final score against jury score, and the jury criteria, were still a
  placeholder in the brief (draft criteria: approach, explainability, craft). Ask at the Tacto desk.

Consequence: a robust agent that gets a decent deal on every case beats one that is brilliant on a
few and times out, breaks a must-have or closes worse than the opening on others.

## 4. How a negotiation works

1. `POST /v1/sessions {"case_id"}`: every supplier sends its **quote e-mail with a quote PDF** at
   once (round 0). The 60-second clock starts **per thread**.
2. We send an e-mail to one supplier's thread: subject, body, **0-3 term sheets**, data IDs,
   optional attachments. The supplier's reply is a message with its **standing term sheet** and a status.
3. We close by **accepting a supplier's standing term sheet** (`term_sheet_id`), or we walk away.
   Only we can close. In RFQ cases 2-3 suppliers run in parallel threads; accepting one ends the case.

Supplier statuses: `open`; `final_offer` (its last word: push further and it may walk); `agreed`
(it offers exactly our terms - **we still have to accept**); `walked_away`; `no_bid`.

Limits:

- **Round limit**: 10 of our messages per thread by default (`round_limit` in the case file). At the
  limit we may still accept.
- **60 seconds per message, per thread**, counted from the supplier's reply. A late message is a
  timeout: our last offer is repeated and the supplier's patience drops. Three timeouts in a row,
  or one after the last round, end the thread.
- A supplier's reply can take **up to about a minute**; that time never counts against our 60 s.
  Use an HTTP timeout of at least 180 s.
- Per key: **10 calls per second, 10 open sessions**. Request body at most 64 KB.

What counts:

- **Only term sheets bind.** They are taken exactly as sent, never guessed from prose. A term sheet
  must carry **exactly** the case's `negotiable` fields, each (except `unit_price`) with a value
  from `term_options`. Anything else is a `422` (nothing happens, no round is used).
- **Unstated terms close on the supplier's standard terms**, listed in its quote PDF and reported
  as `missing_fields`. Read the quote PDF before accepting.
- **Cited data is checked** (section 7). An unknown ID or a wrong figure is `contradicted` and costs trust.
- **What we write is understood and has consequences**: questions, arguments, urgency, a budget, a
  missing alternative, threats, appreciation, tone, manipulation attempts. Padding does not buy price.
- A supplier remembers only within a case. Its history with Hollerau is in the data.

## 5. The cost function C

`arena_kit.total_cost(case, terms, standard, supplier)` computes it; `arena_kit.cost.cost_breakdown`
gives the parts. With `N` need_per_year, `H` horizon_years, `V` volume_per_year, `M` contract_months,
`P` unit_price, `r` interest_rate, `d_ref` reference_payment_days:

```
years     = min(M / 12, H); a single order (M = 0) counts as 1
committed = V * years                      bought, needed or not
covered   = min(V, N) * years
pre       = units bought between the horizon start and effective_date (at current_unit_price)
new       = (committed - pre) * P
spend     = pre * current_unit_price + new
uncovered = (N * H - covered) * fallback_unit_price
C = spend
  + uncovered * (1 + fallback_risk_pct / 100)
  + spend * r * (d_ref - payment_days) / 360
  + committed * freight_eur_per_unit[incoterm]
  + late_cost_per_day * max(0, lead_time_days - need_lead_time_days)
  + committed * ppm_commitment / 1e6 * (cost_per_defect - min(chargeback_eur_per_complaint, cost_per_defect))
  + tooling_eur
  + new * material_share * max(0, |index_path| - deadband_pct / 100) * sign(index_path)   index clause
  + new * material_share * index_risk_pct / 100                                            index clause
  + relationship_eur_per_point * soft(sustainable_margin_pct - supplier_margin_pct) * years
soft(g) = 0 for g <= 0;  g^2 / 10 for 0 < g <= 5;  g - 2.5 for g > 5
```

The horizon starts at the fixed or earliest `effective_date` option. `index_path` is the case's
expected move of the clause's series (`buyer.index_paths`).

What follows from the formula (derived, not from the brief):

- **`effective_date`**: every month the new price starts later is bought at the old price.
- **`payment_days`**: each day beyond `d_ref` earns `spend * r / 360`; each day earlier costs it.
- **Coverage**: a contract shorter than the horizon, or volume below the need, leaves need
  uncovered at the fallback price plus risk. This can turn a good price into score 0 (brief example:
  EUR 41.60 for 12 of 24 months scores 0). Volume above the need is paid for and not used.
- **`incoterm`**: DAP usually has freight 0; EXW and FCA cost per unit.
- **`lead_time_days`** beyond the need costs a flat amount per day.
- **`ppm_commitment` and `chargeback`**: lower ppm and higher chargeback cut the quality cost.
- **Index clause**: earns when the index path falls, costs when it rises, and always costs the
  index risk premium. With an empty `index_paths` a clause only costs the premium.
- **Relationship term** (`stabilise` and `secure_supply` cases only): squeezing the supplier below
  its sustainable margin costs us. Its margin is `(value - full_cost) / value * 100`, where `value`
  is what the deal is worth to it in cash per unit at its own standard terms: price, payment
  timing at **its** cost of money, tooling up front, the freight leg it carries, chargebacks at its
  real defect rate. Contract length and an index clause are security, not cash, and do not count.
  So **a cash-short supplier that trades a lower price for faster payment is not squeezed**. We do
  not know its cost: estimate it from `should_cost`, its quotes and its cost breakdown.

Category goals set the rates: `stabilise` (strategic), `secure_supply` (bottleneck),
`quality_first`, `leverage`, `routine`.

## 6. How suppliers decide

Each supplier is a company with its own economics and a team of roles: the sales rep or owner who
writes, a boss who must approve bigger moves, and engineering, quality, logistics, finance or legal,
who answer their topics and attach documents. Examples named in the brief: a family foundry that
remembers how it was treated, a group with an approval ladder, a job shop that needs cash and work,
a near-monopolist that barely moves.

- Hard limits: it **never sells below its cost floor**, bigger moves need the boss's approval, and
  it **gives nothing without a move from us**.
- Inside those limits it decides as that person would, reading the whole e-mail. It reacts to tone
  and relationship. Identical messages need not get identical replies.
- **Verified is not the same as convincing.** True data may disarm it ("we didn't know that"), move
  it a little, or meet "that's not our reality" because something else weighs more for it right now.
  What weighs more is in its call notes, letters, news and quote remarks. Some notes are noise.
- **Find the trade it wants**: a cash-short supplier may care more about when it is paid than about
  price; one that cannot touch its list price may move on other terms.
- Questions go to the person in charge, who answers as openly as the company is. Cheaper
  engineering variants a supplier mentions are information, not binding terms.
- Sending two or three term sheets shows what a supplier values.
- **Never leak** urgency, a budget or a missing alternative. Do not take the first offer.

Documents are rendered from the supplier's data, never written by an LLM:

| Document | When | Why it matters |
|---|---|---|
| Quote PDF | opening e-mail; with `final_offer` and `agreed` | offered terms, **standard terms**, terms fixed by our enquiry, validity |
| Cost breakdown XLSX | we ask and the supplier is open enough | cost elements in EUR per unit and their share |
| 8D report PDF | quality topics | scorecards, 8D steps, a ppm commitment |
| Delivery schedule XLSX | delivery and capacity topics | monthly quantities, lead time |
| Order confirmation PDF | at the deal | the agreed terms |

The recorded P01 negotiation on the FAQ page scored 0.76 with this pattern: open with appreciation
for past fairness, one verified index argument, an offer to pay faster, two term sheets; answer
"which figures?" with the should-cost estimate (`cost:310010`) and "we want you to earn a fair
margin". The FAQ adds: the same index sent as an ultimatum ("unacceptable ... or we go elsewhere")
got EUR 136.50 from November instead of January, about EUR 13,700 a year worse.

## 7. Citing data

Cite the ID (in the body or in `refs`, at most 20) **and write our figure in the same sentence**.
The arena checks it against `facts.json` and reports `claim_results`, **at most 3 per message**, so
write one argument per sentence. Without a figure the data's own value is taken.

| We cite | Checked | Our figure |
|---|---|---|
| 2 x `idx`, one series, at most 12 months apart, ending within the last 12 months of the data | the change `(later / earlier - 1) * 100` | a % |
| a `quote` of this case (in its `refs` or our alternative), or another supplier's `offer` in this session | its price, same part | EUR |
| `sc` rows (quality also `qn`) | mean on-time delivery, or mean ppm when we speak of quality | % / ppm |
| 2-8 x `po`, same part | the order prices | - |
| `fc` / `cost` / `news` | the recorded change / the estimate / that it is about this supplier | % / EUR / - |
| a letter `doc` giving notice + the contract `ctr` | the notice the letter gives against the contract's | days |

- Tolerance: +-0.5 percentage points for %, else +-0.5 % (at least 0.01).
- Results: `verified`; `irrelevant` (true but not about this supplier or part, or an index window
  too long or too old); `contradicted` (unknown ID or wrong figure: **costs trust**); `duplicate`
  (each ID counts once per case).
- A rival's quote may be cited to every other bidder in an RFQ and counts once per supplier. Citing
  it **reveals** that buyer-private fact to the supplier.
- Order lines of different parts are separate arguments. IDs of notes, suppliers or parts are
  context, not checks. Offers made in the session are citable as `offer:` IDs.

Data ID fields in `facts.json`: `idx:<series>@YYYY-MM` (series, month, value); `quote:` (part,
supplier, unit_price, other terms); `sc:<supplier>@YYYYQn` (otd_pct, ppm); `qn:` (supplier, part,
ppm); `po:` (supplier, part, unit_price); `cost:<part>` (unit_cost); `fc:<part>@YYYY-MM`
(change_pct); `news:` (supplier or null); `doc:` (supplier, date, days, asked_price); `ctr:`
(supplier, days).

## 8. API cheat sheet

Base `https://arena.tacto.ai/v1`. Header `X-API-Key` on everything except `/v1/data`, `/health` and
the boards. Send a fresh `X-Move-Id` with every `POST`; repeating a request with the same id
returns the earlier answer instead of acting twice. `arena_kit.ArenaClient` does all of this.

```
GET  /health                                         is the arena up
GET  /v1/data                                        downloads: package, release-sunday
GET  /v1/me                                          quota used/left/resets_at, best score per case
GET  /v1/cases?set=practice|sandbox|final            full case files
POST /v1/sessions {"case_id"}                        open a case: session_id, case, threads, opening
POST /v1/sessions/{sid}/threads/{supplier}/messages  {"message": {...}} -> the reply, or the result
GET  /v1/sessions/{sid}/threads/{supplier}           the whole thread (resume after a crash)
GET  /v1/sessions/{sid}/attachments/{attachment_id}  a supplier document
GET  /v1/sessions/{sid}                              state; after the end result, trace, replay_url
GET  /v1/sessions/{sid}/backoffice                   the supplier's internal talk (after the end)
GET  /v1/sessions?set=practice                       our sessions: case, status, deal, score, rounds
GET  /replay/{sid}                                   the replay page: every e-mail, the supplier's reasons
```

The back office is thin (seen on P01 and D01): one line per step such as "My call: counter." or
"The buyer asks something for Quality Manager". The supplier's reasons are in the `trace` of
`GET /v1/sessions/{sid}`, not there. `GET /v1/sessions?set=practice|sandbox` lists every session
of the team, whoever played it, so all runs can be pulled into the repo.

Structured path for agents that skip prose: `POST /v1/sessions/{sid}/moves`, `.../accept`,
`.../walk_away`. Same supplier, same rules.

Our message: `subject` (<= 300 chars), `body` (plain text, <= 8,000 chars), `term_sheets` (0-3 x
`{"terms": {...}}`), `refs`, `attachments` (<= 5; md, csv and json are read), `action` (`null`,
`{"type": "accept", "term_sheet_id"}` or `{"type": "walk_away"}`). A message without a term sheet
is fine (a question) and the quote stands.

The reply: `from` (`<role>@<supplier>`), `body`, `status`, `term_sheets` (its standing offer with
`term_sheet_id`), `missing_fields`, `claim_results` (`{"index", "result"}`), `signals`
(`reply_delay_days`, `validity_days`), `attachments`.

Term fields: `unit_price` (EUR, 2 decimals, per the part's `price_unit`), `payment_days` (0-120),
`lead_time_days`, `volume_per_year`, `contract_months` (0-36; 0 = single order), `effective_date`,
`index_clause` (`null` or `{series, material_share, deadband_pct, base_month}`), `incoterm`
(`EXW`/`FCA`/`DAP`), `tooling_eur`, `ppm_commitment`, `chargeback_eur_per_complaint`.

Case file: `case_id`, `set`, `type` (`price_increase`, `renewal`, `rfq`, `bundling`,
`raw_material`, `capacity`, `quality`), `title`, `briefing`, `trigger_doc`, `parts`, `suppliers`,
`negotiable`, `fixed_terms`, `term_options`, `round_limit`, `refs` (a start, not the whole story),
`facts` (hidden cases only: facts that exist only in this case, citable there) and `buyer`:
`need_per_year`, `horizon_years`, `current_unit_price`, `fallback_unit_price`, `interest_rate`,
`reference_payment_days`, `need_lead_time_days`, `late_cost_per_day`, `cost_per_defect`,
`category_goal`, `fallback_risk_pct`, `index_risk_pct`, `sustainable_margin_pct`,
`relationship_eur_per_point`, `freight_eur_per_unit`, `index_paths`, `must_haves`
(`[{field, op, value}]`), `alternative` (`{kind: none | quote | current_contract, ref, terms}`).

Result: `deal`, `must_haves_ok`, `supplier_id`, `offer_id`, `terms`, `c_open`, `c_deal`, `c_alt`,
`c_best`, `score`, `cost_breakdown` (price, uncovered_need, fallback_risk, payment_terms, freight,
late_delivery, quality, tooling, index_clause, index_risk, relationship), and after the end `trace`
(`{round, actor, move, reasons}`; hidden figures shown as `...`).

Errors: `401` bad key · `403` paused key, non-hosted practice case, final list before wave 1, back
office before the end · `404` unknown case/session/thread/attachment (also a final case whose wave
has not started) · `409` thread or session ended, round limit reached, late message (timeout),
final case already played · `413` body over 64 KB · `422` invalid message, nothing happens ·
`429` calls per second (`Retry-After: 1`, retry), open sessions (close one), practice quota
(`practice limit: ...`, **retrying does not help**).

## 9. Practice, sandbox, simulator

| Where | Cost | What it is for |
|---|---|---|
| Offline `total_cost` | free | score any term sheet once a case's `C_open` and `C_best` are known |
| `arena-sim` (`uv run arena-sim serve --no-clock --data data/package`) | free, no key, no clock | plumbing only. Its supplier is a plain script and **not** how real suppliers behave. Cases `S01`-`S03` |
| Sandbox `case:D01`, `case:D02` on arena.tacto.ai | **free, outside the quota** | real supplier behaviour on 3 demo suppliers; replay right after; no board |
| Practice, 10 hosted cases | **quota** | the real learning loop: score, cost breakdown, replay with the supplier's reasons |

**Quota: 200 practice sessions per team per rolling 24 hours, shared by every teammate and
agent.** Our first session ran Sat 14:13, so nothing frees up before Sun 14:13, after the final:
**treat what `uv run arena me` shows as the total budget until the final.**

### Testing without spending quota (verified Sat 14:49)

Sandbox `D01` was played with `uv run arena me` before and after: `used 1 / left 199` both times.
The sandbox does not touch the practice quota. Which free option to use for what:

| You want to test | Use | Not this |
|---|---|---|
| Whether a term sheet is good, what a price/date/payment trade is worth | offline `total_cost` / `cost_breakdown` (needs the case file and the supplier's standard terms; `C_open` and `C_best` for the score) | any session |
| Plumbing: message format, timeouts, resume after a crash, the runner, parallelism | `arena-sim` (local, no key, no clock, no quota) | the sandbox, it adds nothing here |
| **Agent behaviour against real supplier bots**: arguments, tone, term-sheet strategy, LLM prompts | **sandbox `D01`, `D02`** (free, replay after each run, result shows `C_open`, `C_best` and the breakdown) | `arena-sim`: its supplier is a script that concedes a fixed 2 % per sheet and only checks that cited IDs exist, so a strategy that wins there says nothing |
| Behaviour on the real case types (renewal, capacity, quality, raw material, bundling) | practice case, costs one session | the sandbox: it only has a price increase and an RFQ |

Limits of the sandbox: two cases, demo suppliers (`DEMO-F1`, `DEMO-J1`, `DEMO-C1`), no board, and
no `facts` of the real data package for them. A good sandbox score does not prove a good practice
score. Use it to iterate cheaply, then confirm on one practice case.

Unlimited local testing against realistic suppliers would need our own supplier simulator built
from the public data (Tacto suggests it). It would only be as good as our model of the suppliers.

### LLM provider

The kit's `llm_from_env()` supports `LLM_PROVIDER=anthropic` and `LLM_PROVIDER=openai`. The team
uses OpenAI: `LLM_PROVIDER=openai`, `LLM_MODEL`, `LLM_API_KEY` (and `LLM_BASE_URL` only for a
non-OpenAI endpoint). `LLM_EFFORT` and `ANTHROPIC_API_KEY` apply to Anthropic only.

**Trap: a failing LLM call is silent.** `LLMAgent.decide` catches every exception and plays the
naive move instead (it logs a warning, visible only with `-v`). A wrong model name, a bad key or a
timeout (45 s per call in the kit) therefore looks like a working LLM run that negotiates badly.
When you test an LLM agent, run with `-v` and check there is no `LLM failed` line before you
trust the score.

Hosted practice cases (all `round_limit` 10):

| Case | Type | Goal | Supplier | Negotiable | Alternative | H | Must-have |
|---|---|---|---|---|---|---|---|
| P01 | price_increase | stabilise | 70110 Gießerei Brandlhuber, +9.5 % on HN volute casings | unit_price, effective_date, payment_days | quote | 1 | - |
| P02 | price_increase | stabilise | 70510 Nordmark, copper for the 7.5 kW motor | unit_price, payment_days, index_clause | quote | 1 | - |
| P03 | renewal | stabilise | 70530, 7.5 kW frequency converter | unit_price, payment_days, contract_months, volume_per_year | quote | 2 | - |
| P04 | renewal | routine | 70620, ball bearing 6306 | unit_price, payment_days, contract_months | quote | 2 | - |
| P05 | rfq | leverage | 70210, 70240, 70250, pump shaft HX | unit_price, payment_days, lead_time_days | none | 2 | lead_time_days <= 42 |
| P07 | bundling | routine | 70610, fastener kit | unit_price, payment_days, contract_months | current_contract | 2 | - |
| P08 | raw_material | leverage | 70710, 1.4404 bar | unit_price, index_clause, payment_days, contract_months | quote | 2 | - |
| P10 | capacity | secure_supply | 70410 Ravensteiner, seal allocation | unit_price, volume_per_year, contract_months, lead_time_days | none | 2 | volume_per_year >= 22230 |
| P11 | quality | quality_first | 70140 Kalwisz, bearing brackets | ppm_commitment, chargeback_eur_per_complaint, unit_price | quote | 1 | ppm_commitment <= 1500 |
| P18 | raw_material | leverage | 70740 Werdenfels, 1.4404 bar | unit_price, index_clause, payment_days, contract_months | quote | 2 | - |

Sandbox: `D01` price_increase, stabilise, DEMO-F1, no alternative. `D02` rfq, leverage, DEMO-J1 and
DEMO-C1, lead_time_days <= 42. Case files to study but not play: P06, P09, P12-P17, P19.

## 10. The Live Final

- Hidden cases in **5 themed waves**. Before a wave starts the API names nothing: `GET
  /v1/cases?set=final` is `403` until wave 1. Once started, the list holds every started wave's
  cases with `wave`, `theme`, `open` and `seconds_left`.
- A wave's cases appear at its start for all teams. **Hard cap 8 minutes per wave** (the host may
  extend one: read `seconds_left`, do not assume). **One attempt per case**; a second `POST
  /v1/sessions` is a `409` naming the running session, which can be resumed.
- **At the cap every open session ends without a deal** (`end_reason: wave_cap`).
- Play all of a wave's cases **in parallel** (up to 10 open sessions per key).
- Hidden cases share the world, case types and rules of practice, with new suppliers and settings.
  **Up to a third combine supplier types and case types that practice never shows.** Some cite the
  Sunday release. An agent that memorised the practice suppliers will meet strangers.
- A case broken on Tacto's side is replayed.
- Replays and back office of final sessions appear after the final and are open to the jury.

Kit runner: `uv run arena run --set final --agent llm --parallel 10`. It polls the case list, plays
each new wave in parallel, closes each case 90 s before the cap with `play.closing_move` (cheapest
standing sheet that keeps the must-haves and beats the alternative, else walk away), stops after
the fifth wave and resumes its sessions after a crash. Tacto's advice: a cloud VM is safer than a
laptop on venue Wi-Fi.

## 11. Rules that can disqualify us

1. **No human in the loop** during the Live Final.
2. **The agent must not read the live feed during the Live Final**: `/v1/events`,
   `/v1/events/stream`, `/screen`, `/v1/screen`, `/leaderboard`, `/v1/leaderboard`, `/results`,
   `/v1/results`. They are for people. Do not build any code path that calls them from the agent.
3. **One API key per team.** No attacks on the service or on other teams.
4. **Code freeze Sun 12:00.** The final runs the submitted commit; the top 10 are checked for later pushes.
5. Everything else counts, including weaknesses found in the supplier bots. Every replay is open
   to the jury, who may weigh how a score came about.
6. No key in the repo: no `.env`, no LLM key, no arena key.

## 12. Submission and pitch (ehl.gg, Sun 12:00)

- **The repo** with the agent and a README that says how to run it (setup, environment variables
  without values, the command) and the **commit hash** the agent runs in the final. The jury and
  tum.ai must be able to open the repo; tum.ai runs a code agent over every submission.
- **A short description**: how the agent prepares, what it reads in the data, how it decides what
  to offer, when it closes or walks away.
- **Slides.** 5 min pitch + 2 min questions, strictly timed. Pick one negotiation and walk through
  its replay. Expect: Why did your agent write that? Would it have worked on a real supplier? What
  did your agent learn about suppliers, and from where?

11:30 checklist: final machine and network, and one practice case went through it at 09:00 ·
`uv run arena data` ran after 08:00 · `uv run arena me` answers · LLM credits and rate limits for
about an hour of parallel play · the runner is started and logs to a file · the laptop is on power
and does not sleep.

## 13. The data package (`data/package`, as of 2026-09-30)

Not in git: `uv run arena data` unpacks it. `world.sqlite` holds every table; `facts.json` every
citable ID with the values the arena checks; `contracts/` and `correspondence/` hold the texts.
Start with `data/package/README.md` and `company.md`.

| Table | Rows | Content |
|---|---|---|
| `suppliers` / `supplier_intel` | 447 / 46 | vendor master / register facts, turnover, credit index, audit of the 46 detailed suppliers |
| `parts` / `sourcing` | 60 / 90 | material master / approved suppliers per part, quota, tooling owner |
| `price_conditions` / `negotiation_history` | 339 / 300 | price history with the event behind it / past renewals with asked and settled change |
| `contracts` / `contract_clauses` | 46 / 280 | framework agreements / clauses incl. index clauses (`ctr:<no>#<clause>`) |
| `po_lines` / `goods_receipts` / `invoices` | 5400 / 5580 / 5578 | orders / receipts / invoices with due and paid dates |
| `quality_notifications` / `scorecards` | 1033 / 414 | complaints with 8D dates / rolling 12-month OTD, ppm, colour per quarter |
| `forecasts` / `forecast_lines` | 720 / 8640 | demand forecasts shared with suppliers |
| `rfqs` / `quotes` | 47 / 108 | past benchmarks, second-source quotes, open RFQs |
| `spend_cube` | 1137 | spend per fiscal year and supplier |
| `index_series` / `index_values` | 33 / 2258 | real public market series, monthly |
| `cost_drivers` / `should_cost` | 166 / 28 | index series and weight per part / bottom-up full cost without margin (`cost:<part>`) |
| `news` / `documents` | 39 / 208 | press items / letters, e-mails, meeting and call notes |

Company facts: Hollerau Pumpenwerke GmbH, family-owned, about EUR 252 M revenue, fiscal year
October-September, "today" is 2026-09-30. Standard payment 60 days net, cost of capital 8 %.
Quality agreement: OTD target 95 %, EUR 150 flat fee per supplier-caused complaint, 8D within 60
days. Preferred Incoterm DAP Hollerau. FY2027 target: material cost -3 % against the index-adjusted
baseline; no supplier red for more than two quarters. Scorecard classes: A green >= 85, B amber
70-84.9, C red < 70.

Category strategies: castings `stabilise` · machined parts `leverage` · sheet metal `leverage`
(quality first after the 2026 base-frame issues) · seals `secure_supply` · electrical `stabilise` ·
C-parts `routine` · raw material `leverage`. Quality escalations are `quality_first`, capacity
squeezes `secure_supply`, kits and bundles `routine`.

Should-cost: for strategic and bottleneck parts the estimate models the current supplier's own
plant (error about 5 %); other rows use a German cost base (error 5-15 %). Full cost relative to
Germany: AT and CH 1.0-1.1, CZ/PL/HU 0.8-0.85, TR 0.75, CN 0.7.

Coverage (checked Sat 15:15): the 19 practice cases use 22 of the 46 detailed suppliers. The
other 24 have about four documents each (e-mails, meeting notes, call notes, letters) and are the
likely pool for the hidden cases. `negotiation_history` has, per supplier and part, past price
events with asked and settled change and a note, e.g. "accepted below full cost to keep the
volume". `supplier_intel` has owner type, group parent, staff, turnover, equity ratio and credit
index now and 12 months ago; `suppliers` has standard payment days and cash discount terms.

Data quirks that are not errors (`data/package/KNOWN_ISSUES.md`): prices are per `price_unit` (1,
100 or 1,000); `sup:71999` is the old record of `sup:70210`; some PO lines carry a stale price;
index series end at different months; ppm on small lots is jumpy (use the rolling scorecard);
invoices are paid late for some suppliers; OTD differs by 10-30 points depending on the reference date.

## 14. The starter kit (`arena_kit/`)

| Module | What |
|---|---|
| `client.py` | `ArenaClient`: one method per endpoint, paced at 9 calls/s, retries with the same `X-Move-Id`, 180 s timeout, `practice_remaining` |
| `play.py` | `play()`, `play_all()`, `play_waves()` (the final), `RemoteTable`, helpers `latest`, `standing`, `live_threads`, `moves_left`, `closing_move` |
| `cost.py` | `total_cost`, `cost_breakdown`, `supplier_value`, `relationship_cost`, `must_haves_ok`, `complete_offer`, `snap`, `score` |
| `docs.py` | attachments to text (PDF, XLSX); `quote_terms`, `standard_terms` from a quote PDF |
| `data.py` | `DataPackage`: `query` (read-only SQL), `lookup(id)`, `ids(prefix)`, `document(ref)`; merges the Sunday release automatically |
| `agents/naive.py` | anchors 10 % low, splits the difference, accepts early. Price only |
| `agents/llm.py` | one LLM call per move: the model writes the e-mail and term sheets; code computes C, reads documents, drops unknown IDs, refuses bad accepts, falls back to naive on any LLM error |
| `sim.py` | `arena-sim`, the API on localhost with a scripted supplier |
| `mcp_server.py` | read-only MCP server over the data: `list_tables`, `query`, `lookup`, `list_ids`, `read_document`, `get_case` |

An agent is any object with `decide(case, threads) -> {"supplier_id", "message"}`. `threads` is
`{supplier_id: [message, ...]}`, oldest first; supplier attachments carry their text under `"text"`.

Commands (run from the repo root):

```bash
uv sync --all-extras                        # install
uv run arena data                           # unpack data/package (and release-sunday once public)
uv run arena me                             # quota and best scores (free)
uv run arena cases [--set sandbox]          # list cases (free)
uv run arena play case:D01 -v               # sandbox: free, real supplier behaviour
uv run arena play case:P01 --agent llm -v   # one practice session (quota)
uv run arena run --set practice --agent llm --parallel 8   # all 10 hosted cases (10 sessions)
uv run arena run --set final --agent llm --parallel 10     # the Live Final runner
uv run arena mcp                            # MCP server over the data (stdio)
uv run pytest                               # the kit's contract tests against arena-sim
uv run ruff check .                         # lint
```

`.env` (never committed): `ARENA_URL`, `ARENA_API_KEY`, `ARENA_DATA=data/package`, `LLM_PROVIDER`
(`anthropic` or `openai` for any OpenAI-compatible endpoint), `LLM_MODEL`, `LLM_EFFORT`,
`ANTHROPIC_API_KEY` or `LLM_BASE_URL` + `LLM_API_KEY`.

Known limits of the kit agents (read from the code):

- The LLM agent sees only what the case's `refs` point to. It does not mine the data package, the
  supplier's notes, letters, news or history. Tacto says so: "a starting point, not a winner".
- Neither agent passes a supplier estimate to `total_cost`, so the **relationship term is missing
  from the C they optimise** in `stabilise` and `secure_supply` cases (P01, P02, P03, P10).
- `play()` handles one thread at a time and waits for each reply. In RFQ cases the other threads'
  60-second clocks keep running meanwhile. Verify the effect in sandbox `D02` before relying on it.
- The `--agent` choices `naive|llm` are hard-coded in `cli.py`.
- The LLM call has a 45 s timeout; any failure silently plays the naive move.

## 15. Tacto's own tips

- **Numbers come from code, the model writes.** Compute C for every term sheet; put figures next to
  their IDs; let the LLM choose arguments and wording.
- **Read the supplier before arguing**: notes, letters, news, quote remarks.
- **Prepare once, reuse**: the data changes once (Sunday 08:00). Build a dossier per supplier,
  cache it, reuse it in every run. Do heavy research before opening a session, because of the 60 s.
- **Mix models**: a strong model for the plan of a case, a small fast one for the writing.
- Threads are short: at most 10 of our messages per supplier.
- For a local opponent, build our own supplier simulator from the public data.
- **Rehearse the final**: all hosted cases in parallel, from Sunday's machine and network, well
  inside 8 minutes.
- Old replays: `GET /v1/sessions?set=practice`, then `/replay/<session_id>`.

## 16. Links

Kit repo https://github.com/tacto-ai/negotiation-arena-kit · arena https://arena.tacto.ai · FAQ
https://arena.tacto.ai/faq · build page https://arena.tacto.ai/live · results
https://arena.tacto.ai/results · Discord https://discord.gg/hPwFfbWRV · our repo
https://github.com/Amiad2/taco-sellm
