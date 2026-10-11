# sellm2 - team sellm's buyer agent, rewritten from scratch

`sellm2/` is a complete buyer agent for the Tacto Negotiation Arena: its own data layer, decision
logic, e-mails, runner and command line. It imports only the official kit (`arena_kit`) at runtime.
Built Sun 11 Oct 2026, 02:50-03:30, on `amiads_branch`, from everything the team measured on Saturday
(`docs/LOG.md`, `docs/LEARNINGS.md`, `experiments/*.md`).

**Measured:** full practice run **76.4** (`amiads_branch@dc028e5`, 10 hosted cases, own runner, no
LLM). For comparison: the kit's LLM agent 61.5, `main` 72.9, the best other branch 75.4.

| P01 | P02 | P03 | P04 | P05 | P07 | P08 | P10 | P11 | P18 |
|---|---|---|---|---|---|---|---|---|---|
| 0.969 | 0.725 | 0.923 | 0.860 | 0.820 | 0.747 | 0.549 | 0.671 | 0.778 | 0.598 |

## Run it

```bash
uv sync --all-extras          # once
uv run arena data             # the data package (again after the Sunday release)
cp .env.example .env          # ARENA_API_KEY=... (no LLM key needed: sellm2 calls no model)

uv run python -m sellm2 play P01 --label "what this run tests"     # one practice case (quota)
uv run python -m sellm2 run --set sandbox --cases D01 D02             # sandbox, free
uv run python -m sellm2 run --set practice --cases all --parallel 8   # all 10 hosted cases
uv run python -m sellm2 final --dry-run                               # check the final machine
nohup uv run python -m sellm2 final > runs/logs/final.out 2>&1 &      # the Live Final: start before wave 1
uv run python -m sellm2 replay --label 67001e7                        # offline: where we differ from a recorded run
uv run python -m sellm2 brief 70130                                   # what we know about a supplier
uv run python -m sellm2 stress                                        # lab stress test (no arena)
uv run pytest sellm2/tests                                            # 39 tests
```

Environment: `ARENA_URL`, `ARENA_API_KEY`, `ARENA_DATA` (default `data/package`). Logs:
`runs/logs/<time>-sellm2-<command>.log` (every move with its reasons) and `.jsonl` (one row per case).
Every run on the hosted arena first pulls the team's commits (`scripts/pull-first`); the final only
reports. Other runners also play it: `python -m sellm.runner --agent sellm2.agent:make_agent`.

## How it decides

Every move is a pure function of the case file and the e-mails: no state between moves, so a fresh
agent resumes any session, and identical states give identical e-mails (the practice suppliers then
answer identically, which makes `replay` a proof for unchanged cases).

1. **Prepare** (`knowledge/`, about 5 ms per supplier): from the data package, the Sunday release, the
   case file and the opening e-mails - the supplier's signals (short of cash, fixed list price, capacity
   tight, material hedged, wants volume, ...), its cash pressure and cost of money, the should-cost of
   its own plant, its 12-month low price, the contact's name, and every fact we may cite with our
   figure next to its ID (935 for the 46 known suppliers, all checked against `facts.json`).
2. **Structure** (`policy.opening_structure`): every term sheet the case allows, priced in our total
   cost C (the arena's own function) at the price the supplier would want for it. Payment days follow
   its cost of money (latest from suppliers that borrow cheaply, fastest from those short of cash or
   paying 15 % or more); lead time is priced only for capacity-tight suppliers; cover the horizon,
   longest contract where C does not care. After its first answer we follow its cheapest priced sheet.
3. **Price** (`policy.aim`, `policy.plan`): a target from its own cost (in strategic and bottleneck
   cases the price where C including the relationship term is lowest) or from a share of its opening
   read from its signals; first ask 6 % below (never a lowball to a capacity-tight supplier); each
   step sized so both prices meet after four of our messages given how much it has given back; stay
   just below its price so it makes the last move; never lower our own price.
4. **Argument**: one checked fact per e-mail, every round - a rival's cheaper offer, its own
   should-cost, a falling cost driver, a recent fall from the 12-month peak (never to a hedged
   supplier), then the bank by case type, one per topic.
5. **Close**: accept a final offer or an agreement (never ask after a final offer: 3 of 5 such pushes
   lost the deal), take its cheaper alternative sheet by sending it back, accept the cheapest valid
   standing offer when nothing is left to ask, walk away only to a better alternative. In strategic
   cases where its fixed price is at its cost, the index clause goes in as option B at the C-minimal
   price (P02 0.531 -> 0.725).

The runner plays one loop per case with one message in flight per session (the arena processes a
session's messages one at a time), a 40 s deadline per decision, re-reads a thread after a 409/422
(an offer replaced by a timeout, a supplier that left), holds only the best final offer, closes with
our own close before the wave's cap and resumes a session after a crash. It never calls the live feed.

## What was measured and dropped

LLM-written e-mails (71.6 vs 72.9, not repeatable), an LLM verdict on offers (P01, P18 worse), pushes
after a final offer (lost deals), horizon 6, lower first asks, ppm and lead time traded with suppliers
that do not price them (P11 0.620, P05 0.803). Details: `docs/LOG.md`, `docs/LEARNINGS.md`.
