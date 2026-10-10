# LEDGER - Omar's research on omars_branch (Sun 11 Oct 2026, from 02:15 CEST)

Every arena session this research plays is one line in the table at the bottom (written by
`experiments/structure_args.py arena`, lines for other runners by hand). Results stay as measured; a
hypothesis is marked as one.

## Budget

- **50 arena runs**, set by Omar for this research. **One run = one practice session** (`POST
  /v1/sessions` on a hosted practice case), the unit the arena's quota counts (`GET /v1/me`
  `practice.used`). A full practice run is 10 runs. Messages inside a session are free; sandbox
  `D01`/`D02` and the local `arena-sim` do not touch the quota (verified Sat 14:49) and are listed
  with `0 (sandbox)`.
- The previous session on this branch used 21 practice sessions (SESSION_HANDOFF.md section 5). If
  Omar's 50 was meant to include them, 29 remain: **this ledger plans to stay within 29 and goes
  beyond only with a stated reason.**
- The team quota is shared (450 per rolling 24 h, `uv run arena me`: used 195, left 255 at 01:41;
  teammates play too), and 40 sessions are kept for Sunday (AGENTS.md section 5). So the team
  counter cannot count this ledger's runs; the lines below do.

## Method

- Practice suppliers answer identical e-mails identically (confirmed many times, `docs/LEARNINGS.md`),
  so one session per case compares a variant with today's agent exactly *for that case*; P05 (RFQ)
  varies with timing. The reference is today's agent, `@7a49c38` (= `omars_branch@a5b363c`), 72.9
  over the 10 hosted cases, one recorded session per case in `runs/`.
- Before any session, `python -m experiments.structure_args replay <variant>` replays the recorded
  states offline and names the cases where the variant sends a different e-mail. Only those cases
  are played; the others score what they scored.
- Practice is not the final: hidden cases have new suppliers. A change is adopted only with a
  mechanism that should carry over and no loss on the practice cases it changes.

## Experiments

| ID | Hypothesis | Change (knob) | Cases changed offline | Runs | Result | Decision |
|---|---|---|---|---|---|---|
| E0 | Reference | today's agent @7a49c38 | - | 0 (recorded) | 72.9: P01 .969 P02 .531 P03 .923 P04 .860 P05 .820 P07 .747 P08 .549 P10 .647 P11 .778 P18 .467 | reference |
| E1 | A contract longer than the horizon earns us nothing in C, but the supplier prices a longer fixed price (P08: "for a contract of this length we must include an index clause"; P07 quoted 24 and 36 months alike; P10 24 months 0.10 cheaper) | `contract="horizon"`: where C does not care, the shortest option that covers the horizon | P03 P04 P07 P08 P10 P18 | | | |
| E2 | A cost-driver index that fell from its recent peak is a checked argument that answers the supplier's own index argument; index facts were "taken into account" by 4 of 5 suppliers that heard one | `idx_recent=2.0`: cite the largest fall (weight x change) of >= 2 % from the peak of the last 12 months, when the yearly change rose | P05 P08 P18 (AS-14404 -5.5 % 2026-06 to 2026-09) | | | |

## Sessions

| When | Variant | Case | Runs | Score | End | Version | Session |
|---|---|---|---|---|---|---|---|
