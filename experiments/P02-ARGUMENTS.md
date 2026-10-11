# P02-ARGUMENTS - what moves a supplier that has stopped at its limit (Sun 01:20-02:10)

Jonathan's question: other teams close P02 (Nordmark, copper on the 7.5 kW motor) better than we
do, although a lower first ask does not help - so their e-mails must argue better. Collect arguments
from the dossier, the letters and the cost calculation and test three to five of them.

**Result: P02 0.531 -> 0.725 with `--agent sellm` on `jonathans_branch@a49c9b4`.** The lever is not
a better sentence. It is the copper index clause, offered at the price where our total cost is
lowest. Eight practice sessions; runner and variants: `experiments/p02_arguments.py`; rows:
`experiments/results/2026-10-11-p02-arguments.json`; sessions: `runs/practice/P02/`, labels `P02 ARG ...`.

## 1. Where P02 stood

More than ten sessions of four different agents (first ask from 296.77 to 354.43, one to three
facts per e-mail, warm, plain and coercive wording, past renewals, an LLM writing) ended between
371.66 and 371.85 with 90 days, score 0.51-0.53. What the supplier does on a fixed price:

| Our e-mail | Its step (worth to it, EUR) | Its words |
|---|---|---|
| no fact | -0.36 to -0.46 a round, final offer after four messages at 373.65 (0.293) | - |
| order prices 2024 and 2026 (`po`) | -1.11 | "it holds and we took it into account" |
| forecast +11.9 % (`fc`) | -1.91 | "factored this volume increase into our calculation" |
| on-time delivery 90.4 % (`sc`) | -0.21 or 0 | "only allows a small further concession" / "does not change our calculation" |
| complaint (`qn`, `duplicate`) | -0.16 or 0, then `final_offer` | "already taken into account" |

In whatever order: the sum stops at 371.66 with 90 days, and then "below this price we would need
facts, not just a lower number".

## 2. The eight sessions

Each variant is `--agent sellm` plus one change; prices, steps and the close stay the agent's.

| Variant | What was added | Result | Reading |
|---|---|---|---|
| `clause5` | first ask with the CU-NOTATION clause, 5 % deadband, at our usual low price (343.47) | it answered 351.45 at once; taken: **0.242** | it pays 5.3 % for the clause; the arena then charged a relationship cost of EUR 119,974 |
| `market` | producer prices of electric motors +1.6 % (`idx:PPI-C2711`), electricity -3.7 % (`idx:PPI-D351`) | 0.394 (372.85) | both `irrelevant`; the forecast in the same e-mail moved it 0.46 instead of 1.91; final offer one message earlier |
| `sister` | order prices and forecast of the 4 kW motor we also buy from it; the contract's 95 % delivery target | 0.319 (373.45) | both `irrelevant`, same damage |
| `volume` | its question "which volume can you commit to?" answered: the contract's 6,110 units are binding, plus a call-off schedule | 0.525 (371.72) | no effect |
| `committee` | the dossier's approval ladder: "please put our proposal before your pricing committee, we are glad to wait" | 0.480 (372.12) | slightly worse |
| `clause5-direct` | first ask 361.35 with the clause (the price of lowest total cost, section 3) | **0.735**: it agreed in its first reply | "an index clause for copper aligns with our mutual interest in risk mitigation" |
| `clause5-raise` | first ask 343.47 with the clause; after its 351.45 we asked 361.35 twice | 0.242: it held 351.45 | "our offer of EUR 351.45 is economically viable and remains our official position" |
| `agent-clause` | the rule as built in (section 4): two sheets, the usual fixed-price ask and the clause at 362.70 | **0.725**: it agreed to the clause sheet at once | the price came from our own estimate, no number of this case in the code |

Not tested, because the data already answers it: faster payment (it chose the 90-day sheet over an
equal-cost 30-day sheet in the session without a dossier, so money is worth less to it than our
8 %), the second-source quote (421.06, dearer than its offer: citing it shows our alternative is
worse), our should-cost (374.95, above its price: it argues for the supplier).

## 3. Why the price has to be chosen

Two deals carry a relationship charge: 822.73 at 371.66 / 90 days fixed, and 119,974.28 at 351.45 /
90 days with the clause. A full cost of **EUR 367.56** at a cost of money of **6.67 %** (the rate
between its own 30- and 90-day sheets) reproduces both to the euro. So:

- 371.66 with 90 days is worth 367.56 to it: the fixed-price wall is its cost floor. No argument,
  tone or first ask goes below it; the brief says so ("never sells below its cost floor").
- A clause is "security, not cash" in the arena's margin. Nordmark gives 5.3 % of the price for it;
  the relationship term then counts the deal as 5.8 % below full cost.
- Total cost with the clause (5 % deadband, 90 days) by price: 351.45 -> 0.243, 356 -> 0.565,
  358 -> 0.670, 360 -> 0.725, **361.35 -> 0.735**, 362.70 -> 0.725, 364 -> 0.695, 366 -> 0.612,
  368 -> 0.486. Below 361 every euro off the price costs more in the relationship term than it saves.
- The other clauses cost us more and gain nothing: best 0.549 with the 3 % deadband, 0.269 without one.
- It never raises a price it has named. The first ask on the clause decides.

Still open: `C_best` lies EUR 12,500 below the best clause deal. On a fixed price that is about
365.95 with 90 days, 1.5 % below its full cost. Nothing tried reaches it.

## 4. The rule in the agent (`clause_offer`, `sellm/endgame.py`)

Conditions, all read from the case and our data:

1. the category goal has a relationship term (`stabilise`, `secure_supply`),
2. `index_clause` is negotiable and the supplier's opening quotes a fixed price,
3. a should-cost of its own plant leaves its opening no more than the sustainable margin. Then a
   fixed price has no room by our own data, and the cost we price the clause with is the highest its
   own quote allows (its opening less the sustainable margin). With a clause its price no longer
   stops at its cost, so an estimate that is too low would squeeze it without anyone noticing.

Then the first e-mail carries two sheets: the usual fixed-price ask, and the clause variant that
costs us least at the price where our total cost, relationship term included, is lowest - provided
that beats the fixed price at which the supplier just covers its cost. One sentence explains the
clause. If the supplier agrees to it, the agent accepts; if it answers on the fixed price, the
negotiation goes on as before; a clause it prices below ours is neither taken while the thread is
open nor followed.

Checks: of the recorded cases only P02 meets the conditions; P01, P03, P04, P07, P08, P10, P11, P18
and D01 are played move for move as without the rule (`tests/test_endgame.py`). P14 (not hosted:
cable with a copper clause, `stabilise`) opens with a clause and is not touched. Practice mean by
replay: 72.9 -> 74.8.

What the rule assumes and where it can be wrong on a hidden supplier:

- That the supplier's opening earns at least the sustainable margin (true in D01, P01, P02, P03,
  P10). If its opening were below that, our clause price would be too low and the relationship
  term would cost more than computed.
- That a supplier asked above its own price agrees instead of undercutting (seen twice on P02).
- A supplier that does not want the clause answers on the fixed price; the cost is one sentence.

## 5. For the pitch

"Why did your agent write that?" - it offered a copper clause and then asked for a higher price
than the supplier would have given, because the case's own cost function says a healthy supplier is
worth more than the last euro. Replay: https://arena.tacto.ai/replay/411824454914aa5f; the
counter-example, where the low price was taken: https://arena.tacto.ai/replay/70bff38632e765de.
