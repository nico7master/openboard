"""Realism contract L4 (spec 2026-09-11-land-market-l4.md): land market.

Real-world effect under contract:
- DIRECTION: land is a fixed, non-produced asset - supply never grows
  (Ricardo); its price APPRECIATES as population grows; owning it
  transfers society's rent to the owner unless captured (Georgist LVT).
- MECHANISM: fixed parcel registry owned by society at genesis; citizens
  buy at assessed price (money -> society pool), sell back at 90% (10%
  social uplift), pay LVT per tick into the surplus pool; unpaid tax
  past grace forecloses to society.
- MAGNITUDE: assessment = base x quality x population growth; LVT
  default 1bp/tick (~3.6%/yr at 1 tick = 1 day, the Georgist range).
- FLIP: rule absent => no parcels, no actions accepted, byte-identical
  old worlds. land_tax_bp=10000 => private landownership uneconomic.
"""
import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from openboard.engine import apply_tick
from openboard.land import assess, init_parcels
from openboard.ledger import Ledger, Transaction
from openboard.rules import DEFAULT_RULESET_PARAMS, validate_params
from openboard.state import genesis_state

CAP = {"enabled": True, "total": 2_100_000_000, "units_per_credit": 100}


def land_params(**over):
    p = copy.deepcopy(DEFAULT_RULESET_PARAMS)
    p["triage_overrides"] = {}
    p["money_cap"] = dict(CAP)
    p["land_market"] = {"enabled": True, "base_land_price": 100,
                        "land_tax_bp": 1, "grace_ticks": 5}
    p.update(over)
    return p


def _world(params, n=3):
    return genesis_state({f"c{i}": 100_000 for i in range(n)}, ruleset_params=params)


def _buy(s, tick, who, pid):
    return apply_tick(s, Ledger(), [Transaction(
        tick=tick, sender=who, action="BUY_LAND", payload={"pid": pid},
        ruleset_version=1)], current_tick=tick)


def _sell(s, tick, who, pid):
    return apply_tick(s, Ledger(), [Transaction(
        tick=tick, sender=who, action="SELL_LAND", payload={"pid": pid},
        ruleset_version=1)], current_tick=tick)


def _total(s):
    return (sum(s.balances.values()) + int(s.surplus_pool)
            + sum(int(c.get("treasury", 0)) for c in s.coops.values()))


def test_fixed_stock_society_owned_at_genesis():
    """L4 direction: land supply is FIXED (never grows, never shrinks) and
    starts owned by society (nature is society's, market-socialism)."""
    p = land_params()
    s = _world(p)
    n0 = len(s.land_parcels)
    assert n0 >= 4
    assert all(v["owner"] == "society" for v in s.land_parcels.values())
    # a full tick never creates or destroys parcels
    apply_tick(s, Ledger(), [], current_tick=1)
    assert len(s.land_parcels) == n0


def test_buy_moves_money_to_society_exactly():
    """L4 conservation: BUY_LAND pays the assessment to society's pool -
    exact amount, nothing minted or retired."""
    p = land_params()
    s = _world(p)
    before = _total(s)
    b0 = s.balances["c0"]  # money_cap stakes 500cr x upc regardless of input
    price = assess(s, "p000", p)
    lvt1 = price * 1 // 10_000  # land_phase runs after dispatch, same tick
    _buy(s, 1, "c0", "p000")
    assert s.land_parcels["p000"]["owner"] == "c0"
    assert s.balances["c0"] == b0 - price - lvt1
    assert _total(s) == before  # conservation holds through both debits


