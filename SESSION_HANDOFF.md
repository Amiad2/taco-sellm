# SESSION_HANDOFF - Omar's Claude Code session, Sun 11 Oct 2026 01:45 CEST

Written for the next agent on `omars_branch`. Verified against the repo, `docs/LOG.md`, `GET /v1/me`
and a local test run at 01:41-01:45. Everything not marked otherwise is measured; hypotheses are
labelled. The repo's own memory stays authoritative: `AGENTS.md` (rules, read first),
`docs/CONTEXT.md` (the challenge), `docs/STATUS.md` (now), `docs/LEARNINGS.md`, `docs/LOG.md`.

## 1. Project objective

- **Task:** team sellm's buyer agent for the Tacto Negotiation Arena (EHL Grand Finale 2026). It
  negotiates by e-mail over an HTTP API (`https://arena.tacto.ai/v1`) with Tacto's hosted LLM
  supplier bots for the fictional pump maker Hollerau, and accepts a supplier's standing term sheet
  or walks away. Only term sheets bind; unstated terms close on the supplier's standard terms.
- **Success:** case score = `clip((C_open - C_deal) / (C_open - C_best), 0, 1)`, C = the arena's
  total-cost function (`arena_kit/cost.py`). Broken must-have or a deal worse than the opening = 0;
  no deal = the alternative's score. **Live Final Sun 12:00:** hidden cases in 5 waves of 8 minutes,
  every case weighs the same, points = sum of wave means x 100 (max 500). Practice does not rank.
- **Constraints:** no human in the loop during the final; the agent must never call `/v1/events`,
  `/v1/events/stream`, `/screen`, `/leaderboard`, `/results` (or `/v1/...`); one API key, 10 open
  sessions, 10 calls/s; 60 s per message per thread (3 timeouts end a thread), 10 messages per
  thread; code freeze 12:00 (team freeze **11:00**); **the final runs `main`** on Jonathan's MacBook.
  Sunday data release at 08:00 (`uv run arena data`); hidden cases may cite it.

## 2. Current architecture

Execution path (one move):

1. Runner: `sellm/runner.py` (final runner: one loop per thread, waves, closing before the cap,
   resume; `python -m sellm.runner --set final --agent sellm`) or the kit's `arena play|run`
   (`arena_kit/cli.py` -> `arena_kit/play.py`, one thread at a time). Both call `scripts/pull-first`
   before practice runs (not for `--set final`).
2. Agent: `sellm/agent.py:make_agent` -> `sellm/endgame.py:Persistent` (subclass of
   `sellm/negotiator.py:Negotiator`) with `KNOBS = {past_target: True, fast_pay: True}`.
   `SELLM_LLM=shadow|apply` swaps in `sellm/advisor.py:Advised` (LLM writer + verdict); **off by default**.
3. `Negotiator.decide(case, threads, focus)` -> `move()` -> one of ask / hold / take_alternative /
   accept / walk_away -> `message()` (`sellm/writer.py:compose`, template e-mails, no LLM).
   Every move is a pure function of case + threads (resumable after a crash).
