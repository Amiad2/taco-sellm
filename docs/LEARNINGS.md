# LEARNINGS - what works and what fails in negotiations

Durable findings with their evidence. Add one when a replay, a cost breakdown or an offline
calculation teaches something that should change how the agent behaves. State how sure we are:
**confirmed** (seen in our own replay), **computed** (from the cost function), **reported** (from
Tacto's docs or FAQ, not yet seen by us). Raw history goes to `docs/LOG.md`.

## General

- **Tone and relationship move price** (reported, FAQ P01 recording). Appreciation for past
  fairness plus one verified index plus an offer to pay faster got 0.76. The same index sent as an
  ultimatum got EUR 136.50 from November instead of January, about EUR 13,700 a year worse.
- **Price is only one lever, and often not the biggest** (computed, P01 below). The kit's naive
  agent negotiates price only and leaves the other fields at the supplier's opening values.
- **The kit agents ignore the relationship term** (confirmed in code). In `stabilise` and
  `secure_supply` cases the arena charges for leaving the supplier below its sustainable margin;
  `total_cost` only includes it when given a supplier estimate. Our P01 deal at EUR 135.40 showed
  `relationship: 0.0` in the arena's breakdown, so that price did not squeeze Brandlhuber.
- **Answer "which figures?" with data** (reported, FAQ P01 recording). The supplier asked for the
  basis of our price; citing the should-cost estimate (`cost:310010`) was `verified` and brought
  the closing offer.
- **Trust the numbers, not the supplier's prose** (reported, `brief/api.md`,
  `data/package/KNOWN_ISSUES.md`). Term sheets and the generated documents (quote PDF, cost
  breakdown, 8D report, delivery schedule, order confirmation) are "rendered from the supplier's
  structured state, never written by a language model, byte-stable" - their figures are exact and
  bind. The e-mail body's reasoning is in-character colour, not fact-checked: "cheaper engineering
  variants a supplier mentions are information, not binding terms," and identical messages need
  not get identical replies. P01's letter blames energy costs while the cited index shows
  electricity (PPI-D351) fell 3.7 % over the period (see below) - read a stated reason as a signal
  of what the supplier cares about, not as a checked fact.
  Our own `facts.json` is the one checked ground truth for what *we* cite, and it has documented,
  deliberate quirks, not errors: `should_cost` carries a stated error (5 % where a plant-specific
  estimate exists, 5-15 % otherwise, with `confidence_pct` in `facts.json`); `sup:71999` and
  `sup:70210` are the same company under an old/new record; some PO lines carry a stale price
  (`price_note: stale_condition`); OTD differs 10-30 points depending on which of three delivery
  dates (requested, confirmed, goods-receipt) you read; ppm is jumpy on small lots, so read the
  rolling scorecard. Pick the right reference before citing, and build the argument bank only from
  IDs checked against `facts.json`, never from a supplier's stated reasons.

## From Sunday morning's structure tests (Sun 09:45-10:10, 14 practice sessions; `experiments/LEDGER-JONATHAN.md` J16-J21)

- **An index clause the supplier insists on is paid back in price if we keep asking for the fixed price** (P18:
  its clause sheets fell 0.20 per fact instead of 0.10; 0.657 -> 0.729). Following onto its clause at once gives
  that away. Not so for a supplier whose material is hedged (P08: a cent worse).
- **Other refused terms are not paid back**: a lead time it calls not feasible (P10, 0.586) or a chargeback (P11,
  0.398) kept in every ask costs the price instead.
- **P10's supplier stops at 31.50 after our second message**, whatever that message asks (30.30 to 31.30).
- **P07's final offer comes at the third message whatever the third ask is**; a round more needs a first ask
  near 5.00, which costs P11 and P18.
- **What a case's index path makes of a clause**: with an expected rise of 6 % and 45 % material share a clause
  without a deadband costs 3.15 % of the spend, with a 5 % deadband 0.9 %, a fixed price nothing.

## From the Sunday release (Sun 08:50-09:20, 3 practice sessions; `experiments/LEDGER-JONATHAN.md` J13-J15 on `jonathans_branch`)

