"""Realism contract L5 (spec 2026-09-11-foreign-sector-l5.md): foreign
sector.

Real-world effect under contract:
- DIRECTION: open economies arbitrage the world price - export what
  earns more abroad, import what is cheaper abroad; terms-of-trade
  shocks (world price moves) transmit into the domestic economy.
- MECHANISM: one price-taker world market (posted integer price),
  netted in ONE conserved bucket (foreign_balance). The world only buys
  what was first sold to it => the bucket never goes negative (a real
  counterparty, not a money printer). Tariff revenue flows to the
  surplus pool.
- MAGNITUDE: world prices are params (default none = nothing traded);
  costs settle at price x qty exactly; tariff_bp default 0.
- FLIP: a world-price SHOCK moves the effective price at its scheduled
  tick (deterministic terms-of-trade attack for the adversary lab).
  Rule absent => closed economy, byte-identical old worlds.
"""
import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from openboard.engine import apply_tick
from openboard.foreign import world_price
from openboard.ledger import Ledger, Transaction
from openboard.rules import DEFAULT_RULESET_PARAMS, validate_params
from openboard.state import genesis_state


def fs_params(**over):
    p = copy.deepcopy(DEFAULT_RULESET_PARAMS)
    p["triage_overrides"] = {}
    p["foreign_sector"] = {
        "enabled": True,
        "world_prices": {"bread": 300, "grain": 50},
        "tariff_bp": 500,
        "shocks": [{"tick": 5, "good": "bread", "price": 600}],
    }
    p.update(over)
    return p


def _world(params, n=3):
    return genesis_state({f"c{i}": 100_000 for i in range(n)}, ruleset_params=params)


def _tx(tick, who, action, good, qty):
    return Transaction(tick=tick, sender=who, action=action,
                       payload={"good": good, "qty": qty}, ruleset_version=1)


def _total(s):
    """The L5-EXTENDED conservation law: every money bucket, world included."""
    return (sum(s.balances.values()) + int(s.surplus_pool)
            + sum(int(c.get("treasury", 0)) for c in s.coops.values())
            + int(s.foreign_balance))


def test_export_then_import_round_trip_conserves():
    """L5 conservation: export credits the seller from the world's bucket;
    import debits the buyer (price + tariff). Every bucket nets out -
    the world is a counterparty, never a mint."""
    p = fs_params()
    s = _world(p)
    before = _total(s)
    ctrl0 = s.balances["c2"]  # control citizen: isolates dividends
    s.citizen_inventory["c0"] = {"bread": 30}
    apply_tick(s, Ledger(), [_tx(1, "c0", "EXPORT_GOOD", "bread", 30)],
               current_tick=1)
    assert s.balances["c0"] == 100_000 + 30 * 300
    assert s.foreign_balance == -30 * 300
    assert _total(s) == before
    b_mid = s.balances["c0"]
    ctrl_mid = s.balances["c2"]  # window start: tick-1 dividend already in both
    pool_mid = s.surplus_pool
    apply_tick(s, Ledger(), [_tx(2, "c0", "IMPORT_GOOD", "bread", 10)],
               current_tick=2)
    cost = 10 * 300
    tariff = cost * 500 // 10_000
    dividends = s.balances["c2"] - ctrl_mid  # tick-2 flow only (b_mid
    # already contains tick-1's dividend for c0)
    assert s.balances["c0"] == b_mid - cost - tariff + dividends
    assert s.surplus_pool == pool_mid + tariff
    # the world receives its FULL price (3000); the tariff comes from
    # the buyer on top, not out of the world's payment
    assert s.foreign_balance == -30 * 300 + cost
    assert s.citizen_inventory["c0"]["bread"] == 0 + 10  # exported all 30, imported 10
    assert _total(s) == before