4. Ask (`plan()`): structure from `calculator.packages()` (all option combinations priced with C at
   one price; payment days by the dossier's cash persona); target from `aim()`: own-plant should-cost
   (`calculator.supplier_cost`) or a prior share of the opening (`TARGET_SHARE` 0.945/0.88, moved by
   dossier signals), first ask = target x 0.94 (`open_below` 0.06), then steps sized so both prices
   meet after `horizon` 4 of our messages, staying just below its quoted price (`keep_below`).
   Arguments: one new checked fact per e-mail (rival offer > own-plant should-cost > falling index >
   `sellm/claims.py` bank, one per topic, fixed order by case type).
5. Close: accept a `final_offer`/`agreed` standing sheet (never ask after a final offer); walk only
   if the alternative is better. In relationship cases `past_target` keeps asking past our target.
6. Supplier knowledge: `sellm/intel/` (`dossier(sid, parts, case, openings)`: 46 stored dossiers in
   `sellm/dossiers/` + case overlay; never raises) -> cash persona, cost of money, signals;
   `sellm/personas.py` names the personas (description only). Data: `arena_kit/data.py:DataPackage`
   over `data/package` (not in git); `calculator.LOCK` serialises lookups across parallel cases.
7. Lab (no arena): `sellm/lab/` (local API with calibrated engine or LLM suppliers, twins of the played
   suppliers, invented scenarios). Architecture map: https://claude.ai/artifact/XH8RgDAuE42ZZTzNFPD8Ay

## 3. Implementation state

- **Git:** branch `omars_branch` (tracks `origin/omars_branch`) at `a5b363c`, identical to
  `origin/main` at 01:41. Working tree clean before this file. Team rule since 01:20: one branch per
  member for an independent version, shared files (`AGENTS.md`, `docs/`, `runs/`) on `main`, the
  chosen version merged into `main` before 11:00 (`AGENTS.md` section 4); every result names
  `<branch>@<hash>` (section 2).
- **This session's changes (all committed and pushed to `main`):** lock + case facts in
  `sellm/intel` (76be2c8); the dossier now reads all opening e-mails (b4361d2); "no qn after sc"
  tried and reverted (0223875); experiments `experiments/llm_writer.py`, `price_path.py`,
  `price_path_arena.py` with write-ups `LLM-WRITER.md`, `PRICE-PATH.md`; `AGENTS.md` rules (935973a, a5b363c).
- **Agent code since the last measured full run (7a49c38, 72.9):** only a persona log line in
  `sellm/endgame.py`; behaviour unchanged.
- **Unfinished (teammates, on `main`):** Jonathan "P02 arguments" (`experiments/p02_arguments.py`,
  no committed results yet); Codex "P02 experiment repair"; Amiad's playbooks (lab).
- **Known issues:** `uv run ruff check .` reports 1 error in `sellm/lab/p02_c_agents.py` (I001,
  not ours). On Omar's machine `.env` has `OPENAI_API_KEY` but the kit and `sellm/llm.py` read
  `LLM_API_KEY`: LLM calls there fail silently unless it is added. P05 (RFQ): the final runner scored
  0.665 twice vs the kit runner's 0.769 (open, Amiad). P11's 0.778 is one lucky path (0.710 on others).

## 4. Experimental results (arena unless marked)

Full practice runs (10 hosted cases, mean x 100):

| Agent | Commit | Mean | Note |
|---|---|---|---|
| kit LLM agent (baseline) | - | 61.5 | `runs/BASELINE.md` |
| negotiator v1.2 / after data-lock fix | 19b339f / d792ee3 | 67.5 / 67.7 | |
| v1.4: argument bank + signals | cdd9cf8, 61f806f | 72.4 (twice, identical) | |
| **current `--agent sellm`** (past_target + fast_pay) | **7a49c38** | **72.9** | P01 0.969, P02 0.531, P03 0.923, P04 0.860, P05 0.820, P07 0.747, P08 0.549, P10 0.647, P11 0.778, P18 0.467 |
| same with LLM-written e-mails (shadow verdict) | 86db7be | 71.6 | `experiments/LLM-ADVISOR.md` |

Best per case ever (team, `GET /v1/me`): P01 0.984, P02 0.531, P03 0.933, P04 0.860, P05 0.820,
P07 0.779, P08 0.560, P10 0.663, P11 0.778, P18 0.485 (mean 73.9).

Targeted tests (one session per case; practice suppliers answer identical e-mails identically):

| Test | Result | Source |
|---|---|---|
| Argument bank (one checked fact per e-mail) | P01 0.831 -> 0.915, P02 0.293 -> 0.531; no effect P04, P07, P08, P18 | `experiments/PRACTICE-ARMS.md` |
| `past_target`; + `fast_pay` | P01 0.915 -> 0.953 -> 0.969; D01 +0.026 | `experiments/PERSISTENCE.md` |
| push after `final_offer` | P04, P08 withdrew (0.000), P07 +0.032; all five P02 one-euro ladder sessions withdrew | PERSISTENCE.md, LOG Sun 00:18-00:45 |
| `creep`, `zone`, `pay_probe`, `signal_facts`, `soft_give`, closer first ask | no gain (P11 0.710, P18 0.434-0.467, P07 0.773 vs D02 worse) | PERSISTENCE.md |
| dossier: skip qn after sc (reverted) | P11 0.710 (0.778), P02 0.522 (0.531) | LOG Sat 22:18 |
| dossier: read all openings | P05 0.820 (same) | LOG Sat 22:20 |
| LLM verdict acting (`apply`) | P01 0.864 (0.984), P18 0.401 (0.446); P05 0.250 with kit runner timeouts | LLM-ADVISOR.md |
| P02 dials (5 settings) / wording probes | 0.482-0.531 / 0.529, 0.406 | LOG Sat 22:45, 23:51 |
| horizon 6 | P07 0.702, P11 0.710, P18 0.401, D01 0.921 (all below today) | `experiments/PRICE-PATH.md` |
| cost oracle, first ask 3 % below the lab floor | P02 0.531, P07 0.766, P11 0.710, P18 0.406, D01 0.935 (mean -2.4) | PRICE-PATH.md |
| relationship target x0.95 | P02 0.531 (same deal), D01 0.959 | PRICE-PATH.md |

Lab / offline only (not arena; models): LLM-written e-mails -3.1 points vs template on 12 twins with
LLM suppliers (`LLM-WRITER.md`); price-path sweep, 18,444 negotiations: lower first ask, target x0.85
to x1.08, horizon 3/6/8/10, relationship push all lose, oracle +2.0 in the lab but -2.4 in the arena
(`PRICE-PATH.md`); LLM reading supplier personas from e-mails 32/48 = as good as always "no"
(`PERSONA-READER.md`). Sandbox probes of supplier behaviour: `experiments/RESULTS.md`.

## 5. Arena budget

- **The "50 runs" budget cannot be verified from the environment.** The arena's real limit is
  **450 practice sessions per rolling 24 h for the whole team** (one API key; raised from 200).
  `GET /v1/me` at 01:41: **used 195, left 255**, resets 2026-10-11 12:13 UTC (14:13 CEST, after the
  final). `AGENTS.md`: keep at least 40 for Sunday (pre-flight, rehearsal).
- **Counting:** one `POST /v1/sessions` on a hosted practice case = 1 session (a full run = 10).
  Messages inside a session do not count. Sandbox `case:D01`/`case:D02` and the local `arena-sim`
  do not count (verified Sat 14:49). `arena me` and replays are free.
- **This session consumed 21 practice sessions** (+4 free D01), counted from `runs/labels.json`:
  P11 and P02 (fix B), P05 (fix A), one full run of 10 (22:25), 8 price-path checks. Against a
  50-run budget for this workstream that would leave 29 - an assumption, not a measured limit.

## 6. Argumentation

- **How it works (`docs/CONTEXT.md` section 7):** cite a data ID (`idx`, `po`, `fc`, `sc`, `qn`,
  `cost`, `quote`, `news`, `doc`+`ctr`, `offer`) with our figure in the same sentence; the arena
  checks against `facts.json` and returns at most 3 `claim_results` per message: verified,
  irrelevant, contradicted (costs trust), duplicate (each ID, and in practice each topic such as
  sc/qn, once per case). Prose without an ID is read by the bot but not checked.
- **Logic today:** `sellm/claims.py` builds the bank (verified wording: ppm without thousands comma,
  one figure per sentence); `Negotiator.arguments()` sends one new fact per e-mail in a fixed order
  by case type. It does not choose by supplier, does not react to the supplier's answer, and does
  not use the dossier's `stated_drivers` check.
- **Evidence:** facts moved P01 and P02 (the largest single gain, 67.7 -> 72.4 with signals); they
  did not move P04, P07, P08, P18 ("it holds, but it does not change our calculation"). A duplicate
  citation still helps; a round without an argument gets a hold (P11). Rhetoric, LLM wording and
  point-by-point rebuttals did not move prices (see section 4). After `final_offer` nothing helps.
- **Untested:** choosing the fact per supplier (dossier signal, measured effect per kind), reacting
  to "which figures?" / "does not change our calculation", the strongest fact first, more than one
  fact per e-mail, countering the supplier's own stated cost drivers (all 17 in practice openings
  matched the index, so this targets hidden cases). Jonathan's P02 arguments test is running.

