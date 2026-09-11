# Spec: Realism Contract L4 — Land Market (2026-09-11)

Status: approved (user go, 2026-09-11). Follows the Policy Realism
Contracts standard (2026-09-11-policy-realism-contracts.md).

## Real-world contract

- DIRECTION: land is a FIXED, non-produced asset with inelastic supply
  (Ricardo). Its price appreciates as the economy/population grows. It
  is the canonical non-produced-wealth inequality channel: owners gain
  without producing. Idle land hoarding is socially costly; the Georgist
  answer - a land-value tax capturing the rent for society - prevents
  rentier dead-weight while keeping the use of land cheap.
- MECHANISM: a fixed stock of parcels in a dedicated registry (NOT a
  goods-catalog item: land is never produced). Parcels have integer
  quality tiers. Society owns all parcels at genesis (market socialism:
  nature is society's). Citizens buy parcels at a deterministic assessed
  price or sell back to the society land bank at 90% of assessment.
  Every tick owners pay an LVT (land_tax_bp x assessment) into the
  surplus pool; unpaid tax after grace => foreclosure to society.
  Assessment scales with population (appreciation) x quality_bp.
- MAGNITUDE: LVT default 500bp (5%/tick of assessment) - holding idle
  land is expensive, owning USED land must earn its keep elsewhere
  (v1: appreciation + future lease hooks). Assessment base scaled so a
  parcel costs roughly a skilled worker's monthly wage at genesis.
- FLIP: params['land_market'] absent/disabled => no parcels, no actions,
  byte-identical old worlds. land_tax_bp votable: 0bp = pure private
  rentier world (adversary-lab experiment: Georgism vs rentierism);
  10000bp = land nationalized in effect.

## Design (integer-only, deterministic)

- state.land_parcels: dict pid -> {owner: 'society'|citizen_id,
  quality_bp: int}. pid = 'p<zero-padded index>'. Snapshot only when
  non-empty (hash compat). Created in genesis ONLY when rule enabled.
- Parcel count: max(4, n_citizens // 2). Quality pattern cycles the
  fixed tier list (12000, 10000, 8000) bp by index - no rng.
- Assessment: base_land_price (default 20_000) x quality_bp // 10_000
  x current_citizens // genesis_citizens (integer floor, min 1).
- Actions: BUY_LAND {pid} (buyer pays assessment; seller - society or
  citizen - receives same credit; conservation exact), SELL_LAND {pid}
  (owner only; society pays 90% assessment; 10% land-bank fee ->
  surplus pool).
- LAND_PHASE (per tick, after wages): for each privately-owned parcel,
  tax = assessment x land_tax_bp // 10_000; owner balance -= tax,
  surplus_pool += tax; balance short => OWN event, grace_ticks default
  5 (state.land_tax_due counter), then foreclosure to society.
- Params: land_market {enabled, base_land_price 20_000, land_tax_bp
  500, grace_ticks 5}. validate_params block added (strict types).

## Contract tests (tests/test_realism_land.py)

fixed stock never grows; genesis society-owned; buy/sell conservation
exact (money moves, never mints); LVT flows to pool; appreciation when
population grows; foreclosure flip; rule-off replay identity.
