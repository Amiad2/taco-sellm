# The lab: test buyer strategies without spending practice quota

A local copy of the arena with simulated suppliers. Any agent with `decide(case, threads)` plays
against it exactly as against the arena (the kit's `RemoteTable` interface), for free, a few hundred
negotiations per second on a laptop. No arena calls, no LLM calls unless you choose the `llm` agent.

**What it is good for:** ranking strategy variants by their mean over many scenarios; finding the
mistakes that cost points in the final (crashes, refused moves, broken must-haves, deals worse than
the opening, timeouts in RFQs, running out of time). **What it is not:** a prediction of one case's
score. A lab winner is a hypothesis until the sandbox (`case:D01`, `case:D02`, free) or one practice
case confirms it.

## The UI

`scripts/lab ui` opens a local page (http://127.0.0.1:8765, nobody else can reach it):

- **Start**: search, compare or stress with every option as a form field; knobs as JSON or a table,
  or loaded from any earlier run's `best.json` (rank N). Runs go to the background and keep going
  when the UI is closed.
- **Runs**: every run with live progress and the rendered report; stop a running one; **extend**
  (refills the form with more minutes, seeds and scenarios); **use #1 knobs** for a compare;
  **stress-test #1**; **#1 as sellm/agent.py KNOBS** (a block to paste into `sellm/agent.py`); export
  `report.md`, `best.json`, `rows.csv` (one row per negotiation, for a spreadsheet) or the whole run as a zip.
- **Play one**: any twin or generated scenario with any agent and knobs, the full transcript.

## Quick start

```bash
scripts/lab play P01                  # one negotiation against the P01 twin, every e-mail printed
scripts/lab play X01-007 naive        # a generated scenario, the kit's naive agent
scripts/lab compare naive calc        # agents side by side (background, ~1 min)
scripts/lab search 60                 # a 60-minute search for the best Calculator knobs (background)
scripts/lab stress calc               # stress test: everything the final may bring (background)
scripts/lab status                    # what is running, newest progress, where the report is
scripts/lab stop                      # stop a run
```

Every run writes `runs/lab/<time>-<command>[-label]/`: `report.md` (read this), `best.json` (the ten
best variants with their knobs), `progress.log` (live). Raw rows and scenarios are git-ignored.
Commit `report.md` and `best.json` of runs that matter and log them as `[run]` (AGENTS.md).

Use a result: `--knobs runs/lab/<run>/best.json` (rank 1) or `...best.json#3` (rank 3), e.g.
`scripts/lab stress calc --knobs runs/lab/<run>/best.json`. Your own agent: `--agent module:Class`
(constructed with the data package if it takes one), e.g. `scripts/lab compare calc sellm.agent:SellmAgent`.

## Options (all commands that play)

| Option | Default | Meaning |
|---|---|---|
| `--mode parallel\|sequential` | parallel | one loop per thread (what our final runner must do) / the kit's `play()` (one thread at a time; RFQ threads time out) |
| `--no-clock` | off | no simulated time: no timeouts, no wave cap |
| `--wave-cap S` | 480 | seconds per case, as a Live Final wave; the runner closes 90 s before it with the kit's `closing_move` |
| `--think S` | 2.0 | our seconds per move; `-1` = the real time the agent took (use for LLM agents) |
| `--fixed-twins` | off | the fitted twins only; by default each run draws a member of each twin's family |
| `--invented N`, `--test N` | 160, 80 | generated scenarios for training and for the unseen test |
| `--seeds N` | 2 | runs per strategy and scenario |

## Reading a report

- Rank by **Test**: scenarios the search never tuned on (held-out twins P04, P10, P18 plus fresh
  generated ones). A big gap between Train and Test means the variant is fitted to the lab, not good.
- **Crash, 422, Broken, Worse** must be 0 for anything we run in the final. **Below alt**: ended
  under what walking away would have scored. **Wave cap**: ran out of time. **Timeouts**: threads
  left more than 60 s.
- The tables below the ranking break the winner down by case type, goal, supplier archetype and edge
  case: that is where to look for the next improvement.

## How the suppliers are modelled

`persona.py` (the economics), `bot.py` (the decisions and e-mails), `table.py` (the arena's rules and
the clock). In short:

- A supplier accepts a package when its cash value to the supplier (price, payment at its cost of
  money, freight, chargebacks at its real defect rate, plus lever premiums such as overtime for a
  short lead time) reaches its floor, its full cost. For the twins the floor is calibrated so that
  the cheapest acceptable package costs exactly the case's known `C_best`.
- First counter: a share of (opening - floor). Then it gives back a share of each of our steps, up
  to a per-round limit that shrinks; nothing without a move from us; verified data of the kinds that
  move it takes off a little more; `final_offer` when its patience is used up; pushing price after
  that may end the thread. Noise, an approval ladder (one round on hold), `no_bid`, walking after an
  ultimatum, withdrawing when left waiting at a final offer.
- Cited data is checked by the arena's published rules (`claims.py`): verified, irrelevant,
  contradicted, duplicate; a letter and a contract are one argument across the e-mail.
- Tone, threats, leaks and questions are read by keyword (`reader.py`); `llm_reader` can replace that
  with an LLM. The lab does not understand an argument: results that rest on wording prove nothing.

Scenario kinds: **twins** of the 15 suppliers we have played (12 cases, built from `runs/`),
**case files** we never played (P06, P09, P12-P17, P19 with their real suppliers from the data), and
**invented** ones (any type, goal, field, must-have, RFQ; suppliers drawn from the 46 in the data;
eight archetypes from the brief; edge cases such as an opening that breaks a must-have, walking away
as the best move, short round limits, a bidder that does not bid, case-only facts, prices per 100).

## How good it is, and keeping it good

- `runs/lab/BACKTEST.md`: our real sessions replayed into the twins (mean error per reply under 1 %
  of the opening value, status right in about 9 of 10; weak on P05 and P10).
- `runs/lab/VALIDATION.md`: the same agent in lab and arena (kit LLM agent: practice mean 59.8 in the
  lab vs 61.5 in the arena; naive P01 0.590 vs 0.583).

After new practice or sandbox sessions were pulled (`scripts/pull-runs`):

```bash
uv run python -m sellm.lab calibrate              # floors from the new sessions
uv run python -m sellm.lab backtest --fit --write # dynamics and families, runs/lab/BACKTEST.md
uv run python -m sellm.lab validate               # naive agent lab vs arena (free); --llm costs calls
uv run pytest tests/test_lab.py                   # the lab's own tests
```

Then commit `sellm/lab/twins.json` and the reports.
