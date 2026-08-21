# God View — World Analytics Dashboard

Date: 2026-08-21
Status: approved (user: "lets build the world view first")

## Purpose

Give the operator a top-down view of the whole economy: where money sits,
what is produced and bought, per-good flows, and plain-language alerts.
Pure read-only analytics over existing engine state — **no engine changes**.

## Scope

- Server: extend `Run._record_timeline` with per-tick aggregates.
- Server: new `GET /api/analytics` endpoint.
- UI: new "World" view (view switcher: Dashboard / World) with:
  - Money pie: citizens vs coop treasuries vs surplus pool (vs retired).
  - Production pie: units produced by sector (catalog category).
  - Purchases pie: units bought by sector.
  - Flow chart: produced vs bought units per tick (lines).
  - Per-good table: produced, sold, listed, coop stock, citizen holdings,
    last clearing price vs cost baseline.
  - Alerts feed: plain-language warnings (see below).

## Honest labeling

Real consumption does not exist yet (circular-flow milestone comes later).
Charts say "bought", not "consumed". Purchases are the best available proxy.

## Data rules

- Timeline aggregates appended per tick, trimmed to 600 entries like existing keys.
- Categories come from `state.goods[good]["category"]`.
- Money supply = citizen balances + coop treasuries + surplus pool
  (matches existing timeline invariant; escrow does not exist — bids pay at clear).
- Produced units: sum of `outputs_produced` across PRODUCE events per tick.
- Bought units: BUY_ESSENTIAL + auction wins by citizens per tick.
- Analytics endpoint derives current-stock pies and per-good table from live
  state, and time series from the timeline aggregates (no state.applied scans
  in the endpoint — applied events are only used when recording a tick).

## Alerts (server-computed, plain language)

- Coop treasury < 50 cr → "near bankruptcy".
- Coop holds > 200 units of any produced output → "overproduction pile".
- Citizen balance < 10 cr → "out of money".
- Oversight flags present → summarized with citizen/coop and type.
- Surplus pool > 1000 and money_retired == 0 → "surplus not circulating".

## Verification

- Unit test: analytics endpoint money pie sums to the timeline money supply.
- Unit test: per-tick produced/bought aggregates match the events of that tick.
- Existing 192 tests stay green; browser smoke check via screenshot.

## Out of scope

Citizen Seat view, engine circular-flow changes, rule editing UI, save-format
changes (analytics are derived, not persisted beyond the existing timeline).