## 7. Evaluation infrastructure

```bash
export PATH="$HOME/.local/bin:$PATH"                 # uv
uv run pytest -q                                     # 199 passed, 1 skipped (~2.5 min)
uv run ruff check .
uv run arena me                                      # quota and best scores (free)
uv run arena play case:D01 --agent sellm -v          # sandbox, free (D01, D02)
uv run arena play case:P07 --agent sellm -v          # one practice session (quota)
uv run arena run --set practice --agent sellm --parallel 8   # full run (10 sessions)
python -m sellm.runner --set practice --agent sellm --cases P05   # the final runner on chosen cases
scripts/pull-runs --label "<agent> <branch>@<hash>"  # save every session to runs/ (index runs/README.md)
uv run python -m sellm.lab compare <agent> <agent> [--supplier llm]  # lab, free; guide sellm/lab/README.md
uv run python -m experiments.price_path --only base,horizon_6        # lab sweep with test switches
uv run python -m experiments.price_path_arena --variant horizon_6 --cases P07   # arena check (quota)
uv run python -m sellm.intel verify                  # dossiers V1-V10
uv run python -m sellm.calculator P08                # a case's cost sheet
```

- **Logs and metrics:** `runs/<set>/<case>/<time>-<sid>.{json,md}` (full threads, result, cost
  breakdown, supplier reasons), `runs/README.md`, `runs/labels.json`, `runs/logs/` (runner),
  `experiments/results/*.json`, lab runs in `runs/lab/<run>/` (`summary.json`, `report.md`).
