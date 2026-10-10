# PERSONA-READER - can the model tell a supplier's persona without our dossier? (Sun 00:50, offline)

Question behind it (Jonathan): let an LLM (or a decision model such as jev) read the supplier and
pick the fitting strategy. For the 46 suppliers with a dossier the agent already does that by rule
(`sellm/personas.py`). The open case is a supplier we hold no data on: there the agent has only the
case text and what the supplier writes. Can the model recover the persona from that?

Test (`experiments/persona_reader.py`, no arena session, 96 short calls, `gpt-6-sol`): four yes/no
questions per practice supplier (12 suppliers), answered from the briefing and the opening e-mail
(v1) and with the supplier's next two e-mails added (v2). Truth = what the dossier says. The
confidence is the probability of the answer letter, from the token probabilities.
Rows: `experiments/results/2026-10-11-persona-reader.json`.

| Question | v1 right | v2 right | "yes" in the dossier | always answering "no" |
|---|---|---|---|---|
| short of cash | 8/12 | 6/12 | 4 | 8/12 |
| fixed list price or margin at its floor | 7/12 | 7/12 | 5 | 7/12 |
| hungry for volume | 10/12 | 8/12 | 2 | 10/12 |
| approval ladder | 7/12 | 7/12 | 6 | 6/12 |
| **all** | **32/48** | **28/48** | | 31/48 |

- The model is no better than answering "no" to everything, and it is sure when it is wrong: 16
  of 16 errors in v1 and 19 of 20 in v2 carry a probability of 0.8 or more.
- More text made it worse. After we ask for 90 days, a supplier writes about "financing costs", and
  the model reads that as short of cash (P02 0.93, P04 0.85), which neither the dossier nor the rate
  measured from its own offers supports (6.6 % and 7.3 %).
- What the personas rest on is not in the e-mails: the request to be paid within ten days is in a
  letter of September, the fixed list price in a quote remark, the committee in a call note.

So: no LLM-read persona for unknown suppliers. For them the agent keeps the two offers of equal
cost and follows the one the supplier answers - the supplier's own choice is the better reading.
A decision model with calibrated probabilities would not change this: the information is missing
from its input, not from the model.
