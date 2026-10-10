# LLM-written e-mails vs the template (lab, Sat 23:28, Omar)

**Result: no gain from LLM wording. The template stays.** Same moves, same term sheets and the same checked
facts; only the e-mail text differed. Against LLM suppliers on the 12 twins the LLM writer scored 62.0
against 65.2 for the template (-3.1 points; better in 2, worse in 5, equal in 5).

## Setup

- Arms: `sellm.agent:make_agent` (what `--agent sellm` plays, template e-mails) and
  `experiments.llm_writer:make_agent` (the same negotiator; `gpt-6-sol` rewrites the e-mail around the
  argument sentence and the offer phrase, which code requires word for word; no new figures, no leak or
  ultimatum, else the template goes out).
- `uv run python -m sellm.lab compare sellm.agent:make_agent experiments.llm_writer:make_agent --supplier llm
  --fixed-twins --invented 0 --test 0 --seeds 1 --think -1 --workers 4 --label llm-writer`
  (report: `runs/lab/20261010-232834-compare-llm-writer/report.md`). The engine supplier ignores wording,
  so only `--supplier llm` can show a difference.
- Calls: 54 writer calls, 115 supplier calls, about 20 for the P18 check below. No failures.

## Per twin

| Twin | Template | LLM writer | Difference |
|---|---|---|---|
| D01 | 0.913 | 0.913 | 0.000 |
| D02 | 0.631 | 0.658 | +0.027 |
| P01 | 0.827 | 0.798 | -0.029 |
| P02 | 0.281 | 0.170 | -0.110 |
| P03 | 0.942 | 0.943 | +0.001 |
| P04 | 0.860 | 0.860 | 0.000 |
| P05 | 0.304 | 0.304 | 0.000 |
| P07 | 0.818 | 0.805 | -0.013 |
| P08 | 0.484 | 0.484 | 0.000 |
| P10 | 0.660 | 0.633 | -0.027 |
| P11 | 0.676 | 0.693 | +0.017 |
| P18 | 0.421 | 0.181 | -0.240 |
| **Mean** | **65.2** | **62.0** | **-3.1 points** |

## What else was measured

- **The writer is safe and fast enough:** 54 of 54 e-mails passed every guard; 4.3 s median, 6.0 s max per
  call (the 60-second rule is not at risk).
- **The LLM supplier is stable for the same e-mail:** P18 with the template, cached and fresh, gave the same
  deal (0.320). So the differences come from the wording, not from sampling.
- **The size of the effect is not stable:** P18 replayed with `play` (slightly different settings than
  `compare`) gave 0.293 for the LLM writer against 0.320 for the template (-0.027, not -0.240). The sign held.
- **Why it loses** (P18 transcript): the LLM's e-mails are warmer and answer the supplier, but they repeat
  its price ("We appreciate your offer of EUR 5.82 per unit") and concede its points ("We understand your
  concern about material-price risk"). The facts are the same; the position reads softer.

## Limits

- The suppliers are our lab's LLM suppliers (`gpt-6-sol` inside the calibrated engine), not Tacto's bots,
  and the same model wrote our e-mails. One run per twin.
- What would settle it for real: the free sandbox (`case:D01`, `case:D02`, real bots) with
  `experiments/ab_sandbox.py`; the arm `nego-llm` there still writes the template and would need this writer.

## Trap found on the way

The kit and `sellm/llm.py` read the key from `LLM_API_KEY`. A `.env` that only has `OPENAI_API_KEY` makes
every LLM call fail, and the kit's LLM agent then plays the naive move without an error.