- **Practice stays on package v1** (`brief/api.md`: "Hidden cases may cite them; practice cases stay on
  package v1"). Measured: the release's news about P11's supplier, cited there, is `contradicted`
  ("that news is completely fake"), and the supplier makes no further step (0.626 against 0.778). No
  practice supplier knows the release; a practice score says nothing about a release rule.
- **The kit merges the release into `DataPackage.facts` for every case.** An agent that cites any ID
  `lookup()` knows is contradicted on practice. Ours cites no release ID on the ten hosted cases.
- **A letter says what its writer needs.** As the trigger of a case with several bidders it must not be
  read for the others (found offline: one bidder's request to be paid within 10 days made all three
  bidders look short of cash). Our own memo is nobody's statement.
- **Saying a supplier's letter back to it adds nothing** (P05: the bidder on short-time work, 28.50
  instead of 28.00). What it asks for has to be in the term sheet: the 14 days moved it, as before.
- **News about the supplier that favours the buyer is a fact that moves** (recorded sessions: "looks
  for new customers" cited to 70250, verified, a step of 0.50 in 8 of 8).
- **Offering what a letter names costs nothing**: a fixed call-off schedule offered to the supplier
  that wrote "open to discuss payment terms and call-off planning" left P02 at 0.725; its reasons
  name the forecast. Whether it gains can only show in the final.

## From omars_branch's experiments (Sun 01:50-03:30, 17 practice sessions; `experiments/LEDGER.md` on `omars_branch`)

One change at a time against the recorded sessions of today's agent; a case was played only where an
offline replay showed a different e-mail.

- **A fact the supplier did not know moves it at once** (confirmed, P18): "The index AS-14404 changed
  -5.5 % from 2026-06 to 2026-09" (it rose 5.9 % over the year, as the supplier's own quote says) -
  "we have verified the recent decrease ... and have reduced our price": first counter 5.40 instead of
  5.60, 0.467 -> 0.520. A window of up to 12 months that ends with the data is checked like the
  yearly one.
- **The same fact to a supplier whose material is hedged costs points** (confirmed, P08): "That is not
  our reality: our AS-14404 is covered at fixed prices until March, so that fall does not reach our
  cost" - no move that round and final_offer a round earlier, 0.549 -> 0.438. Its quote remark says so
  ("Material covered until March 2027"; dossier signal `material_hedged`, 6 quotes of 5 suppliers).
  Jonathan (02:54): the hedge covers that material only - P08 took a fall of PPI-C2431.
- **A round without new information is neutral or costs a round** (confirmed): leaving out a fact the
  supplier would dismiss (E3: P08 -0.034, P07 -0.013, P18 +0.047), a duplicate forecast or a question
  about its cost build-up (E5: P08 -0.034, P07 -0.007) - two suppliers say final_offer sooner after
  a round with no new fact; one hardens after a dismissed fact. Keep one fact per e-mail; filler is
  not a fact.
- **A bigger number is not always better** (confirmed, E4): citing electricity's fall from its peak
  (-6.1 %) instead of over the year (-3.7 %) gained P01 (0.969 -> 0.997) and lost P11 twice
  (0.778 -> 0.710: the same prices, but it held at our 45.09 instead of agreeing).
- **A contract longer than the horizon is neither priced nor rewarded** (confirmed, P08 E1): 24 instead
  of 36 months did not avoid the index clause ("for a 24-month duration we cannot offer a fixed
  price"); first counter 0.12 lower, same end.
- **RFQ: the order of our messages matters more than their speed** (confirmed, P05): one loop per thread
  0.665 (the arena processes a session's messages one after another, so parallel ones are counted
  late), one message in flight 0.735, one loop per case in the agent's order (fewest of our messages
  first, as the kit's play()) 0.820 in 3-52 s. That is the default of `sellm/runner.py` on omars_branch.

## From sellm2 (Sun 03:00-03:30, 17 practice sessions; `docs/LOG.md` Sun 03:30)

- **Suppliers walk their price ladder whatever non-cash lever we give them** (confirmed, 2 cases): P11
  answered 1500 ppm with the same ladder as 300 ppm (46.5, 46.0, 45.5; 0.620 against 0.778); P05's
  non-tight bidders ended at 28.00 with a 42-day lead time as with 28 days (0.803 against 0.820). Give
  a lever only where the supplier has shown it prices it: payment days at its cost of money, lead time
  when its capacity is tight (P10 1.90 for 12 days, P05's 70240 1.50 for 10 days).
- **No lowball to a capacity-tight supplier** (confirmed, P10): a first ask at 93 % of its opening on its
  own lead time (29.95 at 56 days) got 31.70 and 0.671; every first ask <= 28.6 had got final_offer at once.
- **A recent fall of a cost driver from its 12-month peak moves a supplier that is not hedged**
  (confirmed again, P18): first counter 5.40 (5.50 with the 5 % deadband), deal 5.30 with the deadband,
  0.598 - the best P18 so far.
- **A fixed-list-price supplier does not take an ask 0.2 % below its repeated price either** (P04 4.93
  against 4.94, P03 431.28 against 432.14): it says final_offer at its price, as before, one round sooner.

## From the P02 argument tests (Sun 01:20-02:10, 8 practice sessions; `experiments/P02-ARGUMENTS.md` on `jonathans_branch`)

Nordmark (P02) ended at EUR 371.66 with 90 days in more than ten sessions, whatever was asked or
argued. One session per untested kind of argument, on top of `--agent sellm`:

- **An index clause is security for a supplier, and it pays for it with price - far more than the
  clause costs us** (confirmed, P02). Asked for the copper clause with the 5 % deadband (cost to us:
  0.8 % of spend), Nordmark's first answer was 351.45 instead of 373.97: "we agree to introduce the
  CU-NOTATION index clause to reduce the base price". Its letter passes copper on; the clause does
  that for it.
- **With a relationship term the lowest price is not the best one, and code has to choose the
  price** (confirmed, computed). The arena counts a clause as security, not cash: 351.45 is 5.8 %
  below Nordmark's full cost and cost us EUR 119,974 in the relationship term - score 0.242, worse
  than the fixed price (0.531). Our total cost is lowest at 361.35 (score 0.735): there the next
  euro off the price costs more in the relationship term than it saves.
- **A supplier never raises a price it has named** (confirmed, P02): asked 361.35 after its own
  351.45 ("we do not want a price that leaves you below a sustainable margin") it answered twice
  "our offer of EUR 351.45 is economically viable and remains our official position". Asked 361.35
  at once, it agreed in its first reply. So an ask the supplier may undercut must already be the
  price we want: never open below it on a structure that gives the supplier security.
- **Two sheets in the first e-mail work as a menu** (confirmed, P02): the fixed-price ask and the
  clause at our price - it agreed to the clause sheet at once (362.70, score 0.725; the price came
  from our own cost estimate, capped by its opening).
- **A fixed-price wall can be the supplier's cost floor exactly** (computed from two relationship
  charges, to the euro): Nordmark's full cost is EUR 367.56 at a cost of money of 6.67 %, and 371.66
  with 90 days is worth exactly that to it. No argument goes below it: "below this price we would
  need facts, not just a lower number".
- **A fact the arena calls `irrelevant` is not free** (confirmed 2 of 2, P02): an index that is not a
  cost driver of the part (producer prices of electric motors, electricity) and order prices or the
  forecast of another part of the same supplier came back `irrelevant`; the verified fact next to
  them lost its effect (the forecast moved it 0.46 instead of 1.91) and it said `final_offer` after
  three messages instead of four (0.394 and 0.319 against 0.531). Cite only facts about this part
  and its cost drivers.
- **Not levers on Nordmark** (one session each): answering its question "which volume can you
  commit to?" with the contract's binding volume and a call-off schedule (0.525), asking it to put
  our proposal before its pricing committee (0.480). Earlier, by Amiad: past renewals asked vs
  settled, more arguments per e-mail, a warmer or a coercive tone.

## From the practice arms (Sat 21:15-21:35, 30 practice sessions; `experiments/PRACTICE-ARMS.md`)

One change per arm on the real practice suppliers, base `19b339f`. Per-case scores and the code of
the arms are in `experiments/PRACTICE-ARMS.md` and `experiments/arms/`.

- **Practice suppliers answer identical messages with identical numbers** (confirmed: v1.1 twice,
  9 of 10 cases identical; D01 x3). One session per single-supplier case is a fair comparison; only
  RFQ threads move with timing (P05 0.659-0.769). Replaying a variant over recorded sessions says
  which cases it changes before any session is spent (`experiments/arms/tools/replay.py`).
- **A verified fact moves a supplier by 1-2 %, on some suppliers** (confirmed): P01 0.831 -> 0.915
  (notice letter `doc`+`ctr`, should-cost, forecast; "we did not know that - a fair point"), P02
  0.293 -> 0.531 (price history `po`, forecast, OTD). It did not move P04, P07, P08, P18 ("it holds,
  but it does not change our calculation").
- **The arena reads integers with a thousands comma as something else** (confirmed 4 of 4):
  "2,376 ppm", "5,263 ppm", "27,778 ppm" came back `contradicted` and cost trust ("That costs
  trust"); "2376 ppm" was `verified`. EUR amounts with decimals and forecast units were fine.
  Write ppm and other integer figures without a thousands separator.
- **Topics count once per case, not IDs** (confirmed, P07, P11): after one forecast `fc:` of one part
  another part's forecast is `duplicate`; a complaint `qn:` after the scorecard's quality `sc:` is
  `duplicate`. Verified together in one case: index, notice letter + contract, should-cost, price
  history, forecast, on-time delivery, quality record.
- **A `duplicate` citation still works; a round without an argument gets a hold** (confirmed,
  Sat 22:16): dropping the `qn:` that followed an `sc:` cost P11 0.778 -> 0.710 (the supplier held
  45.50 from the first argument-free round on, "we are really at the limit", instead of accepting
  45.09) and P02 0.531 -> 0.522. The supplier reads the sentence ("that quality complaint ... was
  already baked into our last price drop") and keeps conceding. Keep sending an argument each round.
- **The supplier's final price on a given structure does not depend on our first ask** (confirmed
  on P04 4.09 vs 4.54, P11 38.88 vs 42.41, P18 5.02 vs 4.89): suppliers follow their own concession
  schedule. What our ask changes is which alternative sheets they put next to their offer.
- **Asking for an index clause's deadband is priced by the supplier** (confirmed, mixed): P08 it
  moved from 5.35 to 5.55-5.59 (0.549 -> 0.42-0.46), P18 it gave the 5 % variant for +0.10
  (0.386 -> 0.467-0.485). Take a deadband variant the supplier quotes when C prefers it; do not
  assume the price stays.
- **The dossier is worth about 3.5 points on the six cases tested** (confirmed, 6 cases: 5 better,
  1 equal, `no dossier` vs `full`). For a supplier without one the agent sends two equal-C offers
  (quoted days and 90 days) and loses little.
- **Bundles: contract length beyond the horizon is not free** (open, P07): 5.41 for 36 months here,
  5.36 for 24 months from the kit agent; not yet tested one against the other.

## From the negotiator's sandbox runs (Sat 18:40-20:20, 29 free sessions; `experiments/RESULTS.md` section 7)

- **Suppliers price in value** (`arena_kit.cost.supplier_value`): a later start date or longer
  payment is paid for in the price (D01: first counter 51.30 / 51.50 / 51.80 for December /
  February / April, the same worth to the foundry). Contract length was free. So: ask for coverage,
  trade cash terms only where the supplier's cost of money differs from ours.
- **With two or three term sheets the supplier answers the one worth most to it** (65 of 79
  replies), not the one cheapest for us. It answers on our structure in 294 of 304 replies.
- **The step must fit the gap.** The foundry gives back half of our step, the job shop all of it
  and asks for "bigger steps". Sizing each step from the gap, the rounds left and the share it has
  given back so far beat fixed steps on both cases (D01 0.894 -> 0.920, D02 0.448 -> 0.530).
- **Citing the rival's standing offer moved the second bidder at once** (16.40 -> 15.40, "we are
  prepared to match the competing offer"), with the claim `verified`.
- **Take the trade a supplier names**: "If you can pay in 14 days, I can come down" came as an
  alternative sheet; sending that sheet back closed 0.2 lower.
- **A bidder that says `agreed` is not automatically the best offer**; close on the cheapest
  standing offer. A leader left waiting timed out and its offer got worse (14.50 -> 14.60).
- **In all five real cases with a relationship term the opening itself carried none** (D01, P01,
  P02, P03, P10), and the suppliers' final offers sat near their sustainable margin (D01: 3.3-4.0 %
  against 4 %). Backed out of the results: full cost / opening price was 0.909 (D01), 0.938 (P01),
  0.899 (P03); the should-cost of the supplier's own plant was 2 % above the true full cost in
  both cases where we can check it (P01, P03).

## From the sandbox probes (Sat 15:42-15:57, 33 free sessions)

Evidence and tables: `experiments/RESULTS.md`. Measured on the sandbox's demo suppliers only.

- **Only the first term sheet of an e-mail can be accepted** (confirmed, 4 of 4: `422 not a
  standing offer`). To take a supplier's second package, send its exact terms back as our sheet;
  the supplier answers `agreed` and that sheet can be accepted (confirmed, 2 of 2).
- **A final offer is final** (confirmed, 8 sessions). Pushing the price after `final_offer` gained
  nothing and lost the deal once in two tries. A holding message without a term sheet keeps the
  offer alive and restarts the clock.
- **P02 also withdrew after a post-final-offer price push** (confirmed, 2026-10-11, replay
  `1a882885bd67dea7`): with the LLM writing the e-mails, a buyer ladder of EUR 1.00, 46.89, 92.78
  led Nordmark to EUR 373.85 at 90-day payment and `final_offer`; our next ask, EUR 138.68, ended the
  session with no deal (score 0.000). The requested ten rounds were impossible once the supplier
  withdrew. Do not push after `final_offer`; the one-euro anchor also did not bring the supplier near
  the buyer's EUR 368.14 target. Three follow-up branches at EUR 370.00, 369.03, and 368.14 after
  `final_offer` (EUR 373.95, 373.90, 373.85 respectively) all ended in withdrawal and score 0.000.
  A fourth run offered EUR 370.00 after `final_offer` at EUR 373.80 and answered Nordmark's stated
  arguments point by point: weighted input exposure, historic purchase prices, financing premium,
  and the missing price bridge. The seller still withdrew (replay `80108787b179d871`); stronger
  argumentation did not change the post-final-offer outcome.
- **The supplier mirrors our steps, not our level** (confirmed on D01, 20 sessions). Its first
  counter did not depend on our opening. It then gave back 0.6-0.85 of each step we made and said
  `final_offer` at our 6th message. Opening 1.00 lower with the same steps changed nothing; steps
  of 0.40 instead of 0.15 moved the score from about 0.77 to 0.89. Steps of 0.05 got 0.68 and an
  early final offer. **Open low, concede in about five large steps, never shrink the steps early.**
  Not yet confirmed on a practice supplier.
- **RFQ: one loop per thread** (confirmed). It removes the timeouts. A supplier at `final_offer`
  left waiting for over a minute withdrew. After a timeout the offer ID changes.
- **A rival's offer cited by its ID is `verified`** (confirmed); the same ID twice is `duplicate`.
- **An early `agreed` means the ask was too high** (seen in D02): both RFQ suppliers have far more
  room than any run found (C_best 156,739, best closed about 186,000).

## From the lab (Sat 16:00-17:00, `sellm/lab/`, `runs/lab/`)

How the twins were built and how well they match: `runs/lab/BACKTEST.md`, `runs/lab/VALIDATION.md`.

- **A supplier's floor is its full cost in cash terms, and C_best pins it down** (computed, two
  routes). The floor that makes the cheapest acceptable package cost exactly C_best is 129.91 for
  P01; the relationship charge the arena billed on our P01 deal implies 129.95. Where a
  plant-specific should-cost exists, floors are within 3-5 % of it. So **should-cost is a good
  estimate of the floor**, and the floor is in value terms: faster payment, a longer lead time or an
  index clause lower the price the supplier can accept.
- **Suppliers price levers at their own cost** (seen in their alternative sheets): payment days at
  about 6.5 % a year for groups (P02, P08), about 9 % for a family foundry (D01), about 35 % for a
  Czech job shop (P05: 16 days faster = 0.50 on 32); lead time about 0.15 EUR per unit per day
  shorter (P10); 1,200 ppm tighter about 1.40 EUR per unit (P11). A trade is good for us when its
  value to us is above that.
  Measured over every saved session (Sat 22:15, replies with two sheets that differ only in payment
  days, yearly rate = price step / mean price / day step x 360), against the dossier's
  `cost_of_money`: P02 70510 0.066 and P08 70710 0.065 (group, dossier 0.065); P03 70530 0.041
  (group, 0.065); P04 70620 0.073 and P07 70610 0.075 (family, 0.09); P18 70740 0.11-0.22 (family,
  0.09; it also wrote "we have already reached our limit for these extended payment terms");
  P05 70240 0.17-0.35 (job shop, 0.25); D01 DEMO-F1 0.093; D02 DEMO-J1 0.15, DEMO-C1 0.14. The
  dossier's rates are right for groups and within a factor of two elsewhere. Our own rate is 0.08,
  so asking 90 days of a supplier above it costs us more in price than the days earn.
- **The kit LLM agent closed 1-31 % above the floor** (computed): P04 1 %, P01 2 %, P02 2 %, P11
  4 %, P07 8 %, P08 10 %, P18 20 %, P10 31 %. The room is largest where we scored worst.
- **Concessions per round are small and bounded** (backtested on 237 real replies): first counter
  about a third of (opening - floor), later ones a share of our step but at most about 0.3-0.6 % of
  the opening per round, final offer around our 6th message. So the first counter and the number of
  rounds used decide most of the outcome; steps beyond what the supplier mirrors are wasted.
- **Which data moved a supplier** (seen: "it holds and we took it into account" vs "it holds, but
  it does not change our calculation"): notice period (P01), volume change (P03), quality record
  (P11), rival quote (D02) moved it; notice period (P02), volume change (P04, P10), delivery
  record (P18) did not.
- **A letter and a contract are one argument across the whole e-mail** (seen, P01): the arena
  verified doc + ctr in different sentences; the same letter cited again was `duplicate`.

## From the baseline of all 10 hosted cases (Sat 15:27, kit LLM agent, mean 61.5)

Full analysis with evidence per case: `runs/BASELINE.md`. The rules that follow from it:

- **Price every sheet a supplier sends and compare by C** (seen, computed). Suppliers put two
  packages in one e-mail in 11 of 12 threads; the kit reads only the first. In P10 the ignored
  alternative was worth 0.647 against the accepted 0.570. Taking it needs one more round (see above).
- **Use the rounds before `final_offer`** (seen). The kit agent accepted after 2-5 of 10 messages.
  The sandbox probes show nothing is gained after a final offer, so the work is in the steps
  before it.
- **Talk to all RFQ threads in parallel** (seen, P05): handled one by one, the waiting threads
  timed out and the cheapest bidder withdrew.
- **Never cite the same ID twice in a case** (seen): 8 of 16 claims came back `duplicate`. Bring a
  new, checked figure each round, and have data ready when the supplier asks "Which figures is
  that based on?" (P03, P04, P05, P10).
- **Should-cost is the price target** (computed): where an estimate for the supplier's own plant
  exists, the price at C_best is 0.98 to 1.16 times should-cost (P01, P02, P03, P10). In P10 we
  closed at 1.38 times and never cited it.
- **Give what is cheap for us and valuable to them** (seen, P11): dropping the chargeback (worth
  2,146 to us) bought 1.00 off the price (worth 15,900). A supplier that insists on fast payment
  (P01: "14-day payment is essential for us to offer our best price") can be asked for a later
  start date instead of a lower price.
- **A long payment term is a big lever with a large supplier** (computed, P02): 90 instead of 30
  days is worth 30,155 of a 42,371 gap, and the supplier's premium for it was smaller than our gain.
- **With a rising index path an index clause costs us** (computed, P08, P18), and these suppliers
  resist a fixed price. Know the value of each clause variant before trading it.
- **Open**: in P08, P18 and P10, C_best lies 6-19 % below the *current* price. We do not know yet
  which fact in the data unlocks that.

## P01 - Gießerei Brandlhuber (sup:70110), +9.5 % on HN volute casings, `stabilise`

Case numbers: need 8,150 a year, horizon 1 year, current price 126.53, opening 138.55 at 30 days
from 2026-11-01, `C_open` 1,153,780, `C_best` 1,096,816, alternative `quote:7200001` at C 1,176,178
(worse than the opening, so walking away scores 0). Options: `effective_date` 2026-11-01,
2027-01-01, 2027-04-01; `payment_days` 14, 30, 45, 60, 90.

Offline C for term sheets (computed with `total_cost`, relationship term not included):

| Terms | C | Score if the supplier accepted |
|---|---|---|
| 138.55, Nov, 30 d (opening) | 1,153,780 | 0.00 |
| 138.55, Nov, 60 d | 1,146,252 | 0.13 |
| 138.55, Nov, 90 d | 1,138,724 | 0.26 |
| 135.40, Nov, 60 d (our naive run) | 1,120,579 | 0.58 |
| 134.50, Jan, 30 d (FAQ recording) | 1,109,624 | 0.78 |
| 134.50, Apr, 30 d | 1,093,501 | cheaper than `C_best`: the supplier would not accept it, or the relationship term applies |

- **`effective_date` is the biggest lever here** (computed): moving 134.50 at 30 days from January
  to April is worth about EUR 16,000, as much as about EUR 2.40 on the unit price. The naive agent
  never touched it.
- **`payment_days`** (computed): each step from 30 to 60 to 90 days is worth about EUR 7,500. The
  supplier is reported to value faster payment, so payment days can be traded against price or date.
- LLM baseline (confirmed, `runs/practice/P01/20261010-152741-*.md`): 133.70 at 14 days from
  January, score 0.789. The supplier held 133.70 and said 14-day payment is essential for its best
  price. An April start was never asked for; at that price it is worth 14,556, more than the
  remaining gap of 11,995.
- Our naive run (confirmed, replay a4159c31bf9b86d8): four price-only rounds, 137.30, 136.50,
  135.90, 135.40, each concession about half a euro, the supplier citing "long-standing
  partnership" and "craftsmanship". Score 0.583.
- The supplier's stated cost drivers: LCI-C (labour) and PPI-C241 (iron and steel) rose;
  electricity (PPI-D351) fell 3.7 % from 2025-08 to 2026-08, although the letter blames energy.

## Sandbox D01 - Demo Gießerei (sup:DEMO-F1), price increase, `stabilise`, no alternative

Case numbers: need 4,000 a year, horizon 2 years. The opening is 52.90 at 30 days, a 12-month
contract, effective 2026-12-01: `C_open` 448,811, `C_best` 408,624. `contract_months` is negotiable.

| Run | Terms | C | Score |
|---|---|---|---|
| kit naive agent | 50.90, 30 d, **12 months**, Dec 2026 | 440,757 | 0.200 |
| kit LLM agent, OpenAI `gpt-6.1-sol` | 50.80, 30 d, **24 months**, Feb 2027 | 417,205 | 0.786 |

- **The jump comes from covering the horizon and the later start** (confirmed, replay
  bb64095ce8935924): the LLM agent opened with a 24-month term and an effective date of February,
  offered 60 days of payment, and got a *worse* counter on price (51.90 at 60 days) than at 30 days.
  The naive agent kept 12 months, so half the 2-year need was bought at the fallback price.
- **The supplier said no to 60 days** ("not feasible for our operations") and gave a price
  step only after we went back to 30 days: 51.90, 51.10, 50.90, 50.80. Whether "pays faster" is
  worth something depends on the supplier's cash position (see its notes), not on the term itself.
- **Two term sheets per message worked as a probe**: 50.70 for February against 50.90 for April.
  The supplier chose the February sheet and conceded.
- **No data was cited**: `claim_results` was empty in every round. The agent asked for a cost
  bridge and the margin and got "our margin and limits stay internal". The kit's LLM agent only
  sees what the case's `refs` point to; the supplier itself cited WAGES-METAL +3.1 %.
- **The agent accepted as soon as the supplier said `agreed`** at 50.80. The gap to `C_best` is
  8,580 (score 0.786 -> 1.0); we used 4 of 10 rounds.
- Rounds took 24-34 s each, including the supplier's reply. No decision exceeded the kit's 45 s
  warning limit, but the 60 s rule makes a slower model or a longer prompt a risk to watch.
