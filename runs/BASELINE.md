# Baseline: the kit's LLM agent on all 10 hosted practice cases

Sat 2026-10-10 15:27-15:31 CEST. `uv run arena run --set practice --agent llm --parallel 10 -v`
with the kit's agent unchanged (repo at `6ba71cd`), OpenAI `gpt-6.1-sol`. Ten sessions, quota 199
-> 189. No `LLM failed`, no fallback to the naive move. Run log:
`runs/logs/2026-10-10-1527-baseline-kit-llm.log`. Every session in full: `runs/practice/<case>/`,
index in `runs/README.md`.

**Mean score 61.5.** This is the number our own agent has to beat.

## Results

"Our messages" counts negotiating e-mails before the accept; the limit is 10 per thread.

| Case | Type / goal | Score | Our messages | Supplier's last status | Deal | Gap to C_best | Mostly lost on |
|---|---|---|---|---|---|---|---|
| P02 | price_increase / stabilise | **0.105** | 4 | final_offer | 370.15, 30 d, no index clause | 42,371 | payment term (90 d is worth 30,155) and price |
| P18 | raw_material / leverage | **0.377** | 3 | final_offer | 5.60, index clause, 60 d, 24 m | 45,178 | price (C_best is at about 4.73) |
| P08 | raw_material / leverage | **0.433** | 5 | final_offer | 5.54, index clause, 60 d, 36 m | 99,528 | price (C_best is at about 5.10) |
| P10 | capacity / secure_supply | 0.570 | 2 | final_offer | 33.60, 23,400/y, 36 m, 42 d lead time | 259,372 | price; took the dearer of two packages |
| P05 | rfq / leverage | 0.676 | 1-4 per thread | final_offer | 29.50, 30 d, 35 d lead time (sup:70250) | 26,592 | price; timeouts on the other threads |
| P11 | quality / quality_first | 0.710 | 5 | agreed | 45.50, 300 ppm, chargeback 0 | 27,582 | price |
| P07 | bundling / routine | 0.779 | 4 | final_offer | 5.36, 90 d, 24 m | 20,243 | price |
| P01 | price_increase / stabilise | 0.789 | 5 | open (held its price twice) | 133.70, 14 d, from Jan 2027 | 11,995 | start date (April is worth 14,556) |
| P04 | renewal / routine | 0.810 | 3 | final_offer | 4.91, 60 d, 24 m | 441 | payment term (90 d is worth 1,309) |
| P03 | renewal / stabilise | 0.903 | 4 | open | 432.94, 90 d, 36 m, 4,580/y | 32,587 | price |

Score points lost, of 10 possible: 3.85. Three cases (P02, P18, P08) account for 2.09 of them.

## What the baseline shows

Each finding says how sure it is: **seen** in these sessions, **computed** offline with the cost
function, or **open** (a hypothesis).

### 1. The agent stops as soon as the supplier stops moving (seen, all cases)

It accepted on the first `final_offer` (7 cases), on `agreed` (P11) or when the supplier repeated
its price (P01, P03). It used 2 to 5 of its 10 messages; in P10 it accepted after two. It never
tests whether a final offer is final, and never brings a new trade once the supplier says "final". What a supplier does
when we answer a final offer with a different package instead of a lower price is **open**: test
it in the sandbox before building on it.

### 2. It looks only at the supplier's first term sheet (seen; cost computed)

Suppliers often send two packages in one e-mail; alternatives appeared in 11 of 12 threads. The
kit's `standing()` reads `term_sheets[0]` and never prices the second.

- **P10**: Ravensteiner offered 33.80 with 42 days lead time, and as the alternative
  (`offer:70410-1-a`) 32.00 with 54 days. The alternative costs C 1,541,719 (score 0.647). The
  agent insisted on 42 days and closed at 33.60, C 1,588,298 (score 0.570). It paid 1.60 more per
  seal on 46,800 seals (the two years that count), about 74,900, to save 12 days of lead time
  that cost us 2,400 a day, about 28,800.
- **P02**: 372.30 at 60 days was on the table and is cheaper for us than the accepted 370.15 at 30 days.

Rule for our agent: price **every** sheet a supplier sends and compare by C, not by unit price.
Whether an alternative can be accepted by its ID (`...-a`) in the same or a later round is **open**.

### 3. An RFQ handled thread by thread times out (seen, P05)

`play()` sends one message and waits for the reply while the other threads' 60-second clocks run.
P05 recorded two timeouts on sup:70210, two on sup:70250, and sup:70240 - the cheapest opening at
31.50 - withdrew after a late message. The timeout replies read "Without movement from your side
we cannot move either." We closed with the supplier that had opened highest (38.50 -> 29.50).
C_best corresponds to about 26.71. The runner must write to all threads of a case in parallel.

### 4. Data arguments are barely used, and repeated (seen)

Across 12 threads: 8 claims `verified`, 8 `duplicate`, 0 `contradicted`. Three cases had none at
all (P05, P07, P08). The duplicates are the same ID cited again in a later e-mail, which earns
nothing. Suppliers asked for data outright - "Which figures is that based on? Please send us the
data." in P03, P05 and P10, "Please provide the data supporting your assumptions" in P04 - and the
agent had nothing to send, because it only sees what the case's `refs` point to.