- **Repeatability:** practice suppliers are deterministic for identical messages, so one session per
  case compares variants; D01 varies 0.921-0.947 for one agent; P05 (RFQ) and any run with an LLM in
  the loop vary. Lab: `--seeds`, `--invent-seed`, `--fixed-twins`, `--supplier engine|llm`, `--think`.
- **Cheaper than the arena:** offline replay of recorded sessions (`tests/test_negotiator.py`
  replays all real states; a variant that sends the same moves cannot score differently), the lab
  (engine free; LLM suppliers cost tokens), sandbox D01/D02 (free, real bots), `arena-sim`
  (plumbing only). The lab missed twice in direction (P02 dials +5.5 predicted, 0 real; oracle +2.0
  predicted, -2.4 real): confirm lab gains in the arena before adopting them.

## 8. Important discoveries

- Suppliers end negotiations on their own schedule: `final_offer` after a median of 4 of our
  messages (64 % after at most 4, 171 threads), 2-24 % above their calibrated floor; a final offer
  is final (asking below it lost P04, P08 and all five P02 ladder sessions; only P07 took it).
- Our first ask does not change the supplier's final price (within-case -0.03 pp over 10 cases); a
  very low first ask ends rounds earlier and in RFQs got bidders to quit (P05).
- Price-path knobs (`open_below`, `horizon`, target) are at their optimum; cost knowledge does not
  help in the arena (P18: lower price, but the supplier moved to 30 days and a 0-deadband clause).
- Suppliers price payment days at their own cost of money (groups 6.5 %, measured from their sheets).
- Verified facts are the one lever that moved price (some suppliers); wording, LLM writing, LLM
  verdicts and LLM persona reading did not help or made it worse.
- Wasteful to repeat: replaying a practice case with an unchanged agent; price-path sweeps; LLM
  writer/verdict tests; pushes after `final_offer`; lab-only claims without an arena check.

## 9. Next steps (highest value first)

1. **Sun 08:00 data release** (group B runbook, `docs/STATUS.md` Next up 4): `scripts/sync`,
   `uv run arena data`, `uv run python -m sellm.intel build`, `check`, `verify` (must PASS), read the
   new letters/news, commit `sellm/dossiers` on `main`. Dry run Sat 22:30 was clean.
2. **Final readiness on `main` by 11:00:** decide which branch's version plays, merge it, run
   `scripts/preflight` on Jonathan's MacBook, keep 40+ sessions; decide the RFQ runner (P05 issue).
3. **Argument selection** (the one untested lever with evidence behind the mechanism): first measure
   offline from `runs/` the supplier's concession after each verified fact kind, per supplier and
   dossier signal; then a per-supplier order (strongest first) and answer-aware switching; replay
   offline, sandbox, one practice session per changed case. Coordinate with Jonathan's P02 test.
4. **Structure levers** (hypothesis from cost breakdowns): P08's index clause costs 32,000 of 79,000
   EUR to `C_best`, P10's lead time 33,600 EUR - test asking for a deadband / shorter lead time.
- Architectural uncertainties: how the agent generalises to the hidden suppliers (about a third
  combine unseen types); lab-to-arena transfer; LLM key configuration on the final machine (only
  matters if `SELLM_LLM` is used, which is off).

## 10. Repository handoff

- Branch `omars_branch` @ `a5b363c` (= `origin/main` at 01:41); this file is the only change after it.
- **Known-good baseline:** `a5b363c` - tests pass, agent behaviour identical to `7a49c38`, which
  scored **72.9** on all 10 practice cases. Earlier full-run points: `61f806f` / `cdd9cf8` (72.4).
- Restore: `git switch -c restore-<hash> <hash>` to test an older commit; bring it back with `git
  revert` of later commits or a merge; never `git reset --hard` over pushed work, never force-push.
  Tag versions worth keeping: `git tag -a best-<branch>-<score> <hash> -m "..."`, push the tag.
- Reports (claude.ai, private until shared): price-path analysis
  https://claude.ai/code/artifact/cd7f860c-5e80-433d-b1fe-40bb34782ddf; calculator explanation
  https://claude.ai/code/artifact/ce2bfe89-d5d0-4cde-aa34-1c81057b3905; architecture map (above).
- Session start in Claude Code runs `scripts/session-start` (state, claims, newest log). Before any
  arena run: `scripts/sync` (works on the current branch; `git merge main` brings team changes in).
