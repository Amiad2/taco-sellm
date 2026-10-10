# Lab validation: the same agent in the lab and in the arena

Sat 2026-10-10, 16:20. The backtest (`BACKTEST.md`) replays real e-mails into the twins one by one.
This is the harder check: let an agent we have already run in the arena play the twins on its own
and compare the scores. Twins as in `sellm/lab/twins.json` after `backtest --fit` (dynamics fitted on
237 real supplier replies).

## Kit naive agent (deterministic; 5 lab seeds, all equal)

| Case | Arena | Lab |
|---|---|---|
| P01 | 0.583 | 0.590 |
| D01 | 0.200 | 0.235 |

## Kit LLM agent, OpenAI gpt-6.1-sol (one lab run per case, about 60 LLM calls)

| Case | Arena (baseline) | Lab |
|---|---|---|
| D01 | 0.786 | 0.759 |
| P01 | 0.789 | 0.814 |
| P02 | 0.105 | 0.183 |
| P03 | 0.903 | 0.935 |
| P04 | 0.810 | 0.982 |
| P05 | 0.676 | 0.479 |
| P07 | 0.779 | 0.760 |
| P08 | 0.433 | 0.451 |
| P10 | 0.570 | 0.686 |
| P11 | 0.710 | 0.398 |
| P18 | 0.377 | 0.286 |
| **Mean of the 10 practice cases** | **61.5** | **59.8** |

Mean absolute difference per practice case: 0.11. One LLM run per side, and the LLM agent itself
varies from run to run, so part of that is noise.

## How far to trust the lab

- **Good** (within about 0.03 in score): D01, P01, P03, P07, P08. The mean over the practice cases
  is within 2 points.
- **Weak**: P04, P05, P10, P11 (differences 0.12-0.31), P02 and P18 in between. P05 and P10 have
  one real session each, and P05 is an RFQ with three job shops whose concessions the model gets
  wrong by about 7 % of the opening value.
- **Not modelled**: the 60-second clock and timeouts (the lab has no clock), reply delays, the
  prose itself (the lab's supplier reads keywords and checks data, it does not understand an
  argument), and anything we have never seen a supplier do.
- Use the lab to **rank strategy variants by their mean over many scenarios** (twins plus invented
  ones). Do not read a single case's lab score as a prediction. Confirm a winner in the sandbox, then
  on one or two practice cases.