### 5. Should-cost is the missing price anchor (computed)

Price at C_best with the best non-price terms (relationship term not included, so slightly low for
`stabilise` and `secure_supply`), against the should-cost estimate where one exists for the
supplier's own plant:

| Case | Should-cost | Current price | Opening | Our deal | Price at C_best | Deal / should-cost | C_best / should-cost |
|---|---|---|---|---|---|---|---|
| P01 | 132.64 | 126.53 | 138.55 | 133.70 | 138.2 (with April start and 90 d) | 1.01 | 1.04 |
| P02 | 374.95 | 348.32 | 370.96 | 370.15 | 368.1 | 0.99 | 0.98 |
| P03 | 403.21 | 412.74 | 438.21 | 432.94 | 429.4 | 1.07 | 1.07 |
| P10 | 24.31 | 29.89 | 32.20 | 33.60 | 28.1 | **1.38** | 1.16 |
| P05 | 36.87 (generic, German cost base) | 36.39 | 31.50-38.50 | 29.50 | 26.7 | 0.80 | 0.72 |

For the four cases with a plant-specific estimate, C_best sits between 0.98 and 1.16 times
should-cost. That gives a target before the first e-mail. In P10 we paid 38 % above the supplier's
estimated full cost and never cited `cost:340010`. P05's suppliers include a Czech shop, which the
company's rule of thumb puts at 0.8-0.85 of the German cost base. Cases without a should-cost row
(P04, P07, P08, P11, P18) need another anchor: **open**.

### 6. Non-price terms: what was left, and one trade that worked (computed)

- **P01**: an April start was never asked for. At the deal's price and 14-day payment it is worth
  14,556, more than the whole gap of 11,995. The supplier said "the 14-day payment term is essential
  for us to offer our best price": it wants cash. Keep 14 days, ask for April.
- **P02**: 90 instead of 30 days is worth 30,155 of the 42,371 gap. Nordmark prices longer terms
  ("the premium for extended payment terms is reflected in the price difference between the
  packages"), so the question is whether its premium is smaller than our gain. From its two
  packages: 2.15 per unit for 30 more days, about 13,100, against 15,100 for us.
- **P08, P18**: the case expects the alloy index to rise 6 %, so an index clause costs us. No clause
  is worth 9,453 (P08) and 2,389 (P18); 90-day payment 7,003 and 1,770. Werdenfels refused a fixed
  price for 24 months ("indexation is necessary to manage material volatility").
- **P11, a trade that worked**: the agent gave up the chargeback (500 -> 0 per complaint, worth
  2,146 to us) and got 1.00 off the price (worth 15,900). Give what is cheap for us and valuable to them.
- **Coverage was right everywhere**: no case lost points on uncovered need. The LLM handles this;
  the naive agent did not (D01).

### 7. Where C_best is far below anything we argued for (open)

P18: C_best is at about 4.73, 19 % below the *current* price of 5.84. P08: 5.10 against 5.45.
P10: 28.1 against 29.89. In these cases the supplier would accept far less than it shows, and we
do not know yet which fact unlocks it. Candidates to check in the data before spending sessions:
the split between base price and alloy surcharge (the P08/P18 titles name it), Donautal's remark
that its material "is covered at fixed prices until March", the second-source quotes, the notes
and letters of these three suppliers. The alloy index itself rose 5.9 % in twelve months
(2,839.7 in 2025-09 to 3,007.8 in 2026-09) but fell 5.5 % since June.

### 8. The relationship term is small so far (seen)

Charged by the arena: P01 813, P03 337, P02 0, P10 0. None of the baseline deals squeezed a
strategic supplier. There is room on price before that term matters.

### 9. Time is fine for single-supplier cases (seen)

Ten cases in parallel finished in four minutes. A round takes about 30 s including the supplier's
reply. Using all ten rounds would take about five to six minutes per case, close to the limit of a
final wave (6.5 usable minutes).

## Hypotheses to test, cheapest first

| # | Hypothesis | How | Cost |
|---|---|---|---|
| H1 | A supplier's alternative sheet can be accepted by its ID | sandbox D01 or D02 | free |
| H2 | Answering `final_offer` with a different package (not a lower price) gets another move instead of a walk-away | sandbox | free |
| H3 | Writing to all RFQ threads in parallel removes the timeouts and keeps the cheapest bidder in | sandbox D02, then P05 | free, then 1 |
| H4 | P01: keeping 14-day payment and asking for an April start reaches about 1.0 | P01 | 1 |
| H5 | P10: taking the 54-day package and citing `cost:340010` (24.31) beats 0.647 | P10 | 1 |
| H6 | P02: asking for 90 days and pricing every package by C lifts the score above 0.5 | P02 | 1 |
| H7 | P08/P18: there is a fact in the data that justifies a base price well below today's | data first, then 1 each | 0, then 2 |

Record each result in `docs/LEARNINGS.md` and log it as a `[run]`.