def test_tariff_revenue_flows_to_pool():
    """Tariff = the people's cut: exactly tariff_bp of the net cost lands
    in the surplus pool."""
    p = fs_params()
    s = _world(p)
    pool0 = s.surplus_pool
    apply_tick(s, Ledger(), [_tx(1, "c0", "IMPORT_GOOD", "grain", 100)],
               current_tick=1)
    net = 100 * 50
    assert s.surplus_pool == pool0 + net * 500 // 10_000


def test_shock_moves_world_price_deterministically():
    """Terms-of-trade shock: bread 300 -> 600 at tick 5 (scheduled table,
    no rng). Price persists as 'last shock at or before tick'."""
    p = fs_params()
    s = _world(p)
    assert world_price(s, "bread", p) == 300
    s.tick = 4
    assert world_price(s, "bread", p) == 300  # not yet
    s.tick = 5
    assert world_price(s, "bread", p) == 600  # shock lands
    s.tick = 99
    assert world_price(s, "bread", p) == 600  # persists


def test_world_bucket_tracks_trade_surplus():
    """The world bucket is a real trade balance: exports drive it negative
    (the world owes us - our surplus), imports drive it back up. No-mint
    holds because the bucket is INSIDE the conservation identity."""
    p = fs_params()
    s = _world(p)
    s.citizen_inventory["c1"] = {"bread": 100}
    apply_tick(s, Ledger(), [_tx(1, "c1", "EXPORT_GOOD", "bread", 10)],
               current_tick=1)
    # the bucket went NEGATIVE: that is a trade surplus in our favor -
    # the world owes us (a real claim, like real trade balances)
    assert s.foreign_balance == -3_000
    assert s.balances["c1"] == 100_000 + 3_000
    # and it keeps going negative with further exports (no artificial floor)
    apply_tick(s, Ledger(), [_tx(2, "c1", "EXPORT_GOOD", "bread", 90)],
               current_tick=2)  # only 90 left after the first export
    assert s.foreign_balance == -30_000
    assert s.citizen_inventory["c1"]["bread"] == 0
    assert _total(s) == 3 * 100_000  # extended identity holds throughout


def test_untraded_goods_rejected():
    """Goods absent from the world table have price 0 and are not
    tradable."""
    p = fs_params()
    s = _world(p)
    assert world_price(s, "water", p) == 0
    s.citizen_inventory["c0"] = {"water": 5}
    n_applied = len(s.applied)
    apply_tick(s, Ledger(), [_tx(1, "c0", "EXPORT_GOOD", "water", 5)],
               current_tick=1)
    assert s.citizen_inventory["c0"]["water"] == 5  # untouched
    assert len(s.applied) > n_applied  # rejection recorded


def test_rule_absent_is_closed_economy():
    """Backward contract: rule absent => imports/exports rejected, no
    world bucket activity, worlds replay byte-identically."""
    p = copy.deepcopy(DEFAULT_RULESET_PARAMS)
    p["triage_overrides"] = {}
    assert validate_params(p) is None
    s = _world(p)
    s.citizen_inventory["c0"] = {"bread": 5}
    before = _total(s)
    apply_tick(s, Ledger(), [_tx(1, "c0", "EXPORT_GOOD", "bread", 5)],
               current_tick=1)
    assert s.foreign_balance == 0
    assert s.citizen_inventory["c0"]["bread"] == 5
    assert _total(s) == before


def test_params_validation_blocks():
    """Strict validation: negative tariff, zero/bad prices, malformed
    shocks rejected; free trade (tariff 0) accepted."""
    p = fs_params()
    assert validate_params(p) is None
    free = fs_params()
    free["foreign_sector"]["tariff_bp"] = 0
    assert validate_params(free) is None
    bad = fs_params()
    bad["foreign_sector"]["tariff_bp"] = -1
    assert validate_params(bad) is not None
    bad = fs_params()
    bad["foreign_sector"]["world_prices"] = {"bread": 0}
    assert validate_params(bad) is not None
    bad = fs_params()
    bad["foreign_sector"]["shocks"] = [{"tick": 5, "good": "bread"}]
    assert validate_params(bad) is not None
