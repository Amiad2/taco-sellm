# Presentation brainstorm: intro slide, targeted arguments, our edge, and why `jonathans_branch` is the version

Written Sun 11 Oct 2026, 10:05 CEST, updated 10:15 (Jonathan's corrected memo transcript, his second point, and
the new full run 81.1), by Jonathan's Claude Code, for Jonathan, Amiad, Omar and every agent that works on the
pitch. **The pitch and the slides are in English.** This is a brainstorm: every number is sourced to a file in
this repo, opinions are marked *Opinion*. It complements Amiad's deck (`sellm-pitch.pdf`, 7 slides, LOG Sun 09:18
and 09:26) and does not replace it.

Jonathan's voice memo has two points: **point 1** is the intro slide on our agent memory system (section 2),
**point 2** is "use arguments in a targeted way", which belongs on the Highlight 2 slide of the deck
(section 3.3). **The two slides are built: `pitch-additions.pdf` in the repo root** (page 1 the memory system, page 2 "The same fact, the right supplier", the companion of Highlight 2; `sellm-pitch.pdf` is unchanged). The built memory slide shows the memory as one tall store with the three agents beside it, so the "visual idea" in 2.2 is superseded.

Rule for everything below: **no number on a slide that is not in `docs/LOG.md`, `docs/STATUS.md` or
`experiments/LEDGER-JONATHAN.md`.** Practice scores are in-sample (section 6).

## 0. Short version

1. **Intro slide (memo point 1):** "Six eyes, three agents, one memory." Logs, status and a shared memory kept
   three people and their three agents consistent, so nobody built around anybody and nothing was lost; that is
   also why the score went up version by version instead of jumping up and down. Section 2.
2. **Targeted arguments (memo point 2):** not more arguments but the right one, for this supplier, at this
   moment, one checked fact per e-mail. Same data, the right two rows (Highlight 2: P08 0.433 -> 0.814); same
   fact, other supplier: it cost 0.111 where the material was hedged. Section 3.3.
