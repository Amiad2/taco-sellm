# Lab search 20261010-1632: 10 min, 64 random variants to start

27800 negotiations, 162 scenarios (12 twins). Scores x 100; 'worst 10 %' is the mean of the worst tenth of scenarios; crashes, broken must-haves and deals worse than the opening are counted per negotiation.

| # | Strategy | Knobs | Scen. | Mean | Twins | Invented | Held-out | Worst 10 % | No deal | Crash | Broken | Worse |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | calc | accept_gap=0.01, after_final=accept, ask_breakdown=False, claims=bank, floor_guess=0.85, guess_rate=0.2, open_below=0.1, shape=0.75, sheets=3, steps=8, structure=joint, take_alternative=False, tone=neutral, use_should_cost=False | 162 | **54.5** | 60.4 | 54.0 | 58.4 | 9.1 | 12 | 0 | 0 | 2 |
| 2 | calc | accept_gap=0.01, after_final=accept, ask_breakdown=True, claims=bank, floor_guess=0.85, guess_rate=0.2, open_below=0.06, shape=1.0, sheets=3, steps=8, structure=joint, take_alternative=False, tone=neutral, use_should_cost=False | 162 | **54.3** | 60.5 | 53.8 | 58.4 | 9.1 | 12 | 0 | 0 | 2 |
| 3 | calc | accept_gap=0.002, after_final=accept, ask_breakdown=True, claims=bank, floor_guess=0.85, guess_rate=0.2, open_below=0.1, shape=0.75, sheets=3, steps=8, structure=joint, take_alternative=False, tone=neutral, use_should_cost=False | 162 | **54.2** | 60.4 | 53.7 | 58.4 | 8.0 | 14 | 0 | 0 | 2 |
| 4 | calc | accept_gap=0.01, after_final=accept, ask_breakdown=True, claims=bank, floor_guess=0.85, guess_rate=0.2, open_below=0.06, shape=0.75, sheets=2, steps=8, structure=joint, take_alternative=False, tone=neutral, use_should_cost=False | 162 | **54.0** | 59.3 | 53.5 | 55.6 | 8.4 | 12 | 0 | 0 | 2 |
| 5 | calc | accept_gap=0.0, after_final=accept, ask_breakdown=True, claims=bank, floor_guess=0.85, guess_rate=0.2, open_below=0.06, shape=0.75, sheets=2, steps=8, structure=joint, take_alternative=False, tone=neutral, use_should_cost=False | 162 | **53.9** | 59.6 | 53.4 | 55.6 | 8.0 | 12 | 0 | 0 | 2 |
| 6 | calc | accept_gap=0.01, after_final=accept, ask_breakdown=True, claims=bank, floor_guess=0.85, guess_rate=0.2, open_below=0.06, shape=0.75, sheets=3, steps=8, structure=joint, take_alternative=False, tone=neutral, use_should_cost=False | 162 | **53.7** | 59.7 | 53.3 | 58.4 | 8.4 | 12 | 0 | 0 | 2 |
| 7 | calc | accept_gap=0.01, after_final=accept, ask_breakdown=False, claims=bank, floor_guess=0.85, guess_rate=0.2, open_below=0.06, shape=0.75, sheets=3, steps=8, structure=joint, take_alternative=False, tone=neutral, use_should_cost=False | 162 | **53.7** | 59.7 | 53.3 | 58.4 | 8.4 | 12 | 0 | 0 | 2 |
| 8 | calc | accept_gap=0.01, after_final=accept, ask_breakdown=False, claims=bank, floor_guess=0.85, guess_rate=0.2, open_below=0.06, shape=0.75, sheets=3, steps=8, structure=joint, take_alternative=False, tone=warm, use_should_cost=False | 162 | **53.7** | 59.7 | 53.3 | 58.4 | 8.4 | 12 | 0 | 0 | 2 |
| 9 | calc | accept_gap=0.0, after_final=accept, ask_breakdown=True, claims=bank, floor_guess=0.85, guess_rate=0.2, open_below=0.06, shape=0.75, sheets=3, steps=8, structure=joint, take_alternative=False, tone=neutral, use_should_cost=False | 162 | **53.6** | 60.3 | 53.1 | 58.4 | 7.9 | 12 | 0 | 0 | 2 |
| 10 | calc | accept_gap=0.002, after_final=accept, ask_breakdown=True, claims=bank, floor_guess=0.85, guess_rate=0.2, open_below=0.06, shape=0.75, sheets=3, steps=8, structure=joint, take_alternative=False, tone=neutral, use_should_cost=False | 162 | **53.6** | 60.3 | 53.1 | 58.4 | 7.9 | 12 | 0 | 0 | 2 |
| 11 | calc | accept_gap=0.002, after_final=accept, ask_breakdown=True, claims=bank, floor_guess=0.85, guess_rate=0.2, open_below=0.06, shape=0.75, sheets=1, steps=8, structure=joint, take_alternative=False, tone=neutral, use_should_cost=False | 162 | **53.6** | 58.0 | 53.2 | 52.4 | 7.9 | 12 | 0 | 0 | 2 |
| 12 | calc | accept_gap=0.01, after_final=accept, ask_breakdown=True, claims=bank, floor_guess=0.85, guess_rate=0.2, open_below=0.06, shape=0.75, sheets=2, steps=8, structure=joint, take_alternative=True, tone=neutral, use_should_cost=False | 162 | **53.5** | 60.2 | 53.0 | 55.6 | 6.4 | 16 | 0 | 0 | 2 |

Baselines:

- naive: mean 38.7, twins 22.3, invented 40.0

Per twin (best three and baselines):

| Strategy | D01 | D02 | P01 | P02 | P03 | P04 | P05 | P07 | P08 | P10 | P11 | P18 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| calc #1 | 0.90 | 0.36 | 0.71 | 0.18 | 0.89 | 0.81 | 0.48 | 0.81 | 0.35 | 0.63 | 0.81 | 0.31 |
| calc #2 | 0.90 | 0.38 | 0.71 | 0.18 | 0.89 | 0.81 | 0.48 | 0.81 | 0.35 | 0.63 | 0.81 | 0.31 |
| calc #3 | 0.90 | 0.36 | 0.71 | 0.18 | 0.89 | 0.81 | 0.48 | 0.81 | 0.35 | 0.63 | 0.81 | 0.31 |
| naive | 0.23 | 0.33 | 0.59 | 0.22 | 0.07 | 0.78 | 0.00 | 0.12 | 0.21 | 0.00 | 0.00 | 0.12 |

Run: `uv run python -m sellm.lab search --minutes 10 --invented 150 --start 64 --seeds 2 --label first`, 699 s.
