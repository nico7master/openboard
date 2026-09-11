# Spec: Realism Contract L5 — Foreign Sector (2026-09-11)

Status: approved (user go, 2026-09-11). Realism Contracts standard.

## Real-world contract

- DIRECTION: open economies arbitrage the world price: import what is
  cheaper abroad, export what earns more abroad. World-price shocks
  transmit into domestic scarcity/prices; trade cheapens consumption
  and drains domestic stock when world prices exceed domestic cost
  (export booms can STARVE domestic buyers - the classic food-export
  famine pattern).
- MECHANISM: one exogenous PRICE-TAKER world market (unlimited quantity
  at the posted price). Two new citizen/coop actions: EXPORT_GOOD sells
  inventory to the world at world_price (domestic stock leaves, foreign
  balance grows); IMPORT_GOOD buys from the world at world_price x
  (10000 + tariff_bp) // 10000 (tariff = votable friction; revenue ->
  surplus pool). World prices are an integer table in params (no rng);
  foreign_shock events (tick-scheduled in params) shift a good's price
  deterministically for adversary-lab terms-of-trade attacks.
- MAGNITUDE: default world prices ~ 2x domestic cost baselines for
  essentials (imports are the expensive backstop) and ~ 1.2x for
  luxuries/surplus goods (exports profitable); tariff default 0.
- FLIP: params['foreign_sector'] absent => closed economy, byte-
  identical. Conservation: the foreign sector holds a REAL bucket
  (state.foreign_balance) - total money is still constant, the identity
  gains one bucket (engine invariant + test_fixed_supply updated).

## Design

- state.foreign_balance: int (money the world owes us / we owe, netted
  in one bucket; starts 0). Absent-when-default snapshot compat.
- params: foreign_sector {enabled, world_prices: {good: int units},
  tariff_bp: 0, shocks: [{tick, good, price}]}. validate_params block.
- _validate/_apply for IMPORT_GOOD {good, qty} (buyer pays world price
  x tariff into the WORLD's offer; goods to citizen/coop inventory,
  money -> foreign_balance) and EXPORT_GOOD {good, qty} (escrow-checked
  inventory leaves to the world, foreign_balance pays from its bucket;
  foreign_balance >= 0 enforced - the world only buys what we first
  sold it; this keeps the foreign sector a conserved counterparty).
- World trades settle at price x qty exactly; integer floors.

## Contract tests (tests/test_realism_foreign.py)

export then import round-trip conservation (all buckets incl. foreign);
tariff revenue -> pool; import pricier than domestic => bots untouched
(rule adds capacity, never forced); shock flips export profitability;
foreign_balance >= 0 invariant; rule-off replay identity.
