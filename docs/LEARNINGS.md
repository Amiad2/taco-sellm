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
- Our naive run (confirmed, replay a4159c31bf9b86d8): four price-only rounds, 137.30, 136.50,
  135.90, 135.40, each concession about half a euro, the supplier citing "long-standing
  partnership" and "craftsmanship". Score 0.583.
- The supplier's stated cost drivers: LCI-C (labour) and PPI-C241 (iron and steel) rose;
  electricity (PPI-D351) fell 3.7 % from 2025-08 to 2026-08, although the letter blames energy.
