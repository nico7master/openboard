# Week 2 Harvest — Winnable Policy Paths from the 50/50 Unequal Start

Date: 2026-09-07 · Engine: commit e56ec2c state (fixed 21M cap, D21g offer smoothing, unequal scenario)

## Result: WP2.2 gate EXCEEDED — 18 distinct policy paths proven (gate asked for 3)

Every combination of `wealth_tax.rate_bp` ∈ {100, 200, 400, 600, 800, 1200}
× `surplus_spending.dividend_share_bp` ∈ {2000, 3000, 5000} — 18 combos ×
3 seeds (42/123/7) = **54/54 WIN** at 1500 ticks:

- Final private top-1 share: **~524–525 bp** (gate: < 1500 bp) — a fall from
  the 50/50 genesis (≈5000 bp) to ~5.2× the equal share.
- Everyone fed: worst essential unmet streak 11 (bound 30), identical
  across the grid.
- Money invariant exact on every tick of every run (inv_bad = 0).
- Full data: `sweeps/unequal_rerun/` (54 JSONs, HEATCARD.md, grid.log).

## Key findings

1. **Convergence is robust, not knife-edge.** Even the lowest tax rate
   (100bp = 1%/tick above threshold) reaches the gate. The policy
   quadrilateral (tax × dividend) is uniformly winnable: the game's first
   real policy decision is forgiving, not punishing.
2. **The rate sets the path speed, not the destination.** At 300 ticks the
   rates clearly separate (100bp → 948bp, 200bp → 577bp, ≥400bp → ~557bp
   private top-1); by 1500 ticks all converge to ~524bp. Higher rates
   converge faster but the endpoint is the same.
3. **The residual ~524bp is structural, not a failure**: the whale's
   below-threshold balance (500k credits ≈ 2.4% of supply) is untaxed by
   design (subsistence protection), and coops hold working capital. The
   economy converges to 'no private holder above 5× the equal share' —
   an honest, explainable equilibrium for the game's story.
4. **Dividend share barely matters for the endpoint** (2000 vs 5000bp are
   within 1bp at 1500 ticks) — it shapes the ride (services vs cash back
   to citizens), which is game-feel, not survival.

## Semantic decision (recorded, tested)

Top-1 share measures **private** wealth: citizen balances + coop
treasuries, EXCLUDING the Society Pool (public money — the tax's own
destination). Counting the pool masks exactly the redistribution the gate
measures. Implemented in `openboard.metrics.top1_share_bp` wiring and
`scripts/harvest_rerun.holders` (8 unit tests in `tests/test_metrics.py`).

## Why the banked sweeps couldn't prove this

`sweeps/*.json` (100 runs) are single-knob, pre-21M-cap, pre-D21g
aggregates: no top-1 metric, no combination coverage, and unmet tails of
~170–240 at the 1k scale (vs bound 30). Triage heat-card:
`sweeps/harvest_triage.md` (PROVISIONAL label retained). The re-run grid
is the proof; the banked data remains useful as the pre-cap comparison.

## Method

- Harness: `scripts/harvest_rerun.py` (resumable, one combo-seed per
  process, hardcore-gate loop recipe, per-tick money invariant, essentials
  streaks, top-1 trajectory every 10 ticks).
- Policies enacted at genesis via ruleset override (rate_bp /
  dividend_share_bp only — threshold stays upc-scaled by the dashboard,
  per the 2026-09-04 unit-scale fix).
- Each run: 1500 ticks, ~160s, 10GB-cgroup-safe (one process at a time).

## What this unlocks

- The unequal world ships with ≥3 (actually 18) verified winning policy
  paths — the core game loop has proven content.
- Week 3 (multiplayer, Break-the-System v2, onboarding quest) can build on
  this: the tutorial campaign can steer new players along the proven
  400bp×3000bp path.
- WP2.4 deflation study: docs/superpowers/specs/2026-09-07-deflation-policy-study.md
  (credit velocity votable; demurrage as default-OFF Lab rule).
