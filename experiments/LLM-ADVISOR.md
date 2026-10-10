# LLM-ADVISOR - the LLM around the code's moves, measured on practice (Sat 23:55 - Sun 00:10)

Jonathan asked for a full practice run with the LLM, tool calling, and a decision with a confidence
on whether to take the supplier's offer, tested on five random cases. 15 practice sessions.
Code: `sellm/advisor.py` (`SELLM_LLM=shadow|apply`, off by default), `sellm/llm.py:chat_tools`, the
e-mail writer of `experiments/llm_writer.py` (Omar). Model `gpt-6-sol`. Rows and every verdict:
`experiments/results/2026-10-11-llm-advisor.json`. Sessions: `runs/practice`, labels `... LLM writer ...`.

## What the model does

1. It writes the e-mail around the move code has fixed (guards: required sentences word for word,
   no new figure, no leak; else the template).
2. It gives a verdict on the supplier's standing offer, A = take it now, B = keep negotiating. It
   can call three functions first: the calculator's cost of any price, the dossier's profile of
   the supplier, the checked facts we have left. The confidence is the probability the model puts on
   its letter, read from the token probabilities - computed, not asked.

## Results

Full run, LLM writes every e-mail, verdict logged only (`shadow`); reference = the same agent with
template e-mails (v1.4 run of 21:58; P01 from the test with both new rules):

| Case | LLM e-mails | template | |
|---|---|---|---|
| P01 | 0.984 | 0.969 | +0.015 |
| P02 | 0.515 | 0.531 | -0.016 |
| P03 | 0.933 | 0.923 | +0.010 |
| P04 | 0.860 | 0.860 | 0 |
| P05 | 0.820 | 0.820 | 0 |
| P07 | 0.766 | 0.747 | +0.019 |
| P08 | 0.493 | 0.549 | -0.056 |
| P10 | 0.562 | 0.647 | -0.085 |
| P11 | 0.778 | 0.778 | 0 |
| P18 | 0.446 | 0.467 | -0.021 |
| **mean** | **71.6** | **72.9** | -1.3 |

- The writer worked as built: 45 of 45 e-mails by the model, none rejected by the guards, 4.3 s
  median (5.5 s max). Verdict: 53, 2.4 s median (4.1 s max), no failure. A move took 6-8 s.
- The wording changes what the supplier answers, in both directions. P10: after the model's e-mail
  the supplier sent its final offer without the second sheet that the template run had sent back
  for 31.90 (0.562 against 0.647).
- With the model writing, a case no longer repeats: P07 scored 0.766 in the full run and 0.740 in
  the next session, P02 0.515 and 0.531.

The verdict:

- Shadow run: 48 of 53 verdicts agree with code (B while code asks, A at a final offer or an
  agreement, each with a probability of 0.86 or more). 5 say "take it now" while code kept asking,
  in P03 (three times; the session ended at the same score) and P01 (twice; after two messages at
  135.60 with p = 0.95, where taking it scores 0.898 and the session went on to 0.984).
- Applied in five cases drawn at random (P01, P02, P05, P07, P18), a sure A (0.85+) before the final
  offer accepts at once: it acted twice. **P01: accepted 135.50 after two messages, 0.864 (0.984 in
  shadow). P18: accepted 5.60 after three messages, 0.401 (0.446).** P02 0.531 and P07 0.740: no
  verdict acted.
- P05 in that batch: 0.250. Not the verdict - all three threads timed out (two bidders withdrew)
  with the kit's one-thread-at-a-time runner while five sessions and the model's 6-8 s per move
  ran. The same agent had 0.820 in the full run. An RFQ with a model in the loop needs the
  runner with one loop per thread, or no model.

## Reading

- An early accept can only give up concessions: in about 270 sessions no supplier withdrew before
  its own final offer. So "take it now" has nothing to win before a final offer, and after one code
  accepts anyway.
- The model's reason in P01 was our own cost function: "a further price cut could raise our
  total cost" - the relationship estimate that is 2 % too high there (experiments/PERSISTENCE.md, P1).
  A verdict built on our numbers repeats their error with confidence 0.95.
- Not adopted: the model as writer (-1.3 on the mean, and results stop being repeatable) and the
  verdict as a decision. The layer stays in the repo, off. What it is good for as it is: one
  logged sentence per move on why to take an offer or not, at 2-4 s, without touching the move.
