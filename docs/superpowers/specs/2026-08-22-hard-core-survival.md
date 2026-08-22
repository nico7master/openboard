# Hard Core — Long-Run Survival

Date: 2026-08-22. Approved by user ("Fix") after 2,000-tick probe exposed
a systemic freeze at ~t800 (all 14 citizens unmet bread/electricity/water).

## Problems (evidence: seed 42, 2,000 ticks)

1. **Book-cost bleed**: cost baselines stamp from input *book baselines*,
   not realized purchase prices. Downstream co-ops (millers) underprice,
   treasury pins at 0, chain dies. Root: `_apply_produce` uses
   `good_cost_baseline.get(good)` and hardcoded `energy_price`.
2. **Capital depletion**: bootstrap endowment machines/tools are consumed
   by mining/logging recipes; no producer exists. Mining stops ~t800 ->
   power -> water -> everything.
3. **Thin utility buffers**: coal/electricity/water targets give the
   circular coal<->power<->water dependency no slack.
4. **Gate blind spot**: 500-tick gate cannot see t800 failures.

## Fixes

- **A1 True-cost (VWAP) accounting** — new rule param `cost_accounting:
  {"method": "vwap"}` (off in genesis; old saves replay identically).
  State tracks per-coop inventory-weighted average purchase cost per good
  (int, 1/10,000 cr units), updated on every coop purchase settle;
  `_apply_produce` stamps baselines from coop VWAP (fallback: book) incl.
  energy. Sell-side unchanged: sellers receive floor; floor now = true cost.
- **A2 Solvency guards** — specialists skip PRODUCE when treasury <
  estimated next-run input cost (VWAP/market based); no more producing
  into insolvency. New alert: coop cannot afford inputs.
- **A3 Buffers + capital refresh + alerts** — utilities stock targets up
  (coal 120, electricity 250, water 250). New votable rule param
  `capital_refresh` {interval_ticks, hand_tools, machines}: every interval,
  each capital-consuming coop below threshold receives tools/machines;
  replacement cost paid from surplus pool and RETIRED (public capital
  maintenance; money leaves supply). Explicit scaffolding until the
  toolsmith milestone makes capital endogenous. New analytics alerts:
  supply halt (good near-zero stock + unmet demand >= 10 ticks),
  coop-insolvency warning.
- **A4 Long-run gate** — pytest: 3 seeds x 2,000 ticks; zero unmet over
  final 500 ticks, all co-ops solvent & producing recently, Gini <= 0.5,
  loop >= 0.6, utilities above floors, money invariant exact every check.

## Out of scope
Money sink for savings (B5-B6), toolsmith chain (C7), Citizen Seat (D10).
