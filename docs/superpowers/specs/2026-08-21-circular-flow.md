# Circular Flow — Needs, Consumption & Surplus Spending

Date: 2026-08-21
Status: approved (user: "fix all the issues")

## Purpose

Close the economic loop: citizens have needs, goods get consumed, surplus
returns to citizens. Fixes the five evidence-backed failure modes from the
500-tick analysis:

1. Nothing is consumed → goods pile up forever.
2. Specialists (6 of 8 citizens) never buy anything → demand starvation.
3. Surplus never spends → pool grows, retirement never triggers.
4. No utility producer in baseline → electricity death clock (~t650).
5. Production ignores demand → overproduction piles.

## Design

### 1. Needs & consumption (engine)

- New rule params (votable, D7): `needs` = per-citizen-per-day consumption
  quotas by good. Default: `{"bread": 1, "water": 1, "electricity": 1}`
  (housing later; keep v1 minimal).
- New lifecycle phase in `apply_tick`, after markets clear:
  `CONSUME` — for every citizen, for every needed good, consume
  `min(held, quota)` from citizen inventory. Emits `CONSUMED` events
  (aggregated per citizen+good) into `applied`.
- Unmet needs tracked in state: `unmet_needs: dict[citizen][good] -> ticks
  without fulfillment` — God View alert + future welfare basis.
- Goods are destroyed (that is the point); money untouched → conservation
  invariant of money unchanged. New goods-flow invariant: produced =
  consumed + Δstocks (asserted in tests).

### 2. Surplus spending (engine)

- New rule params: `surplus_spending` = how the pool funds society each tick:
  - `citizen_dividend_share_bp` (default 5000 = 50% of *spendable* pool)
  - `public_services_share_bp` (default 5000)
  - `min_pool_buffer` (default 500; never spend below this)
  - `max_dividend_per_tick` (default 200 total, split evenly)
- New lifecycle phase `SURPLUS_SPEND` after CONSUME:
  - spendable = max(0, pool − min_pool_buffer), capped
  - dividend part: split evenly across citizens → balances (money printed
    INTO circulation from pool; pool decreases)
  - services part: funds public needs directly — v1: pays for consumed
    essential units at cost-baseline from the pool (virtual service payment:
    pool -= cost × units, retired-style accounting in `treasury_in`-like
    counter `services_paid`)
- Retirement rule stays: pool above `surplus_reserve_cap` (5000) still
  retires. Spending has priority (happens first in tick).

### 3. Utility sector in baseline (dashboard config)

- New coops: `power_plant` (recipe `electricity_coal`, buys `coal`),
  `water_works` (recipe `water_service`), `miners` (recipe `coal_mining`,
  buys nothing, needs hand_tools+machines endowment).
- New specialist fns in `SPECIALISTS`: `miner`, `power_worker`,
  `water_worker`.
- Baseline bots: 2 members each for the three new coops (14 citizens total).
- Treasuries: 600 for miners/power_plant (they buy inputs), 0 for
  water_works (no inputs).
- Electricity quota consumption applies to coops? NO — coops already burn
  electricity in PRODUCE (energy field). Citizen-side: households consume
  the 3 needs; coop electricity stock still only drains via production.
  Death clock killed because power_plant replenishes it.

### 4. Demand-driven production (sim specialists)

- `make_specialist` gains a stock-target: produce only when
  `own_output_stock < target` AND `listed_now == 0` (nothing already on
  market). Default target: 40 units output. Kills infinite piles; keeps
  shelves stocked.
- Input buying scales with target too (buy inputs for ≤ 1 production run
  beyond current stock target).

### 5. Specialists consume (bots)

- All specialists append personal purchases: buy their daily needs quota
  (`BUY_ESSENTIAL` for bread/water; `BID` for electricity at floor+1)
  when personal balance ≥ price and inventory below 2× quota.

## Determinism & compatibility

- All new params live in rules v-next with defaults; old save files
  (openboard-run-v1) replay correctly (no CONSUME phase existed → engine
  detects absent params and skips phases; `from_save` stays compatible).
- Events: `CONSUMED`, `SURPLUS_SPEND` — deterministic order (sorted citizens,
  sorted goods).
- Integer math only.

## Verification

- Tests: consumption destroys goods & updates unmet; dividend math exact;
  services payment; goods-flow invariant (produced = consumed + Δstock);
  pool never below buffer; retirement still works above cap; replay of
  mixed history with new phases; old-save compat.
- Simulation gate: 500-tick run shows (a) loop closure > 60%, (b) no
  permanent grain/bread piles, (c) citizens' bread holdings bounded
  (< 5× quota), (d) electricity stock stable or growing, (e) Gini
  trajectory ≤ baseline, (f) money supply growth flattens (dividend +
  services recycle; retirement triggers at least once after pool > cap).

## Out of scope

Housing/healthcare needs, decay of durables, citizen taxes, public
services as real transactions to coops (v1 bookkeeping only), Citizen
Seat UI (next milestone).


## Amendment (2026-08-22, post-gate findings)

Gate runs surfaced two structural gaps beyond the original scope, both now
implemented and gate-verified (3 seeds x 500 ticks, Gini 0.347):

1. **Co-op patronage (`coop_distribution` rule param)** — treasuries with no
   outflow hoarded worker-created surplus. Surplus above an operating buffer
   now returns to members each tick. Buffer 1,600 also reserves capital-rent
   capacity (a drained treasury underpays rent; observed miners capturing
   ~1,100 cr/machine via treasury cap).
2. **Capital rent (`capital_rent.per_machine_used` = 1,500)** — machines are
   socially owned capital; co-ops consuming machines as inputs pay society
   the replacement cost into the surplus pool (recycled via dividends and
   services). Fixes free-endowment rent capture: Gini 0.541 -> 0.347.
3. **Amended criterion (f)** — "retirement fires >= 1" replaced by
   "surplus recycles to citizens (dividends + services > 0) with pool
   bounded": with spending-priority, the pool never crosses the 5,000
   retirement cap; spending is the correct recycling mechanism. Retirement
   itself remains unit-tested in test_phase4.
4. **honest_worker bot** — bread buying is now holdings-gated (no slow
   hoarding); personal_needs covers actual consumption.
