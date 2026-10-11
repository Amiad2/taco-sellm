# LEDGER - Jonathan's night search on jonathans_branch (Sun 11 Oct 2026, from 03:00 CEST)

Jonathan's brief before he left (02:55): go on trying things and combinations, index arguments first,
and "special things as in P02" (a structure the supplier pays for); stop when the team has 100
practice sessions left (450 limit: used 350); change a little at a time and save every step so that
no good version is lost.

How a step is saved: the experiment runs on a pushed commit and its sessions carry
`jonathans_branch@<hash>` in their label; the row below names result and decision; an adopted change
gets tests, a `[change]` entry in `docs/LOG.md` (on `main`) and - when the mean moves - a full practice
run with a tag `best-jonathans_branch-<score>`. Reference for a single case is the last full run
(`jonathans_branch@b7b279e`, 75.4): P01 .969 P02 .725 P03 .923 P04 .860 P05 .820 P07 .747 P08 .549
P10 .647 P11 .778 P18 .520. Practice suppliers answer identical e-mails identically, so one session
per variant and case compares exactly; P05 (RFQ) varies with timing.

Earlier tonight (records: `experiments/P02-ARGUMENTS.md`, `docs/LOG.md`): clause offer P02 0.531 ->
0.725 (adopted); clause in the first ask P08/P18 (worse); the other source's order price P18
(`irrelevant`); cost breakdown asked P08/P18 (none sent); planner live, full run 75.4.

