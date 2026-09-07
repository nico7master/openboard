# Deflation Policy Study — Fixed Money + Growth (WP2.4)

Date: 2026-09-07 · Status: evidence from unequal-world runs (current engine: 21M fixed cap, D21g offer smoothing)

## The structural fact

The 21,000,000-credit supply is fixed and never minted. Any real growth —
more production, better skills, more citizens served — must therefore show
up as **falling prices**, not more money. Deflation here is a *feature of
honest money*, not a bug; the design question is which consequences we
make votable game decisions.

## Observed evidence (300-tick unequal run, tax 400bp, dividends 3000bp)

- Essentials (bread, water, meals) do NOT trade on the auction: citizens
  buy them at **cost floors** via BUY_ESSENTIAL (514k events, zero
  MARKET_CLEAR_AUCTION events for them). Their nominal prices cannot
  deflate while cost baselines hold.
- The one auctioned good (electricity) moved 21 → ~25 credits and
  stabilized — no deflationary spiral in 300 ticks.
- The whale drain (50% → ~5% private top-1 share) flows through the
  Society Pool and back out as dividends/services: velocity of the SAME
  money rises. This is the healthy answer to fixed money: faster
  circulation instead of more units.

## Where deflation WILL bite (structural, to watch at 1500+ ticks)

1. **Wages are sticky, prices fall** — cost-floor restamps lag productivity;
   workers gain real purchasing power (good) but coop wage debts set in
   nominal credits get heavier in real terms (the plan's Risk #2).
2. **Credit: fixed-fee loans get heavier in real terms** as prices fall —
   `credit.fee_bp` is charged on principal; deflation raises its real rate.
3. **Savings hoarding** — falling prices reward waiting to buy; without a
   counter-pressure, demand timing can bunch (perishability R1 already
   caps the pure-arbitrage version).

## Recommendation: one votable knob, ship demurrage as a Lab rule

- **Primary: keep credit velocity as the first counter-cyclical knob** —
  the credit union already exists (loans + fee_bp); making the fee and
  quota votable lets a society speed circulation in deflationary phases
  without touching the supply invariant.
- **Optional (default-OFF Lab rule): demurrage** — a small per-tick tax on
  balances above a threshold, paid into the Society Pool. Structurally it
  is `_wealth_tax_phase` with a low rate and a low threshold; it composes
  with the wealth tax (one extra optional param, no engine change).
  Gate before enabling: adversary lab must show it does not kill saving
  for durable inputs (durable_capital interplay).

## Decision

Ship v1.0 with credit velocity votable; keep demurrage as a default-OFF
Policy Lab experiment with the evidence above in code comments. Revisit
after the 1500-tick harvest grid lands (this study will be amended with
long-horizon price data from `sweeps/unequal_rerun/`).
