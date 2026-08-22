# Circular Flow — Implementation Plan

Spec: docs/superpowers/specs/2026-08-21-circular-flow.md (approved)

## Tasks

- [x] T1 `rules.py`: add `needs` (dict good->int quota, default
      `{bread:1, water:1, electricity:1}`) and `surplus_spending`
      (dividend_share_bp, services_share_bp, min_pool_buffer,
      max_dividend_per_tick) to `DEFAULT_RULESET_PARAMS`; extend
      `validate_params` schema.
- [x] T2 `state.py`: new fields with defaults — `unmet_needs: dict`,
      `services_paid: int`, `dividends_paid: int`, `consumed_totals: dict`;
      wire into `snapshot_dict`, `clone`, genesis. Old saves lacking the
      fields must load (defaulted) — replay unchanged.
- [x] T3 `engine.py`: two deterministic end-of-tick phases inserted after
      market clearing, before governance:
      - `_consume_phase`: sorted citizens × sorted goods; consume
        min(held, quota); emit aggregated `CONSUMED` events; update
        `unmet_needs` (reset on full fill, +1 otherwise).
      - `_surplus_spend_phase`: spendable = clamp(pool - buffer, 0,
      caps);
        dividend → even integer split to citizens (remainder stays),
        pool -= paid, `dividends_paid` += paid; services → pool pays
        cost-baseline × units consumed-essentials this tick,
        `services_paid` += paid (money leaves supply).
      Both phases no-op when params absent (old rulesets / old saves).
      Money invariant becomes: supply = initial + minted − retired −
      services_paid (dividends are transfers from pool).
- [x] T4 `sim.py`: `make_specialist(..., stock_target=40)` — produce only
      when output stock + listed < target; input buys sized to ≤1 run beyond
      target. New helper `personal_needs()` returning BUY_ESSENTIAL/BID txs
      appended by ALL bot archetypes (workers + specialists).
- [x] T5 `dashboard/server.py`: baseline adds coops `miners` (coal_mining),
      `power_plant` (electricity_coal), `water_works` (water_service);
      specialists miner/power_worker/water_worker; 14 citizens; treasuries
      miners:600 power_plant:600; analytics series: consumed/tick,
      dividends/tick, unmet needs/tick, services paid.
- [x] T6 `dashboard/static/index.html`: World view — consumption overlay on
      circular-flow chart, surplus-flow panel (in/out/retired/services),
      unmet-needs alert line; Dashboard tab: needs badges per citizen.
- [x] T7 tests (`tests/test_circular.py` + dashboard additions):
      consumption destroys goods & bounds holdings; unmet escalation;
      dividend integer math + remainder conservation; buffer never
      breached; services payment reduces supply; retirement still fires
      above cap; replay of old-format save unchanged; replay of new save
      identical; shuffle determinism with new phases; sim stock-target;
      personal purchases present; 14-citizen baseline; new analytics
      endpoints.
- [x] T8 Gate: 500-tick, 3-seed simulation meets spec verification
      criteria (loop closure >60%, piles bounded, bread holdings <5× quota,
      electricity stable, Gini ≤ old baseline, retirement fires ≥1).
      Full pytest. Update README + decisions log. Commit.

## Order

T1→T2→T3 (engine core) → T4 (bots) → T5+T6 (server/UI) → T7 (tests) →
T8 (gate + docs + commit).
n