3. **The edge has two halves of about equal size.** Of the 19.6 points from 61.5 to 81.1, about 9.5 came from
   *what we ask for* (structure and trades priced by the arena's own cost function) and about 10.1 from *what we
   say* (one checked fact per e-mail, chosen per supplier by the dossier). Section 3.
4. **Why `jonathans_branch` beats everything else we built:** it is the only version that has all three of:
   exact total-cost structure (calculator), a per-supplier dossier that decides *which* fact and *which* trade a
   supplier takes, and the rules learned from reading real replies. `omars_branch` (75.4) is a subset of it;
   `sellm2` (76.4) lacks the price-jump pair and the second index on P08. Section 4.
5. **The newest measured version is 81.1** (`jonathans_branch@f1c3fb9`, Sun 09:57, tag
   `best-jonathans_branch-81.1`; again 81.1 at 10:11 and 10:22), 80.3 before it (`@363b6e6`). **`main` is that
   agent since 10:39** (`jonathans_branch@49eebc9`). Amiad's deck still says 80.3. The rule that carried
   77.3 -> 80.3 is the price-jump order pair (`_po`); 80.3 -> 81.1 is `hold_fixed` (P18 0.657 -> 0.729).
6. **Fix before showing:** the "0.72 %" simulator claim has a narrower scope than the slide implies, "What others
   don't do" says something we cannot know about other teams, and the slot length differs between files
   (section 9).

## 1. What we know about the pitch

| Fact | Source |
|---|---|
| Top 10 pitch from 13:00. `docs/CONTEXT.md` and `brief/submission.md` say **5 min + 2 min questions**, strictly timed. Amiad's deck (LOG Sun 09:26) is cut for a **3-minute slot**. Which one is right is not written anywhere in the repo: confirm at the Tacto desk. This file gives both cuts (section 7). | `brief/submission.md`, LOG Sun 09:26 |
| "Pick one negotiation and walk through its replay." Final-case replays appear after the final. | `brief/submission.md` |
| Questions to expect: *Why did your agent write that? Would it have worked on a real supplier? What did your agent learn about suppliers, and from where?* | `brief/submission.md` |
| Draft jury criteria: approach, explainability, craft. Weighting against the final score is still a placeholder (Q2). | `docs/CONTEXT.md` section 3 |
| Submission needs the commit hash the agent runs. README still says `_TODO_`. | `README.md` |

## 2. Point 1, intro slide: the agent memory system

### 2.1 What the memo says (Jonathan's own transcript, Sun 10:0x)

> So, the first thing we actually did was to set up our agent system with logs and status and the memory system,
> that our agents are always consistent with the things that we are building right now. Which allows us to move
> quicker and with more confidence, so we don't build around each other, because the agents always know what the
> other agent is doing. This was a huge advantage, because we always had six eyes basically looking over our
> work, which is mine, Amiad's and Omar's, and our three agents working in parallel, because the tasks are
> divided equally and efficiently without the agents getting into their way and without losing any of the memory
> and context that we have worked for the last hours, that is also why we were able to improve consistently
> instead of jumping up and down.

(Replaces the machine transcript of the Voice Memos app, which was garbled.)

Claims in it, and what stands behind each:

| Claim | Stands on |
|---|---|
| Logs and status, so agents are consistent with what we build right now | `docs/STATUS.md`, `docs/LOG.md`, SessionStart hook prints both |
| Agents always know what the other agent is doing | claims table in STATUS, `scripts/log`, `runs/`, `pull-first` before every run |
| Six eyes: three people, three agents in parallel | three authors on three machines, three branches; Jonathan's, Omar's and Amiad's Claude Code sessions |
| Tasks divided equally and efficiently, no getting in each other's way | `docs/PLAN.md` section 3 (groups A, B, C), one branch per person, shared files on `main` |
| Nothing lost of memory and context from the last hours | append-only LOG, handoffs, `runs/` with every session in full, tags `best-*` |
| We improved consistently instead of jumping up and down | ten measured versions of the main line in a row, none worse than the one before: 67.5, 72.4, 72.9, 74.9, 75.4, 77.3, 78.2, 79.3, 80.3, 81.1 (STATUS scoreboard, LEDGER-JONATHAN full-runs table; side experiments such as the LLM writer at 71.6 are not versions of the line) |

The last claim needs one honest sentence: the only jump down, 61.5 -> 53.2 at Sat 20:38, was our first own agent
tuned on sandbox and lab; it was logged, found by the practice run, and fixed 28 minutes later (67.5 at 21:06).
The rule "judge by a full practice run" came out of it. Show the red bar, as Amiad's chart does: it makes
"consistently" credible.

### 2.2 The slide

*Opinion: title options, in order of preference.*

1. **Six eyes, three agents, one memory.** (Matches the memo; short enough for a slide.)
2. We built the team's memory before we built the agent. (True: first commit Sat 14:02, "Add team memory and
   working protocol for all agents" Sat 14:44; our own negotiator played its first practice run at 20:32.)
3. One repo, one memory: agents that always know what the others are doing.

Body, three blocks (one line each on the slide, the rest in speaker notes):

| Block | On the slide | Behind it (verifiable) |
|---|---|---|
| **Shared state** | STATUS: who does what. LOG: typed, append-only. runs/: every session in full. | `docs/STATUS.md` claims table; `docs/LOG.md` with `[run] [change] [finding] [decision] [handoff]`; `runs/` = saved sessions with transcripts and the supplier's reasons |
| **Enforced by hooks, not discipline** | A new session starts with the live state; a session cannot end with unlogged or unpushed work. | SessionStart hook `scripts/session-start` (time to freeze, git state, last commits, STATUS, newest LOG); Stop hook `scripts/stop-check` blocks ending with uncommitted or unpushed changes or no LOG entry |
| **Every result names its commit** | `<branch>@<hash>` on every run; tags `best-*`; any better version can be restored. | `AGENTS.md` section 2; `scripts/pull-first` is built into `arena play/run` and restarts the run on the team's newest code; 12 `best-*` tags |

Numbers that are safe to put on it (counted from the repo at about 10:00): **320+ commits** by three people
(Jonathan 154, Omar 101, Amiad 65 at 09:51) from **three machines** (MacBook, Fedora, Yoga) on **three
independent branches**; **about 185 typed log entries** (66 `[run]`, 56 `[change]`, 42 `[finding]`, 13
`[decision]`, 8 `[handoff]`); **475+ saved sessions** (Amiad's deck says 451, counted at 09:18; the number grows
with every run, so recount before the slide is final: `ls runs/practice/*/*.json runs/sandbox/*/*.json | wc -l`);
**12 `best-*` tags**.

Visual idea: three laptops, each with a person and an agent (six eyes, three agents), one box in the middle
(`docs/STATUS`, `docs/LOG`, `runs/`, `main` + 3 branches), and the loop around it:
`sync -> claim -> change -> log -> commit -> push`. Hooks as two small icons on the loop (start, stop). Optional
strip at the bottom: the version bars 67.5 -> 81.1 with "ten in a row, none worse".

### 2.3 Speaker notes (about 25 seconds)

"The first thing we built was not the agent but its memory: logs, a status file and a shared record of every
run. Three of us, three agents, six eyes on the same work, and every agent starts a session by reading what the
others did and decided. It cannot end a session with unlogged work, and every result names the commit that
produced it. That is why we never built around each other, never lost context over seventeen hours, and why the
score went up version by version instead of jumping up and down."

### 2.4 Proof that it worked (use one, not all)

- **Rules travelled between branches without re-testing.** Omar's hedge guard and the one-loop-per-case runner,
  and Amiad's no-lowball rule for capacity-tight suppliers, are in `jonathans_branch` with their measured
  numbers (`experiments/LEDGER.md` on `omars_branch`, J4 in `LEDGER-JONATHAN.md`, STATUS "In progress").
  Omar's check after merging main: 137 recorded states replay unchanged.
- **A teammate withdrew a proposal on the evidence.** Amiad's LOG entry of Sun 08:59: sellm2 stays a fallback
  because `jonathans_branch` measured 80.3 against 76.4. That only works when the numbers are in one place.
- **Quota was not burned twice.** "Before you play a case, read its earlier sessions in `runs/`"
  (`AGENTS.md`), plus replay of recorded sessions to see which case a variant changes: 30 sessions instead of 70
  (`experiments/PRACTICE-ARMS.md`).
- **The wrong-version problem was designed out.** "Pull before every run" is built into the run commands
  (LOG decision, `scripts/pull-first`): a score cannot be credited to the wrong code.
- **A wrong turn was caught in half an hour.** 53.2 at 20:38, its cause named in the log, 67.5 at 21:06.

### 2.5 What to leave out or fix first

- Do not claim that agents "never" collide. The system makes sure they always know what the others are doing
  (claims, log, pull before every run); it does not make a shared checkout safe by itself. Say "always know",
  not "never conflict".
- Before any STATUS screenshot: the "In progress" table still lists claims that are 8 to 12 hours old (Amiad
  group C, playbooks, Codex P02 repair). Clean them or do not show the table.
- Entire session checkpoints are pushed to origin since Sun 10:42 (LOG decision by Amiad, 56 checkpoints searched for keys first). They can still hold internal prompts: do not put a transcript on a slide without reading it first.

## 3. Where our edge is

### 3.1 Where the 19.6 points came from

Sequence of measured full practice runs (all 10 cases, mean x 100; `docs/STATUS.md` scoreboard,
`experiments/LEDGER-JONATHAN.md`). Attribution is by step in the order they were measured, not by ablation: a
different order would shift points between neighbouring rules.

| Step | Mean | Points | What changed | Cases that moved |
|---|---|---|---|---|
| Kit LLM agent (Sat 15:27) | 61.5 | - | baseline | - |
| Own v1 (Sat 20:38) | 53.2 | -8.3 vs kit | tuned on sandbox and lab only; contract length judged at the opening price | P04 0.81 -> 0.00, P08 0.43 -> 0.15 |
| **Calculator** (v1.2, 21:06) | 67.5 | +6.0 vs kit (+14.3 vs v1) | package priced at the expected end price with the arena's own cost function, relationship term included | against v1: P04 0.00 -> 0.860, P08 0.152 -> 0.527; against the kit: P02 0.105 -> 0.293, P18 0.377 -> 0.430 |
| **Fact bank + dossier signals** (v1.4, 21:58) | 72.4 | +4.9 | one verified fact per e-mail, ppm without thousands comma, one fact per topic | P01 0.831 -> 0.915, P02 0.293 -> 0.531 |
| Past target, fast pay (Sun 00:45) | 72.9 | +0.5 | keep asking while the supplier moves; cash-short suppliers asked the fastest payment | P01 0.915 -> 0.969 |
| **Clause offer** (02:25) | 74.9 | +1.9 | index clause as a second sheet at our cost-optimal price | P02 0.531 -> 0.725 |
| Recent index fall + hedge guard (02:38) | 75.4 | +0.5 | cite a fallen cost-driver index, not to a hedged supplier | P18 0.467 -> 0.520 |
| **More indices, planner** (03:12) | 77.3 | +1.9 | every fallen index, one per e-mail; index the supplier blames with its larger fall | P08 0.549 -> 0.637, P18 -> 0.598, P01 -> 0.997 |
| No lowball (04:10) | 78.2 | +0.9 | capacity-tight supplier gets no first ask below 93 % of its opening; final runner | P10 0.647 -> 0.679 (+0.3); P05 0.872 by timing (+0.5, not repeatable) |
| **Price-jump pair** (04:25) | 79.3 | +1.1 | order history as the two orders around the supplier's price jump | P08 -> 0.814, P18 -> 0.657, P03 -> 0.956 (+2.7); P05 dipped to 0.717 when a bidder timed out (-1.6) |
| RFQ: do not ask a bidder that cannot win (04:29) | 80.3 | +1.0 | `drop_behind`: P05 back to 0.820 and 12-14 s | P05 (net against 75.4: 0) |
| Sunday release built in (08:08 to 09:20) | 80.3 | 0 | cannot be measured on practice (LOG Sun 09:16) | - |
| **Fixed price held** (09:57, J16) | 81.1 | +0.7 | `hold_fixed`: a supplier that answers the fixed-price ask with clause sheets is still asked for the fixed price, unless its material is hedged | P18 0.657 -> 0.729: its clause sheets fell 0.20 per fact instead of 0.10 |

Grouped (*Opinion*: this is the story for the slide):

| Half | Points | Rules |
|---|---|---|
| **What we ask for** (structure and trades) | about 9.5 | calculator 6.0, clause offer 1.9, fixed price held 0.7, past target / fast pay 0.5, no lowball 0.3 |
| **What we say** (checked facts, per supplier) | about 10.1 | bank + signals 4.9, price-jump pair 2.7, more indices 1.7, recent index + hedge guard 0.5, blamed index 0.3 |

### 3.2 The edges, ranked by how well we can defend them

| # | Edge | Evidence | Does it carry to hidden suppliers? |
|---|---|---|---|
| 1 | **Structure priced by the arena's own cost function** (calculator) | +6.0 on the mean. Kit agents read only the first term sheet, ignore the relationship term and accept the first final offer (`runs/BASELINE.md`, CONTEXT section 14). P10: the ignored second sheet was worth 0.647 against the accepted 0.570. | Yes, with no tuning: it *is* the scoring function. |
| 2 | **A dossier that decides which fact and which trade a supplier takes** | No-dossier ablation: about 3.5 points on six cases, 5 better, 1 equal (`PRACTICE-ARMS.md`). The same fact to an unhedged supplier moved P18's first counter 5.60 -> 5.40; to a hedged one (P08) it cost 0.111 (`LEARNINGS.md`, Omar). | Rules are keyed on signals read from letters, news, quote remarks and scorecards, not on IDs (no supplier ID in the agent's decision code). Strangers get a dossier from the case alone. The eight suppliers of the Sunday release were played offline in invented cases: 48 negotiations, no crash. |
| 3 | **A trade the supplier pays for** | P02: 0.105 (kit) -> 0.725. The clause is security: Nordmark moved from 373.97 to 351.45 for it, and our code then chose 362.70 because below its full cost (367.56) the relationship term bills us (0.242 at 351.45). | Only where a letter carries the signal. The LLM planner finds such trades with a quoted passage (P02 clause 3 of 3 calls). Measured kinds only are acted on. |
| 4 | **A measurement stack** (twins, replay, ledger) | Own supplier twins: mean error 0.2 to 1.3 % on the single-supplier practice cases, 1.85 % over 1100 real replies, P05 9.2 % (`runs/lab/BACKTEST.md`); 18,444 lab negotiations for the price path; practice suppliers answer identical messages identically, so one session compares exactly. | Process edge: it is why ten versions in a row did not regress (the 53.2 detour was the lesson). |
| 5 | **A final runner built for the wave cap** | P05 203 s and 243 s before, 12 to 14 s after; full runs: 0 crashes, 0 refused moves, 14 s (`LEDGER-JONATHAN.md`). A case open at the cap scores as no deal. | Yes: it is plumbing for any hidden RFQ. |
| 6 | **The memory system** (section 2) | Three people and three agents in parallel with no lost version. | Process edge. |
| 7 | **LLM reads, code decides** | LLM-written e-mails 71.6 against 72.9; verdict allowed to accept made P01 and P18 worse; planner is the only model in the loop and changes one practice e-mail (`LLM-ADVISOR.md`, `LLM-PLANNER.md`). | Yes, and it is a defensible answer to "why not just an LLM". |

