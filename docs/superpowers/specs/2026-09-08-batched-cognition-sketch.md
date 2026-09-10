# WP4.2 Design Sketch — Batched Bot Cognition (v1 draft)

Status: APPROVED (user, 2026-09-10 "yes continue") — sub-steps 1+2 LANDED.

## Implementation log (2026-09-10, Patch A)

- `_my_coop` now reads a per-tick citizen->coop map cached on state
  (lazy, keyed on state.tick, first-match order preserved = the scan's
  exact semantics; membership mutates ONLY in apply_tick's JOIN/LEAVE/
  FOUND handlers, cognition is a frozen-tick pure read).
- personal_needs resolves active_ruleset_params once (was 2x/citizen).
- sim.bot: duplicated recipe lookup removed (dead lines, zero effect).
- drive() resolves params once per tick (was per bot = 966x).
- PROOF: 30-tick fingerprint A/B byte-identical (96d0e0fa91804b61,
  SEQ_SHA f732931b9f938ef1, 5,000 records, seq 509,842).
- PERF (pinned 2-core nice-19 harness): 1.46 -> 1.52 ticks/s (+4%).
  Smaller than the est. because the map build is once-per-tick and the
  entrepreneur jobless scan is the dominant consumer of the old scan
  cost - the map serves it O(1) now, but entrepreneur's own per-citizen
  work remains. Next lever: coop-constant blocks in sim.bot (bridge
  trigger rescans listings per member; equity _run_cost; honest-wages
  _replace_w/EMA - all identical across a coop's members).

## Problem

Bot cognition is the largest remaining profiled block (~30% of tick time
at pop=966): `sim.py bot()` runs per citizen per tick (35,341 sorted()
calls in 6 ticks are its per-citizen determinism loops alone), plus
`bots.py personal_needs` (~13.5%). At 1.32 ticks/s the gate needs another
**3.8×**; cognition batching is the biggest single lever left before the
structural regional-markets work.

## Hard constraint: byte-identical replay

Any batching MUST produce byte-identical results: the same transactions,
with the same contents, submitted in the same deterministic order, under
the same ruleset version. The proof protocol stays: 30-tick fingerprint
A/B + full suite + same-harness double benchmark.

## Safe transformations (est. combined ~10–18%)

1. **Per-coop decision templates.** Citizens in the same coop with the
   same role run structurally identical decision logic over identical
   recipe data (inputs/outputs sorts, wage math, skill levels differ only
   by per-citizen scalars). Precompute per-coop invariants ONCE per tick
   (sorted recipe keys, input cost sums, run-gap targets) into a
   tick-scoped cache object passed into bot(); per-citizen work shrinks
   to scalar math + tx construction. Cache is rebuilt from state each
   tick — no cross-tick state, replay-safe.
2. **Loop-invariant state reads.** Same pattern as tonight's
   personal_needs fix, applied everywhere: `state.active_ruleset_params()`,
   `effective_triage`, cost baselines, and triage-overrides hoisted out of
   per-citizen/per-good loops into per-tick locals.
3. **Group-ordered iteration.** Where a phase loops `for who in
   sorted(state.balances.keys())` and each citizen's outcome is
   independent (buys, dividends), precompute the sorted order once per
   tick instead of per phase. Order preserved exactly.

## Explicitly OUT of scope (determinism risk)

- Reordering tx submission by batching citizens into groups — even when
  provably independent today, it changes sort_key input order and breaks
  the fingerprint contract. NOT ALLOWED.
- numpy vectorization of decision logic: branchy per-citizen rules
  (mobility guards, shortage memory, triage splits) don't vectorize
  without semantic rewrites. Revisit only after (1)–(3) land.
- Any caching ACROSS ticks (state may change between ticks in replay
  forks). Tick-scoped caches only.

## Expected ladder after this

| Step | est. ticks/s (pop 966) |
|---|---|
| tonight (done) | 1.32 |
| cognition invariants (this spec) | ~1.5–1.6 |
| market-clearing allocations hoist | ~1.6–1.7 |
| regional markets (structural, separate spec) | ≥5 at scale, design-level |

Honest note: even with this spec, the ≥5 gate likely needs the structural
step. This spec is worth landing because every % won here multiplies
through all future prediction/grids (policy lab answers get faster too).

## Verification protocol (per project rules)

- 30-tick fingerprint A/B vs parent commit after EACH sub-step
- full suite green before each commit
- same-harness double benchmark (bench_scale.py) recorded in the ladder
- per-seed process discipline for any gate runs (10 GB cgroup limit)
