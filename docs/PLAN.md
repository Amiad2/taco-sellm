# PLAN - how three people get the best agent running by Sunday 12:00

Status: **proposed Sat 15:20 by Jonathan (with Claude Code), not yet agreed by the team.** Owners
are open: claim a workstream in `docs/STATUS.md`. Change this file when the team changes the plan,
and log the change as a `[decision]`.

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
files. Proposed location: a new package `sellm/` next to `arena_kit/` (the kit stays untouched
except for registering our agent in `cli.py`; add `sellm` to the wheel packages in `pyproject.toml`).

| Part | Does | Interface |
|---|---|---|
| **Calculator** `sellm/calc.py` | For a case and a standing offer: enumerate term sheets over `term_options`, price each with `total_cost`, say what each lever is worth to us, guard must-haves and coverage, set a target and a walk-away value, estimate the supplier's margin for the relationship term | `plan(case, threads, dossier) -> {sheets ranked by C, lever values, target, floor estimate, walk_away}` |
| **Intel** `sellm/intel.py`, `sellm/claims.py` | Built once for **all 46 detailed suppliers**, cached as files: who they are (family firm, group, job shop, monopolist), cash position, capacity, quality record, how past negotiations ended, what their notes and letters say they care about. Plus an argument bank per supplier and part with figures computed in code and checked against `facts.json` | `dossier(supplier_id, part_ids) -> text + fields`; `arguments(case, supplier_id) -> [{sentence, ids}]` |
| **Negotiator** `sellm/agent.py` | The round plan and the e-mail. Code decides the term sheets and which arguments are allowed; the LLM chooses among them and writes. Falls back to the calculator's move, never to the naive agent | `decide(case, threads) -> {supplier_id, message}` |
| **Runner and measurement** `sellm/runner.py`, `scripts/pull-runs` | All threads of an RFQ in parallel, a round budget from the time left in the wave, logs to a file, resumes after a crash. Saves every session of the team (transcript, trace, breakdown) to `runs/` so nobody replays a case to see what happened | `uv run arena run ... --agent sellm` |

## 3. Workstreams (one per person, each with its own agent sessions)

**A - Numbers and strategy** (calculator + negotiator). First deliverable: `plan()` reproduces the
P01 and D01 tables in `docs/LEARNINGS.md` and proposes the first two term sheets for every hosted
case. Then the round policy: open with a question and two or three sheets that probe what the
supplier values, trade one lever per round, never accept before the target unless the status is
`final_offer`, close on the best standing sheet when time or rounds run out.

**B - Data and arguments** (intel + claims). First deliverable: dossiers for the 22 practice
suppliers, checked by hand against two replays; then all 46. The 24 detailed suppliers that appear
in no practice case have about four documents each and are the likely pool for the hidden cases.
`negotiation_history` carries notes such as "accepted below full cost to keep the volume"
(Brandlhuber, the P01 part). Sunday 08:00: rebuild with the new release, it must be one command.

**C - Arena, measurement, final** (runner + runs + submission). First deliverable: the baseline
below and `scripts/pull-runs`. Then: RFQ threads in parallel, the 8-minute budget, the final
machine, the rehearsal, the README run instructions, the approach text and the slides.

Integration points: A needs B's dossier format by Sat 17:00 (agree the fields first, fill them
later). C runs every new agent version and reports per case what the cost breakdown says we lost.

## 4. Timeline (CEST)

| When | Milestone |
|---|---|
| Sat 15:30 | **Baseline**: kit LLM agent on all 10 hosted cases and on D02. We then know `C_open` and `C_best` of every case and can score any term sheet offline |
| Sat 17:00 | Interfaces agreed; `runs/` in the repo; lever table for all 10 cases |
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

## 8. Not doing

- No supplier simulator of our own: too much work for what it would prove before Sunday.
- No tuning on a single practice case until it scores 1.0: the final cases are different ones.
- No changes to `arena_kit/` beyond registering our agent, so upstream fixes stay easy to take.
