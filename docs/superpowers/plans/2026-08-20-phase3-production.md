# Implementation Plan — Phase 3: Production

**Date:** 2026-08-20
**Spec:** `docs/superpowers/specs/2026-08-19-openboard-economy-engine-design.md` (§6, §12 Phase 3)
**Gate:** production tests green + all Phase 1–2 tests still green

---

## Goal

The economy starts running: citizens work, cooperatives produce, cost-baselines are computed. Work mints credits (D4: money is created by work), production consumes real inputs (labor pool + energy + materials) from co-op inventory, and every produced good gets an integer cost-baseline (production at cost as accounting truth — constitutional core).

## Design Decisions

- **Labor pool model**: `WORK` logs hours into the co-op's labor pool and pays wages immediately (credits minted from nothing — money creation by work). `PRODUCE` consumes `labor_hours × runs` from the pool. Wages paid ≠ labor consumed: the pool is the buffer. This gives clean socialist accounting: labor is an input like any other.
- **Integer-only wages (no floats, ever)**: multiplier as basis points (`wage_multiplier_bp`, 10000 = 1.0×). Per-co-op remainder accumulator: `total_bp = hours × mult + remainder; credits = total_bp // 10000; remainder = total_bp % 10000`. Deterministic, lossless over time.
- **Energy = the `electricity` good**: recipe `energy` field is kwh deducted from co-op inventory as `electricity`. `electricity_coal` (energy: 0) is the generator recipe.
- **Bootstrap endowment (solves the chicken-egg problem)**: `FOUND_COOP` grants a starter inventory (water, electricity, hand_tools, machines) defined as a **votable rule param** `bootstrap_endowment` (good → qty) — the means of production are socially granted, and the grant itself is democratically changeable (D7 demo for economy params).
- **Cost baselines**: integer per-good `good_cost_baseline` in state, seeded from `DEFAULT_BASELINES` (catalog data, all 39 goods). Each production run computes `new_baseline = (labor_cost + energy_cost + input_cost) // total_output_units` (floor) and stamps it on each output good (last-production-cost accounting; refined when markets arrive in Phase 4).
- **Money supply invariant**: `total_credits == initial + state.money_minted − state.money_retired` (retired stays 0 until Phase 4 surplus retirement). Phase 1's transfer-only conservation is superseded; new test enforces the general invariant.
- **Rule params grow** (complete documents, so schema extends now in dev): + `wage_multiplier_bp` (10000), `energy_price` (2 credits/kwh), `max_work_hours_per_tick` (8), `bootstrap_endowment` (dict good→qty, validated against known goods, qty int > 0).

## New Actions

- `WORK` `{coop_id, hours}` — sender must be member; 0 < hours ≤ `max_work_hours_per_tick`; mints wage credits, fills `coop.labor_pool_hours`, adds to `state.labor_hours[sender]`.
- `PRODUCE` `{coop_id, recipe_id, runs}` — sender must be member; runs > 0; checks recipe known, inputs × runs in inventory, electricity ≥ energy × runs, labor pool ≥ labor_hours × runs. Consumes all, adds outputs × runs, computes + stamps cost baselines.

## New Reason Codes

`RECIPE_NOT_FOUND`, `INVALID_RUNS`, `INVALID_HOURS`, `NOT_ENOUGH_LABOR`, `NOT_ENOUGH_INPUTS`, `NOT_ENOUGH_ENERGY`

## Tasks

- **P3-T1** `catalog.py`: `DEFAULT_BASELINES` for all 39 goods (integers, generous enough to make early chains sensible)
- **P3-T2** `rules.py`: extend `REQUIRED_PARAMS` + validation (bootstrap_endowment schema), update `DEFAULT_RULESET_PARAMS`
- **P3-T3** `state.py`: coops gain `labor_pool_hours`, `wage_remainder_bp`, endowment inventory at founding; state gains `good_cost_baseline`, `money_minted`, `money_retired`; snapshot/hash covers all
- **P3-T4** `engine.py`: WORK + PRODUCE actions, FOUND_COOP grants endowment, integer baseline computation
- **P3-T5** tests `test_phase3.py`: WORK happy/rejections, PRODUCE happy/rejections (each reason), baseline math on a known recipe, endowment-granted founding, money invariant, fuzz with WORK+PRODUCE loops (fishing chain: labor-only), determinism + shuffle + replay + tamper
- **P3-T6** update `params_with()` in test_phase2.py for the new schema

## Definition of Done

- [x] All production tests green
- [x] Phase 1–2 tests green (with updated params schema)
- [x] Money invariant test green
- [x] Mixed fuzz incl. production replays deterministically

## Out of Scope

Markets/auctions (Phase 4), surplus retirement (Phase 4), wage multipliers per role (Phase 5 voting), bots (Phase 7)
