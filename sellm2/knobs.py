# ruff: noqa: E501  (long sentences and messages)
"""Every setting of sellm2 in one place, each with the evidence it rests on (docs/LOG.md,
docs/LEARNINGS.md, experiments/*.md). The lab and the experiments override them by keyword."""

KNOBS = dict(
    # -- price path ------------------------------------------------------------------------------
    open_below=0.06,  # first ask this far below the target: 0.03 -0.25, 0.10 -1.90, 0.20 -6.55 pts (lab, 18,444 runs)
    horizon=4,  # our messages until the prices meet: final_offer after a median of 4 (171 threads); 6 lost 4 of 4 in the arena
    pace=0.5,  # share of our steps a supplier gives back until the thread shows its own (foundry 0.5, job shop 1.0)
    keep_below=0.006,  # stay this far below its price: it makes the last move (P01 took asks 0.6-1 % below)
    target_share={True: 0.945, False: 0.88},  # end as a share of the opening without a cost of its plant (relationship / not)
    rate_guess=0.08,  # cost of money of a supplier we hold no data on: our own, so no bias on payment days
    fast_rate=0.15,  # a supplier whose money costs this much gets the fastest payment (job shops: 17-35 %)
    past_target=True,  # relationship cases: keep asking past our target while it still moves (P01 0.915 -> 0.953, D01 +0.026)
    estimate_error=0.05,  # ... down to the target of a cost estimate this much lower
    max_holds=2,
    stall_gap=0.002,  # a fixed-list-price supplier that repeats its price: ask this far below it (P04 one cent = 0.14)  # holding e-mails per waiting RFQ thread
    # -- structure -------------------------------------------------------------------------------
    lever_prices=True,  # price lead time, ppm and deadband at what suppliers charged for them (P10, P11, P08, P18)
    clause_offer=True,  # P02 0.531 -> 0.725: the index clause as option B at the C-minimal price
    no_lowball_tight=True,  # P10: every first ask <= 28.6 of 32.2 got final_offer at once
    tight_open_below=0.07,  # ... first ask at most this far below its opening to a capacity-tight supplier (29.89 kept it open)
    # -- arguments -------------------------------------------------------------------------------
    arguments=True,  # one checked fact per e-mail (P01 0.831 -> 0.915, P02 0.293 -> 0.531)
    recent_fall=True,  # a cost driver's fall from its 12-month peak (P18 0.467 -> 0.520), never to a hedged supplier
    breakdown=True,  # a cost breakdown the supplier attaches becomes our cost estimate where we hold none
    # -- data ------------------------------------------------------------------------------------
    data=True,  # read the package (False: case and e-mails only, a supplier we hold no data on)
)