What is **not** an edge, measured: the first ask's level (the supplier's final price on a structure did not
depend on it), wording and tone from an LLM, pushing after `final_offer` (withdrawal, score 0), per-case
playbooks (+0.05 in the lab, "no book works everywhere").

*Opinion on the jury criteria:* approach = structure first, code decides; explainability = one checked fact per
e-mail with its ID and the arena's `verified`, the replay shows the supplier's reasons; craft = 227 tests, the
runner, logs, hooks. The strongest single story is P02 (section 7.1) because it shows the mechanism, not only a
number; Highlight 2 (P08) shows the argument side.

*Opinion on "what others do":* we have no data on other teams. Tacto's own tips (CONTEXT section 15: numbers
from code, read the supplier, dossier once, rehearse, own simulator) describe our approach, so the idea is not
unique to us. What we can claim is that we executed all of it and **measured every step**.

### 3.3 Point 2: use arguments in a targeted way (Highlight 2 slide)

**The point (Jonathan's memo):** write down that we deploy arguments in a targeted way; it fits the Highlight 2
slide of the pitch deck (page 6 of `sellm-pitch.pdf`, "The same data, the right two rows", P08 0.433 -> 0.814,
"3 cases moved by the same rule").

**One sentence:** *We do not stack arguments. Every e-mail carries one checked fact, chosen for this supplier
and this moment, and the dossier keeps back the facts that would backfire.*

What the arguments are, mechanically (`docs/CONTEXT.md` section 7): a cited ID plus our figure in the same
sentence; the arena checks it (`verified`, `irrelevant`, `contradicted`, `duplicate`); then the supplier decides
whether it matters to it. "Verified" is not "convincing". So the work is in choosing.

| # | What "targeted" means | What the agent does | Evidence |
|---|---|---|---|
| 1 | **The right two rows of the same data** | `_po` in `sellm/claims.py`: not the first and last order of 24 months but the two orders around the supplier's price jump of the last twelve months | "5.75 two years ago, 5.84 today" was dismissed 42 times; "5.17 in 2025-12, 5.45 in 2026-09" was taken: P08 5.52 -> 5.17 in one reply, 0.637 -> 0.814; P18 0.598 -> 0.657; P03 0.923 -> 0.956 |
| 2 | **The right supplier** | The dossier's signals decide who hears which fact: `material_hedged` gets no index; `list_price_fixed` dismisses everything (37 of 37 answers, 70620), so no fact is spent; `capacity_tight` dismisses volume; `wants_volume` hears the forecast first; delivery records only with a delivery or quality problem | Same index: P18 (unhedged) first counter 5.60 -> 5.40, 0.467 -> 0.520; P08 (hedged until March 2027) "not our reality", 0.549 -> 0.438 without the guard |
| 3 | **The right size** | A fallen index is cited with its larger fall (from its twelve-month peak) only where the supplier's own letter blames that driver (the planner reads it) | P01 0.969 -> 0.997 (energy, -6.1 % instead of -3.7 %); the same larger number to a supplier that gave no such reason lost P11 0.068 |
| 4 | **The right moment** | One fact per e-mail, in a fixed order (rival offer > own-plant should-cost > fallen index > bank), indices first and the price jump after them; facts early, because suppliers say `final_offer` after about four of our messages | Two facts in the first e-mail: P18 0.564 against 0.598, P08 0.593 against 0.637 (J5). Strongest fact first: P18 0.542 against 0.657 (J11). A round with no fact ends the supplier sooner |
| 5 | **The right thing to leave out** | Nothing `irrelevant` (another part's order lines, an index that is no cost driver of the part): it cancels the verified fact next to it. No release ID on practice (`contradicted`). No insolvency news (sensitive). ppm without a thousands comma | P02: forecast moved the supplier 0.46 instead of 1.91 and it said `final_offer` after three messages, 0.394 and 0.319 against 0.531; P11 with the release news 0.626 against 0.778 |
| 6 | **A trade is not a fact** | The index clause is offered as a second sheet where the supplier's fixed price sits at its cost (P02), and *not* first where the supplier demands it anyway (P08, P18) | P02 0.531 -> 0.725; the clause in the first ask: P08 0.527 / 0.484 against 0.549, P18 0.386 / 0.401 against 0.467 |

**Proposed addition to the Highlight 2 slide** (*Opinion*; the slide is already full, so one strip or a swap of
the caption "3 cases moved by the same rule"):

- Headline stays: **The same data, the right two rows.**
- Strip under the two boxes: **Same fact, other supplier: it moved P18 and cost P08 0.111. The dossier decides
  who hears what.** (Evidence: row 2.)
- Small line: **One checked fact per e-mail. 0 contradicted.** (0 contradicted over all detailed suppliers in
  `tests/test_claims.py`; "0 contradicted" in the full runs: STATUS 22:25 run, 36 verified / 3 duplicate.)
- Keep "3 cases: P03, P08, P18" as the caption.

**Speaker notes (about 20-25 seconds):**

"An argument only works when it is chosen. The arena checks every fact we cite; the supplier then decides whether
it matters. Here is the same order history twice. First and last order, 5.75 two years ago and 5.84 today: 'it
does not change our calculation'. The two orders around its price jump, 5.17 in December and 5.45 in September:
five fifty-two to five seventeen in one reply. And the same index that moved one steel supplier cost us points
at another one that had hedged its material, so our dossier decides who hears what. One fact per e-mail, never
a pile."

**What not to claim:** that "targeting" is learned online by the agent. It is a fixed rule set derived from
about 480 saved sessions with Tacto's bots and from the supplier's own replies; per-supplier effect sizes are
single sessions. Say "rules we measured", not "the agent learned".

## 4. Why `jonathans_branch@f1c3fb9` (81.1) and not the others

### 4.1 Per case

Scores of the full practice runs (kit LLM: `runs/BASELINE.md`; others: `docs/STATUS.md` scoreboard; 81.1:
`experiments/LEDGER-JONATHAN.md`).

| Case | Kit LLM 61.5 | main 72.9 | omars 75.4 | sellm2 76.4 | 80.3 `@363b6e6` | **81.1 `@f1c3fb9`** | What moved it |
|---|---|---|---|---|---|---|---|
| P01 | 0.789 | 0.969 | 0.969 | 0.969 | 0.997 | **0.997** | planner names the blamed index (energy, larger fall) |
| P02 | 0.105 | 0.531 | 0.725 | 0.725 | 0.725 | **0.725** | clause as second sheet |
| P03 | 0.903 | 0.923 | 0.923 | 0.923 | 0.956 | **0.956** | price-jump pair exists for the first time |
| P04 | 0.810 | 0.860 | 0.860 | 0.860 | 0.860 | **0.860** | fixed-list-price supplier, nothing moves it |
| P05 | 0.676 | 0.820 | 0.820 | 0.820 | 0.820 | **0.820** | runner, one message in flight, drop a bidder that cannot win |
| P07 | 0.779 | 0.747 | 0.747 | 0.747 | 0.747 | **0.747** | below the kit: final offer at its third message whatever we say |
| P08 | 0.433 | 0.549 | 0.549 | 0.549 | 0.814 | **0.814** | several indices, then the price-jump pair (5.52 -> 5.17 in one reply) |
| P10 | 0.570 | 0.647 | 0.647 | 0.671 | 0.679 | **0.679** | no lowball to a capacity-tight supplier |
| P11 | 0.710 | 0.778 | 0.778 | 0.778 | 0.778 | **0.778** | - |
| P18 | 0.377 | 0.467 | 0.520 | 0.598 | 0.657 | **0.729** | recent index + hedge guard, more indices, price-jump pair, fixed price held |

`jonathans_branch` (81.1) against `omars_branch` (+5.7): price-jump pair 2.7, more indices 1.7, fixed price held
0.7, no lowball 0.3, blamed index 0.3. Against `sellm2` (+4.7): P08 +0.265, P18 +0.131, P03 +0.033, P01 +0.028,
P10 +0.008 (sellm2 already had the second index on P18 and the no-lowball rule, so what it lacks is the
price-jump pair, the second index on P08 and the held fixed price). `omars_branch` is a subset of
`jonathans_branch` (STATUS, Omar's row); `sellm2` lent its no-lowball rule (J4).

### 4.2 Per alternative

| Alternative | Score | What it was | Why it loses to 81.1 |
|---|---|---|---|
| Kit LLM agent | 61.5 | one model call per move writes everything | first sheet only, no relationship term, accepts the first final offer, one thread at a time (RFQ timeouts), sees only the case's `refs` |
| Own v1, sandbox/lab-tuned | 53.2 | 2.5 h of tuning on D01, D02 and the lab | a rule taken from one sandbox supplier lost P04 and P08; practice, not sandbox, is the yardstick |
| main negotiator + bank | 72.9 | calculator, bank, signals, past target | no clause offer (P02 0.531), one index only, no hedge guard, no price-jump pair |
| LLM writes the e-mails | 71.6 | gpt-6-sol around code's moves, all guards passed | -1.3; softer wording, and a case stops repeating (P07 0.766 then 0.740) |
| LLM verdict may accept | P01 0.864, P18 0.401 | "take it now" with a probability | repeats our own estimate's error with confidence 0.95; in 264 saved sessions no supplier of a single-supplier case withdrew before its own final offer, so accepting early protects against nothing |
| Per-case playbooks | +0.05 lab | knob sets per twin | most books lose elsewhere (P02 0.23 -> 0.07); one merged rule set plus dossier selection instead |
| `omars_branch` | 75.4 | clause offer, recent index, runner | strict subset |
| `sellm2` (Amiad's rewrite) | 76.4 | independent rewrite, no LLM | lacks multi-index and price-jump arguments (P08 0.549, P03 0.923) |

### 4.3 "The 80.2 rule"

There is no single rule: `--agent sellm` on `jonathans_branch` is the KNOBS block in `sellm/agent.py` on top of
the always-on parts. The number in the repo is **80.3** for `@363b6e6` and **81.1** for `@f1c3fb9`.

| Part | Where | Measured |
|---|---|---|
| Package and price path from total cost | `sellm/calculator.py`, `sellm/negotiator.py` | +6.0 |
| Dossier signals (cash short, list price fixed, hedged, capacity tight, wants planning ...) | `sellm/intel/signals.py` | about 3.5 on six cases |
| One checked fact per e-mail, order set by case type, `_po` price-jump pair | `sellm/claims.py` | bank +4.9; pair +2.7 |
| `past_target`, `fast_pay`, `clause_offer`, `idx_recent=2.0`, `idx_many=3`, `idx_blamed`, `no_lowball=0.93`, `drop_behind=0.08`, `plan_give`, `hold_fixed` | `sellm/agent.py` KNOBS, `sellm/endgame.py` | table in 3.1 |
| Planner (LLM reads the supplier, code acts on two measured kinds) | `sellm/planner.py`, `SELLM_PLAN=llm` | P01 +0.028, rest in reserve for strangers |
| Final runner | `sellm/runner.py` | 12-14 s per RFQ |

If "the 80.2 rule" meant **the rule that took us from 77.3 to 80.3**: that is the price-jump pair (`_po` in
`sellm/claims.py`), section 3.3 row 1. The first and last order of 24 months ("5.75 two years ago, 5.84 today")
was dismissed 42 times; the two orders around the supplier's jump ("5.17 in 2025-12, 5.45 in 2026-09") were
taken into account. Same data, the right two rows.

**State as measured:** `363b6e6` = 80.3, `f1c3fb9` = 81.1 (tag `best-jonathans_branch-81.1`, Sun 09:57), 81.1 again at `362bf0f` (10:11) and `abf71c0` (10:22): final runner, planner live, 0 refused. **`main` is `jonathans_branch@49eebc9` since 10:39 (LOG decision)**: its agent code is the measured `362bf0f`, fallback tags `best-jonathans_branch-81.1-head` and `best-jonathans_branch-80.3-sunday3`. Later commits on the branch change `experiments/` only.

## 5. Mechanisms worth a sentence each (the "what did it learn about suppliers" answer)

- **Verified is not the same as convincing.** The arena checks each cited ID and figure; the supplier then
  decides whether it matters to it. "It holds, but it does not change our calculation" against "we did not know
  that, a fair point". A fact that is new to the supplier moves it; a fact it already priced in does not.
- **The same fact can hurt.** A fallen alloy index cited to a supplier hedged until March 2027 ("Material covered
  until March 2027" in its quote remarks): "not our reality", final offer a round earlier, 0.549 -> 0.438. The
  dossier's `material_hedged` signal is the guard.
- **An index clause is security, not cash.** The arena counts no cash value for it, so the supplier pays with
  price, and the price it names is below its cost, which the relationship term then charges us for (P02: 351.45
  scored 0.242, 361.35 would score 0.735, the sheet we sent 0.725). Code chooses the price.
- **Suppliers price levers at their own cost of money.** Groups about 6.5 % a year, a family foundry about 9 %, a
  Czech job shop about 35 %. A 2 % discount for paying at 10 instead of 30 days is 36 % a year: the cash discount
  terms in the vendor master show it. A trade is good when its value to us is above that rate (ours is 8 %).
- **Suppliers mirror our steps, not our level**, say `final_offer` after about four to six of our messages, and
  a final offer is final. So facts must come early and one per e-mail.
- **A supplier that signs without a person must not be greeted "Dear Mit freundlichen Grüßen"** (found in the lab
  on unplayed cases, fixed in `sellm/writer.py`): craft detail for the Q&A.

## 6. Honest caveats (and the answers to them)

| Challenge | True answer |
|---|---|
| "81.1 on the same suppliers you tuned on." | Yes, practice is in-sample. P04, P10 and P18 were held out at v1.2 and were above the baseline then; P18 was tuned later (J1, J8, J16). Evidence beyond practice: twin suppliers in the lab, the nine unplayed case files, invented suppliers of all seven types, the eight release suppliers offline. We expect the final to be lower than 81.1. |
| "Three cases carry it." | P02 +0.62, P08 +0.38, P18 +0.35 are 69 % of the 1.95 case points gained over the kit; structure moved P05, P10, P11, P01 too. Nine of ten cases are at or above the kit; P07 is below (0.747 against 0.779). |
| "One session per change is not statistics." | For single-supplier practice cases the supplier answers identical e-mails with identical numbers (9 of 10 identical across two full runs), so one session is an exact comparison *for that supplier*. It says nothing about a supplier type; RFQ P05 varies 0.66 to 0.87 with timing. |
| "Would it work on a real supplier?" | We have only Tacto's bots. What should carry over is the economics (total cost, payment at the supplier's cost of money, a clause as security, one verifiable fact). What may not is the concession timing. We say so. |
| "Does the Sunday release help?" | Built in and checked offline; cannot be measured on practice (a release ID cited there is `contradicted`, P11 0.626, LOG Sun 09:16). Rules that act only on hidden cases: trigger letter read for its writer only, `wants_planning`. |
| "Where are the other 19 points?" | `C_best` is the best package any supplier would accept with every lever, so 1.0 is a ceiling that no supplier may reach. Missing at 81.1 (1 minus the score): P10 0.32, P02 0.28, P18 0.27, P07 0.25, P11 0.22, P08 0.19, P05 0.18, P04 0.14. |

## 7. Walk-through and slide order

### 7.1 Which negotiation to walk through

**P02 (copper motor), two rounds**, session `c5df08dc91c18229` (jonathans_branch@e658273 with the knob set),
https://arena.tacto.ai/replay/c5df08dc91c18229, score 0.725, kit 0.105.

| Step | What happens | Say |
|---|---|---|
| Supplier opens | 370.96 at 30 days, no clause; letter: copper +47.7 % in twelve months, 20 % of its cost | "Its reason is copper, and it carries the risk." |
| Our first e-mail | Two sheets as a menu: A 343.47 fixed, 90 days; B 362.70 with a CU-NOTATION clause (20 % share, 5 % deadband), 90 days. One fact: our own order prices 339.37 (2024-09) and 348.32 (2026-09). Offer of a call-off schedule and rolling forecast. | "One checked fact, and the trade it pays for: we take its copper risk, it takes our price." |
| Supplier | "We checked the price history data you cited; it holds and we took it into account ... formally accept your Option B at EUR 362.70" | "The arena verified the claim; the supplier says so in its own words." |
| We accept | Round 2, order confirmation | - |

Numbers for the backup slide: `C_open` 2,282,867, `C_deal` 2,248,556, `C_best` 2,235,514; Nordmark's full cost
367.56 (recovered from two charges of the arena). The clause costs us an index risk premium of 17,729 (session
breakdown); the fixed-price wall was 371.66 at 90 days and the clause sheet closed at 362.70, which is 8.96 per
unit on 6,110 units a year, about 54,700 (computed).

**P08 as the second example (Highlight 2):** session `3778b21e05901271` (`LEDGER-JONATHAN.md` J9): second e-mail
"5.17 in 2025-12, 5.45 in 2026-09", supplier from 5.52 to 5.17 at once, deal 5.11, 0.814.

*Opinion:* the brief asks for a replay from the final. Plan A: after the final, pick the case where the same
mechanism fired from `runs/logs/*.jsonl` and walk that one (P02 as the explanation of the mechanism). Plan B:
P02 as above.

### 7.2 Slide order, 3-minute cut (Amiad's 7 slides plus the intro)

| # | Slide | Time | Note |
|---|---|---|---|
| 1 | Title: "A buyer that measures before it negotiates", 61.5 -> 81.1 | 10 s | Amiad slide 1, number updated |
| 2 | **Six eyes, three agents, one memory (section 2)** | 25 s | new, memo point 1 |
| 3 | Versions 61.5 -> 81.1, with the two halves of 3.1 as a legend (ask 9.5 / say 10.1) | 30 s | Amiad slide 2 + 3.1, add the 81.1 bar |
| 4 | P02: sell the supplier security (0.105 -> 0.725) | 35 s | Amiad slide 5 |
| 5 | **Highlight 2: the same data, the right two rows, and the right supplier (section 3.3)** | 25 s | Amiad slide 6 + strip, memo point 2 |
| 6 | Measured, not guessed: twins, 450+ sessions, LLM 71.6 vs 72.9 | 20 s | Amiad slide 3, relabelled (section 9) |
| 7 | Close: structure first, measure, code decides | 15 s | Amiad slide 7 |

Total about 2:40. Amiad's "case by case" bar chart (slide 4) falls out for 3 minutes and is the first extra
for a 5-minute slot, followed by an "honest limits" slide (the table in section 6, three rows) and the
dossier slide (one supplier, its signals with their quoted evidence: `uv run python -m sellm.intel show 70130`).

## 8. Likely questions

| Question | Answer with evidence |
|---|---|
| Why did your agent write that? | Code fixes the move (structure, price, which sheet); the e-mail carries one fact with its ID and our figure; the arena returns `verified`; the replay shows the supplier's reasons. P02 e-mail above. |
| Why not let an LLM negotiate? | Measured: LLM-written e-mails 71.6 against 72.9, and not repeatable; a verdict that may accept lost P01 and P18. The model does what code cannot: it reads the letter and names the trade with a quoted passage (the clause in P02, 3 of 3 calls). |
| How do you choose the arguments? | One checked fact per e-mail; the dossier decides who hears which; same data, the right two rows (section 3.3). |
| What did it learn about suppliers, and from where? | Dossiers for 46 suppliers from letters, news, quote remarks, scorecards and cash discount terms; then rules from about 480 saved sessions (section 5). |
| What if a supplier is a stranger? | A dossier is built from the case alone; the planner reads its opening e-mail; two equal-cost offers differing in payment days when we do not know its cash position. Lab: invented suppliers of all seven types. |
| Did you overfit? | We did once: 53.2. Since then every change is judged on a full practice run, with P04, P10 and P18 as controls until they were used, and rules are keyed on signals, not IDs. |
| How did three people and their agents not collide? | Section 2: claims, typed log, hooks, pull before every run, one branch per person, every result names its commit. |
| What did you not do? | No second key, no events feed, nothing waits for input; no commit after the freeze. |

## 9. Open points before 12:00

1. **Slot length:** 3 minutes (Amiad's deck) or 5 + 2 (brief)? Confirm and say it in `docs/STATUS.md`.
2. **Numbers in the deck:** it says 80.3 on every slide and ends its version chart at 80.3. The newest measured
   full run is **81.1 (`f1c3fb9`, P18 0.729)**; the case-by-case slide shows P18 0.657 and `8a854c4`.
3. **Slide 3 of Amiad's deck, "What others don't do":** we have no data on other teams. *Opinion:* "What the
   starter kit doesn't do" or "How we know it works".
4. **"0.72 %":** it is the Sat 20:03 refit on 307 replies (LOG). `runs/lab/BACKTEST.md` (Sat 22:45) reports
   1.85 % over 1100 replies, P05 9.2 %, D02 2.7 %. Safe wording: "about 1 % on the single-supplier practice
   cases, under 2 % over 1100 real replies".
5. **Commit hash for the submission:** `main` is the 81.1 agent since Sun 10:39 (`jonathans_branch@49eebc9`, its code is the measured `362bf0f`; 81.1 three times). The submission and the README name the hash of `main` at the freeze; the slides say 81.1 and the same hash. `README.md` still has `_TODO_` for commit and approach.
6. **STATUS cleanup** before any screenshot (2.5).
7. **Final-case replay:** decide Plan A or B (7.1) by 12:30 so the replay is open in a tab at 13:00.

## 10. Sources

`docs/STATUS.md` (scoreboard, decisions), `docs/LOG.md` (Sun 08:59 to 09:26 entries), `docs/CONTEXT.md`
(sections 3, 7, 12, 15), `docs/LEARNINGS.md`, `experiments/LEDGER-JONATHAN.md` (J1 to J19, full-runs table;
on `jonathans_branch`), `experiments/LLM-ADVISOR.md`, `LLM-WRITER.md`, `LLM-PLANNER.md`, `PRACTICE-ARMS.md`,
`P02-ARGUMENTS.md`, `runs/BASELINE.md`, `runs/README.md`, `runs/lab/BACKTEST.md`,
`runs/practice/P02/20261011-091245-c5df08dc91c18229.md`, `sellm/agent.py` (KNOBS), `sellm/claims.py` (`_po`),
`sellm/intel/signals.py`, `sellm/planner.py`, `AGENTS.md`, `scripts/session-start`, `scripts/stop-check`,
`scripts/pull-first`, `.claude/settings.json`, `brief/submission.md`, `sellm-pitch.pdf`.
