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
| E1 | A contract longer than the horizon earns us nothing in C, but the supplier prices a longer fixed price (P08: "for a contract of this length we must include an index clause"; P07 quoted 24 and 36 months alike; P10 24 months 0.10 cheaper) | `contract="horizon"`: where C does not care, the shortest option that covers the horizon | P03 P04 P07 P08 P10 P18 | 1 | **P08 0.538 (ref 0.549).** Refuted where it was meant to work: "for a 24-month duration, we cannot offer a fixed price". First counter 0.12 lower (5.45 vs 5.57), but smaller steps after it and the same end (5.36 vs 5.35) | **rejected**; knob stays off; the other 5 cases not played (expected effect about +-0.01, not worth 5 runs) |
| E2 | A cost-driver index that fell from its recent peak is a checked argument that answers the supplier's own index argument; index facts were "taken into account" by 4 of 5 suppliers that heard one | `idx_recent=2.0`: cite the largest fall (weight x change) of >= 2 % from the peak of the last 12 months, when the yearly change rose | P05 P08 P18 (AS-14404 -5.5 % 2026-06 to 2026-09) | 2 | **P18 0.520 (ref 0.467, +0.053)**: "We have verified the recent decrease in the AS-14404 index and have reduced our price" - first counter 5.40 instead of 5.60, deal 5.30 db0 instead of 5.50 db5. **P08 0.438 (ref 0.549, -0.111)**: "That is not our reality: our AS-14404 is covered at fixed prices until March, so that fall does not reach our cost"; the round was lost and it said final_offer a round earlier, at 5.45 | split by a signal the dossier already has -> E2g |
| E2g | As E2, but the fall of a material index does not reach a supplier whose material is hedged; the dossier reads that from its quote remark "Material covered until March 2027" (`material_hedged`, 6 quotes of 5 suppliers) | E2 + `Negotiator.hedged`: no material index claim (not LCI-, PPI-D35) to a `material_hedged` supplier | P05 P18 (P08 now sends what the reference sent) | 0 | by replay: P08 = reference 0.549, P18 = the E2 session 0.520 (same e-mails). P05 (RFQ, 70210 hears the index at message 2 instead of its OTD; 70210 took index facts 10 of 10) not played: RFQ scores vary 0.66-0.82 with timing, one run would not say much | **candidate**: +0.53 points on the 10 cases (73.4), no loss measured or replayed |
| R1 | The final runner (one loop per thread) loses RFQ threads to timeouts because the arena works through a session's messages one after another (P05: 0.665 with a 70250 timeout in every runner session; kit runner 0.820 x5 with today's agent, 0 timeouts) | `sellm/runner.py --serial`: one POST per session in flight | P05 (RFQ) | 1 | **P05 0.735, 0 timeouts** (runner 0.665, kit runner 0.820). Timeouts gone; the deal 28.83 was our own ask capped just below the rival's 29.00, where the kit's order had both bidders down to 28.00 | timeouts fixed, order still worse -> R2 |
| R2 | The kit's order (the agent picks the thread, fewest of our messages first) is what made P05 0.820, not the kit runner as such; the final runner in that order keeps its safety (cap, resume, deadline, holds) | `--turns`: one loop per case, the agent decides without `focus`, one message in flight | P05 | 1 | **P05 0.820, as predicted** (the kit run's e-mails and prices exactly), 0 timeouts, 0 refused, 3.3 s for the whole case | **adopted on omars_branch: default of `python -m sellm.runner`** (`--per-thread` restores one loop per thread). Single-thread cases play the same moves either way |

## Sessions

| When | Variant | Case | Runs | Score | End | Version | Session |
|---|---|---|---|---|---|---|---|
| Sun 02:00 | E1 | P08 | 1 | 0.538 | accepted | omars_branch@c8c0eb5 | c2a43a93eb19604c |
| Sun 02:00 | E2 | P18 | 1 | 0.52 | accepted | omars_branch@c8c0eb5 | 78ad49af234d527a |
| Sun 02:02 | E2 | P08 | 1 | 0.438 | accepted | omars_branch@c8c0eb5 | 04f83caa53890e47 |
| Sun 02:11 | R1 runner --serial (reference agent) | P05 | 1 | 0.735 | accepted | omars_branch@650e6e8 | 5aa402cdd13ddb6b |
| Sun 02:19 | R2 runner --turns (reference agent) | P05 | 1 | 0.820 | accepted | omars_branch@fdb262e | b6c71e626f579a83 |
