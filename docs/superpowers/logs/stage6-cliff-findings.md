# Stage 6 cliff-zoom findings (2026-08-28)

## Knob 1: surplus_spending.dividend_share_bp — buffer-gated near-inert at scale
- Fine sweep (7 values x 5 seeds x 1500 ticks, 986 citizens): 32/35 stable.
- The 3 'unstable' verdicts are NOT a cliff: identical metrics (streak 9,
  trend 0.153) at three different values = chaotic forking after rare
  buffer-crossing dividends, failing only the strict trend bound (0.153 > 0.05).
- Root cause measured: surplus pool hovers at ~435 cr, BELOW
  min_pool_buffer (500) -> dividends almost never flow at 986 citizens,
  regardless of the nominal share (probe: 0 dividends in 100 ticks at
  share 1000 AND 7000).
- Economic discovery: at production scale the surplus pool barely
  accumulates; the dividend channel is effectively dormant. Revisit
  min_pool_buffer or pool inflows in a later balance pass.

## Knob 2: wealth_tax.rate_bp — mechanically real, dose-responsive
- Probe (300 ticks, 986 citizens): rate 100 -> 92,706 cr collected,
  top balances ~7,850; rate 800 -> 211,164 cr, top balances ~5,400.
- Tax = (balance - threshold 5000) x rate_bp / 10,000; verified live via
  WEALTH_TAX events in state.applied. Fine sweep stands as measured.

## Methodology note
A votable-looking knob can be mechanically inert if gated by a pool
buffer or threshold; always verify the knob's mechanical effect (probe
endpoints, count events) before interpreting a sweep. Governance is
already OFF in sweep runs (Run(governance=False) default), so the
politics-freeze concern does not apply to these results.
