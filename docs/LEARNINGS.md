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

## From the sandbox probes (Sat 15:42-15:57, 33 free sessions)

Evidence and tables: `experiments/RESULTS.md`. Measured on the sandbox's demo suppliers only.

- **Only the first term sheet of an e-mail can be accepted** (confirmed, 4 of 4: `422 not a
  standing offer`). To take a supplier's second package, send its exact terms back as our sheet;
  the supplier answers `agreed` and that sheet can be accepted (confirmed, 2 of 2).
- **A final offer is final** (confirmed, 8 sessions). Pushing the price after `final_offer` gained
  nothing and lost the deal once in two tries. A holding message without a term sheet keeps the
  offer alive and restarts the clock.
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