| ID | Hypothesis | Change | Case | Result (reference) | Decision | Version, session |
|---|---|---|---|---|---|---|
| J1 | A second cost-driver index that fell is a new fact (omars_branch cites one, assuming a second is a duplicate) | second e-mail: PPI-C2431 -2.3 % (2026-06 to 2026-08) instead of the dismissed fact | P18 | **0.598** (0.520): verified, "acknowledge its impact on our cost basis", closed 5.30 with the 5 % deadband | adopted as `idx_many=3` | `@a8bc950`, 413f68afe4d5598f |
| J1 | same, to the supplier whose alloy is hedged | as above | P08 | **0.560** (0.549): "adjusted our calculation accordingly" | hedge guard narrowed to the clause's series | `@a8bc950`, 3ebdeeb798f29bce |
| J2 | With `idx_many` the index comes before the forecast in P08: a new path | the built-in rule (`agent-idx`) | P08 | **0.637** (0.549): 5.52, 5.42, 5.31, 5.27 | adopted | `@8600f3f`, f619da40ff4745fe |
| J3 | The larger fall of an index helps where it answers the supplier's own reason (P01 +0.028 in Omar's E4) and not elsewhere (P11 -0.068) | planner names the blamed drivers; larger fall only for those (`idx_blamed`) | P01, P11 | by replay: P01 = Omar's E4 session 6d45cb41 (**0.997**), P11 = reference (0.778) | adopted, needs `SELLM_PLAN=llm` | replay, no session |
| - | The other approved source's order price is leverage | second e-mail: po lines of the other source for the same part | P18 | claim `irrelevant` ("does not concern this part or our company"); 0.598 by a lucky answer on the 5 % deadband | rejected: order lines count only with the supplier we talk to | `@0431f57`, 7d8fb3f093721d13 |
| - | Eleven suppliers "offered to walk us through their calculation": ask for the breakdown | first e-mail asks for the cost breakdown | P18, P08 | 0.520 (=), 0.515 (0.549); no XLSX: "more detail we do not share", "as a distributor ..." | rejected | `@6f1de17`, 3f7143e0af078edb, ceef38181210a072 |
| - | Planner: both letters propose an alloy clause, so offer it at once | clause (deadband 0 / 5) in the first ask | P08, P18 | 0.527 / 0.484 (0.549); 0.386 / 0.401 (0.467) | rejected: a clause the supplier demands is a move it pays for when taken later | `@0400b0b`, 0f3250ac, f8191a5c, 80380e16, 1847ba7c |
| J4 | Amiad's rule on this agent: a capacity-tight supplier answers a low first ask with its final offer | first ask >= 93 % of its opening where the dossier has `capacity_tight` (`no_lowball`) | P10 | **0.679** (0.647; sellm2 0.671): open at 33.6 / alt, final 31.5 with 56 days | adopted | `@c74d723`, b1e54e486bfbb175 |
| J5 | Suppliers on a ladder say final_offer after about four messages, so facts should come early: two in the first e-mail | `first_facts=2` | P18, P08 | 0.564 (0.598), 0.593 (0.637): the same first answer or a worse one, smaller steps after | rejected: one fact per e-mail | `@e0af192`, 2bdb002fe3dea9fc, f428ea736329802f |
| J6 | P18's supplier gives 0.10 for every 30 days it is paid sooner (its two-sheet answers) | first ask with 30 / 14 days payment | P18 | 0.603 (5.11 at 30 days), 0.606 (5.20 at 14 days) against 0.598 | not adopted: within a hundredth, it prices payment at about our own rate | `@d9e6957`, 82af6326fdc6fbb8, 5ad07f6ae3839b14 |
| J7 | P07 gets the final offer at our third e-mail because that one has no fact; order lines of the kit's parts are separate arguments | order history of two kit parts in e-mails 3 and 4 | P07 | 0.747 (=): verified, and still final at the third message, 5.41 | rejected: its patience is three messages whatever the third says | `@39672a0`, e93d45d42a375fac |
| J8 | The order history is dismissed because of what it says ("5.75 two years ago, 5.84 today"), not because it is history: the pair around the supplier's last price jump is an argument | scripted: third e-mail cites the last order at the old price and the latest one | P18, P08 | **0.657** (0.598): "verified the prices from June and September ... we can reduce our price", then agreed at 5.21. **0.659** (0.637): "took it into account", 5.28 instead of 5.31 | built into `sellm/claims.py` (`_po`): where the price rose >= 2 % within twelve months | `@e381ed8`, b8f073fc4b476df2, 24b3c399db70b112 |
| J9 | With the rule in the bank the fact comes earlier in P08 and exists for P03 for the first time | `--agent sellm` as it is (`agent`) | P08, P03, P18 | **P08 0.814** (0.637): second e-mail "5.17 in 2025-12, 5.45 in 2026-09" - it went from 5.52 to 5.17 at once, deal 5.11. **P03 0.956** (0.923): 430.71. P18 0.657 as scripted | adopted | `@e303538`, 3778b21e05901271, 26d30dbdbb5f5c1b, 622e183a563f67a0 |
| - | A cash-short supplier whose payment days are fixed says "faster payment would help us more than anything" in every e-mail: promise payment on the due date (we pay it 8.8 days late) | sentence after its request (`ontime`) | P11 | 0.710 (0.778): the same ladder 46.5, 46.0, 45.5 and a final offer at 45.5; the close at 45.09 of the reference path did not come | rejected: words do not buy price; P11's 0.778 hangs on one answer | `@539670e`, 4179c48e07748d3a |
| J10 | In an RFQ every message costs the other threads their clock (the arena answers a session's messages one after another); a bidder that cannot win should not be asked | `drop_behind=0.08`: not asked again once it has answered two asks and still costs 8 % more than the best other offer | P05 | the lost state replayed: accept 28.00 instead of a fourth ask to the bidder at 33.00; live 0.820, 0.820 (12 s each); in the full run 0.820 (13 s; before 203 s and 243 s with 0.872 / 0.717) | adopted | `@c4efa65`, 78bd2811a77e6731, b33e92e35279093d |

## Full runs (the versions to go back to)

| When | Version | How | Mean | Per case |
|---|---|---|---|---|
| Sun 02:25 | `jonathans_branch@67001e7`, tag `best-jonathans_branch-74.9` | kit runner, no LLM | 74.9 | P01 .969 P02 .725 P03 .923 P04 .860 P05 .820 P07 .747 P08 .549 P10 .647 P11 .778 P18 .467 |
| Sun 02:38 | `@b7b279e`, tag `-75.4` | kit runner, planner live | 75.4 | as above, P18 .520 (Omar's recent index fall) |
| Sun 03:12 | `@0eaf946`, tag `-77.3` | kit runner, planner live (P10, P11 singly after a 429) | 77.3 | P01 .997 P08 .637 P18 .598 |
| Sun 04:10 | `@79c2d0a`, tag `-78.2` | final runner, 10 in parallel, planner live | 78.2 | P10 .679, P05 .872 |
| Sun 04:25 | `@2caef7f`, tag `-79.3` | final runner, planner live | 79.3 | P03 .956 P08 .814 P18 .657, P05 .717 (a bidder timed out) |
| Sun 04:29 | `@8a854c4`, tag `-80.3` | final runner, planner live | **80.3** | P01 .997 P02 .725 P03 .956 P04 .860 P05 .820 P07 .747 P08 .814 P10 .679 P11 .778 P18 .657 |

## After the 80.3 run

| ID | Hypothesis | Change | Case | Result (reference) | Decision | Session |
|---|---|---|---|---|---|---|
| J11 | The strongest fact should come first: the price jump in the first e-mail, the indices after it | scripted order | P08, P18 | 0.803 (0.814), 0.542 (0.657) | rejected: indices first, then the jump, as the agent does | 5514dbc17dbe1c82, 6544c8c84fe5461b |
| - | Unplayed case files in the lab with the planner on (no arena session): how does the first e-mail look for suppliers we never met? | - | P06, P09, P12, P13, P14, P16 | a supplier that signs without a person was greeted "Dear Mit freundlichen Grüßen," | fixed in `sellm/writer.py` (`contact`), test; the fifteen real suppliers' names are read as before | - |