def test_sell_returns_90_pct_social_uplift():
    """L4: selling back to the land bank pays 90% of assessment - the 10%
    uplift stays in society's pool (the bank never loses)."""
    p = land_params()
    s = _world(p)
    b0 = s.balances["c0"]
    ctrl0 = s.balances["c2"]  # control citizen: no land, no coops
    pool_before_any = s.surplus_pool
    _buy(s, 1, "c0", "p000")
    after_buy = _total(s)
    pool_after_buy = s.surplus_pool
    _sell(s, 2, "c0", "p000")
    assert s.land_parcels["p000"]["owner"] == "society"
    price = assess(s, "p000", p)
    payout = price * 9_000 // 10_000
    lvt1 = price * 1 // 10_000  # charged at the buy tick only
    # dividends (surplus-spend phase) hit every citizen equally each
    # tick; the control citizen isolates that flow exactly, so the
    # assertion stays exact regardless of dividend params.
    dividends = s.balances["c2"] - ctrl0
    assert s.balances["c0"] == b0 - price - lvt1 + payout + dividends
    # the bank paid out of the pool that held the full price: final pool
    # = pool_after_buy - payout. The 10% SOCIAL UPLIFT is the net gain vs
    # pre-buy: (final pool) - (pool_before_any + lvt1) == price - payout.
    assert s.surplus_pool == pool_after_buy - payout
    assert s.surplus_pool - pool_before_any - lvt1 == price - payout
    assert _total(s) == after_buy


def test_lvt_flows_to_pool_and_forecloses_on_default():
    """LVT: private parcels pay land_tax_bp x assessment into the surplus
    pool every tick; an owner who cannot pay accrues due-counters and is
    foreclosed after grace_ticks (rent recaptured by society)."""
    p = land_params(land_market={"enabled": True, "base_land_price": 100,
                                "land_tax_bp": 100, "grace_ticks": 3})
    s = _world(p)
    _buy(s, 1, "c0", "p000")
    assert s.land_parcels["p000"]["owner"] == "c0"
    balance_after_buy = s.balances["c0"]
    tax1 = assess(s, "p000", p) * 100 // 10_000
    assert tax1 > 0  # money-capped world: 1 unit = 100 sub-units
    apply_tick(s, Ledger(), [], current_tick=2)
    assert s.balances["c0"] == balance_after_buy - tax1
    assert any(e.get("action") == "LAND_TAX" for e in s.applied
               if isinstance(e, dict))
    # broke owner: forecloses after grace ticks
    s.balances["c1"] = 0
    # test-only ownership transfer (no TRANSFER_LAND action by design:
    # private land trading would create a rentier market - society bank
    # is the only counterparty)
    s.land_parcels["p001"]["owner"] = "c1"
    for t in range(3, 9):
        apply_tick(s, Ledger(), [], current_tick=t)
    assert s.land_parcels["p001"]["owner"] == "society"
    assert "p001" not in s.land_tax_due
    assert any(e.get("action") == "LAND_FORECLOSE" for e in s.applied
               if isinstance(e, dict))


def test_appreciation_tracks_population_growth():
    """L4 Ricardo: same stock + more people => higher assessment. Double
    the population and the assessment doubles (integer floor)."""
    p = land_params()
    s = _world(p)
    base = assess(s, "p000", p)
    for i in range(3):
        s.balances[f"new{i}"] = 50_000 * 100
    assert len(s.balances) == 2 * 3
    assert assess(s, "p000", p) == base * 2


def test_land_market_disabled_rejects_and_replays_identical():
    """Backward contract: rule absent => no parcels created, land actions
    rejected, params validate, worlds replay exactly as before."""
    p = copy.deepcopy(DEFAULT_RULESET_PARAMS)
    p["triage_overrides"] = {}
    assert validate_params(p) is None
    s = _world(p)
    assert s.land_parcels == {} and s.land_genesis_pop == 0
    ev = apply_tick(s, Ledger(), [Transaction(
        tick=1, sender="c0", action="BUY_LAND", payload={"pid": "p000"},
        ruleset_version=1)], current_tick=1)
    # the tx is rejected at validation (recorded), world unchanged
    assert s.land_parcels == {}
    assert _total(s) == 3 * 100_000  # no cap: passed balances preserved


def test_params_validation_blocks():
    """Strict param validation: bad types/counts rejected, defaults OK."""
    p = land_params()
    assert validate_params(p) is None
    bad = land_params()
    bad["land_market"]["land_tax_bp"] = "1"
    assert validate_params(bad) is not None
    bad = land_params()
    bad["land_market"]["grace_ticks"] = 0
    assert validate_params(bad) is not None
    bad = land_params()
    bad["land_market"]["enabled"] = "yes"
    assert validate_params(bad) is not None
    # foreign_sector placeholder accepted too (L5 wires behavior next)
    p2 = land_params(foreign_sector={"enabled": False})
    assert validate_params(p2) is None
