# Sandbox probes: how the suppliers react (Sat 2026-10-10, 15:42-15:57)

33 sandbox sessions, no practice quota used. Script: `experiments/sandbox_probes.py`. Raw summaries:
`experiments/results/`. Every session in full: `runs/sandbox/D01/` and `runs/sandbox/D02/`, labelled
`probe <name>` in `runs/README.md`.

**All of this was measured on the three demo suppliers of the sandbox** (a family foundry in D01, a
German job shop and a Polish machining company in D02). Samples are 2-3 sessions per variant.
Treat the mechanics (sections 1, 2, 4) as how the arena works, and the price dynamics (section 3)
as a strong hypothesis to confirm on practice suppliers of other types.

## 1. Only the first term sheet of an e-mail can be accepted (H1: refuted, with a way round)

- Accepting an alternative by its ID (`offer:...-a`) fails with `422 not a standing offer in this
  session`, in the round it was offered (h1a, 2 of 2) and one round later (h1b, 2 of 2). A 422 costs
  nothing, the session goes on.
- **Way round (h1c, 2 of 2):** send the alternative's exact terms back as our own term sheet. The
  supplier answers `agreed` with those terms as its standing sheet, and that one can be accepted.
  It costs one message and took 8 s.

So when a supplier's second package is cheaper for us by C: one extra round, then accept.

## 2. After `final_offer` (H2)

All sessions reached `final_offer` on the scripted path; then one more message:

| Our answer to `final_offer` | n | What happened |
|---|---|---|
| lower price only (`h2-push`) | 2 | once unchanged, **once the supplier walked away: no deal, score 0** |
| lower price plus a give, here an earlier start (`h2-trade`) | 2 | once unchanged; once repriced to the new date at 0.10 less, which cost us 50 more in C |
| same price, later start (`h2-shift`) | 2 | refused twice, offer unchanged |
| holding message, no term sheet, no ask (`h2-hold`) | 2 | offer unchanged, new offer ID, accepted without trouble |

- **A final offer is final.** Nothing was gained after it in 6 attempts, and a plain price push
  lost the deal once in two.
- **A holding message keeps the offer alive** and restarts the 60-second clock. It costs a message
  and about 15 s.
- The gain has to be made **before** `final_offer` (section 3).

## 3. The supplier mirrors our steps, not our level (H8, H10: new)

D01, same terms in every session (30 days, 24 months, start February), only the opening ask and
the size of our concession per message varied:

| Opening ask | Our step per message | n | Supplier's final price | Score | Messages until `final_offer` |
|---|---|---|---|---|---|
| 50.00 | 0.05 | 3 | 51.40, 51.40, 51.40 | 0.676 | 4 |
| 50.00 | 0.15 | 8 | 50.70-51.00, mean 50.86 | 0.75-0.80 | 6 |
| 49.00 | 0.15 | 3 | 51.00, 50.60, 51.00 | 0.75-0.82 | 6 |
| 48.60 | 0.30 | 3 | 50.80, 50.40, 50.70 | 0.79-0.86 | 6 |
| 48.00 | 0.40 | 3 | 50.20, 50.30, 50.20 | **0.88-0.90** | 6 |

- The supplier's first counter was 51.50 in all 20 sessions, whatever we opened with (48.00 to 50.00).
- After that it gave back roughly 0.6 to 0.85 of each step we made. Tiny steps got tiny steps and an
  early `final_offer`.
- **Opening lower alone changed nothing** (49.00 against 50.00 at the same step: same result).
  **Moving more did**: every increase of our step lowered the final price.
- `final_offer` came at our 6th message in every session with steps of 0.15 or more.

What follows: plan about five concessions, open low enough that five sizeable steps still end
below the supplier's price, and make every message a visible move. The kit's LLM agent does the
opposite: it starts close and shrinks its steps (P07: 5.00, 5.10, 5.20, 5.25).

Not known yet: where this stops (the supplier's cost floor; C_best in D01 corresponds to about
49.65 on these terms, the best run reached 50.20), whether asks below the current price (48.60)
cost goodwill with a real supplier, and how a group with an approval ladder or a near-monopolist reacts.

## 4. RFQ: the 60-second clock (H3)

| Variant | n | Timeouts per session | Deal | Score |
|---|---|---|---|---|
| kit `play()`, one thread at a time (`h3-seq`) | 2 | 2 (one on each thread) | job shop, `agreed` at 15.30 and 15.00 | 0.492, 0.441 |
| rounds in lockstep, a ready thread held back (first try of `h3-par`) | 1 | 2 | **the cheaper supplier withdrew**; closed with the other at 16.10 | 0.239 |
| one loop per thread, accept the first ready thread if cheapest (`h3-par`) | 2 | **0** | job shop, `final_offer` at 15.40 | 0.345, 0.345 |
| scripted, citing the rival's offer by ID (`h11`) | 2 | 0 | job shop, `agreed` at 15.50 DAP | 0.461, 0.461 |

- **One loop per thread removes the timeouts.** Each thread answers as soon as its own reply
  arrives; replies took 30 to 59 s, so waiting for the slowest thread breaks the others' clocks.
- **Never leave a thread at `final_offer` waiting.** The job shop, at `final_offer`, was left for
  over a minute while the other thread went on. When we came back to accept, it had withdrawn: "We
  need to plan our machine time, so I am closing this RFQ." Accept at once, or send a holding message.
- **How a timeout works:** it is counted when the session is next touched, once, however long the
  silence was. The supplier then sends a follow-up with a **new offer ID** (the old one is no
  longer acceptable) and may harden: the Polish supplier went from `open` to `final_offer` at the
  same price. `GET /v1/sessions/{sid}` shows `seconds_left` per thread. Accepting the re-issued
  offer inside the new 60 s worked.
- **Removing the timeouts did not raise the score here.** The sequential runs happened to get the
  better price. What we ask decides the score; the clock decides whether a supplier is still there.
- **A rival's offer cited by its ID is `verified`**; citing the same ID again is `duplicate`. Offer
  IDs change every round, so there is always a fresh one.
- **An early `agreed` means we asked too little**: in `h11` the job shop agreed to our second ask
  at once. C_best in D02 is 156,739; the best we closed is about 186,000. Both suppliers have far more
  room than any run found.

## 5. Rules for our agent

1. Price every sheet in an e-mail by C. To take a second sheet, send its terms back, wait for
   `agreed`, accept.
2. Never push the price after `final_offer`. Accept, or hold once if another thread needs a minute.
3. Open low and concede in about five large, visible steps; keep every ask below the supplier's
   standing price. Never repeat an ask and never shrink the steps early.
4. In an RFQ run one loop per thread. No thread may wait on another.
5. Accept a thread at `final_offer` within its 60 seconds, or hold it. After any timeout re-read the
   thread: the offer ID has changed.
6. If the supplier says `agreed` early, the ask was too high: the next case of that kind needs a
   lower opening.

## 6. Next probes

| # | Question | Where | Cost |
|---|---|---|---|
| H12 | Can we go on negotiating after `agreed` instead of accepting, and does the agreed sheet stay acceptable? | D01 | free |
| H13 | Where does the mirror effect stop: steps of 0.6 and 0.8, opening at 47.00 and 46.00 | D01 | free |
| H14 | Does the mirror effect hold for a practice supplier? P07 lost only on price (gap 20,243) | P07 | 1 session |
| H15 | RFQ with a low opening, large steps, rival citations and a held leader | D02, then P05 | free, then 1 |
| H4-H7 | still open from `runs/BASELINE.md`: P01 April start, P10 the 54-day package with should-cost, P02 90 days, P08/P18 data | practice | 1 each |
