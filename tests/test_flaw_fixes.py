"""D14/v0.02: fixes for the v0.01 flaw inventory (docs 2026-09-03).
L2 treasury-first wages, L3 pool-funded birth stakes, L4 inventory-inclusive
wealth tax, L5 fair clearing default."""
import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from openboard.demographics import demographics_phase
from openboard.engine import _apply_work, _wealth_tax_phase, apply_tick
from openboard.ledger import Ledger, Transaction
from openboard.rules import DEFAULT_RULESET_PARAMS
from openboard.state import genesis_state


def _params(**over):
    p = copy.deepcopy(DEFAULT_RULESET_PARAMS)
    p.update(over)
    return p


def _world(p):
    return genesis_state({"a": 1000, "b": 1000, "c": 1000}, ruleset_params=p)


def _work_tx(tick, who, coop, hours=8, version=1):
    return Transaction(tick=tick, sender=who, action="WORK",
                       payload={"coop_id": coop, "hours": hours},
                       ruleset_version=version)


def _found(state, ledger, coop_id, members, tick=1):
    apply_tick(state, ledger, [Transaction(tick=tick, sender=members[0],
        action="FOUND_COOP",
        payload={"coop_id": coop_id, "name": coop_id, "members": members},
        ruleset_version=1)], current_tick=tick)


# ---- L2: treasury-first wages

def test_l2_treasury_first_wages():
    p = _params(wage_mint_mode="treasury_first")
    s = _world(p)
    led = Ledger()
    _found(s, led, "bakery", ["a", "b"])
    coop = s.coops["bakery"]
    coop["treasury"] = 10  # can fund only 10 of 8 credits (wage=8/hr)
    minted_before = s.money_minted
    tx = _work_tx(2, "a", "bakery")
    assert _apply_work(s, tx, p)["wage_credits"] == 8
    # 8 credits funded entirely from treasury: no new money
    assert s.money_minted == minted_before
    assert coop["treasury"] == 2
    assert s.balances["a"] == 1000 + 8


def test_l2_treasury_first_shortfall_mints():
    p = _params(wage_mint_mode="treasury_first")
    s = _world(p)
    led = Ledger()
    _found(s, led, "bakery", ["a", "b"])
    coop = s.coops["bakery"]
    coop["treasury"] = 3  # funds 3, mints 5
    minted_before = s.money_minted
    _apply_work(s, _work_tx(2, "a", "bakery"), p)
    assert s.money_minted - minted_before == 5
    assert coop["treasury"] == 0


def test_l2_legacy_mode_mints_all():
    p = _params()  # no wage_mint_mode -> v0.01 behavior
    s = _world(p)
    led = Ledger()
    _found(s, led, "bakery", ["a", "b"])
    s.coops["bakery"]["treasury"] = 10_000
    minted_before = s.money_minted
    _apply_work(s, _work_tx(2, "a", "bakery"), p)
    assert s.money_minted - minted_before == 8  # full mint, treasury untouched


# ---- L3: birth stake from pool

def test_l3_birth_stake_from_pool():
    p = _params(demographics={"enabled": True, "birth_interval_ticks": 2, "adulthood_ticks": 600},
                birth_stake_from_pool=True)
    s = _world(p)
    s.surplus_pool = 800
    minted_before = s.money_minted
    pool_before = s.surplus_pool
    ev = demographics_phase(s, 2, p)
    born = [e for e in ev if e.get("action") == "CITIZEN_BORN"]
    assert born, "birth should fire at tick 2"
    cid = born[0]["citizen"]
    assert s.balances[cid] == 500           # full stake received
    assert s.surplus_pool == pool_before - 500  # society paid
    assert s.money_minted == minted_before      # nothing minted


def test_l3_birth_stake_shortfall():
    p = _params(demographics={"enabled": True, "birth_interval_ticks": 2, "adulthood_ticks": 600},
                birth_stake_from_pool=True)
    s = _world(p)
    s.surplus_pool = 200
    minted_before = s.money_minted
    ev = demographics_phase(s, 2, p)
    cid = [e for e in ev if e.get("action") == "CITIZEN_BORN"][0]["citizen"]
    assert s.balances[cid] == 500
    assert s.money_minted - minted_before == 300  # shortfall minted
    assert s.surplus_pool == 0


def test_l3_legacy_mints_full_stake():
    p = _params(demographics={"enabled": True, "birth_interval_ticks": 2, "adulthood_ticks": 600})
    s = _world(p)
    s.surplus_pool = 800
    minted_before = s.money_minted
    ev = demographics_phase(s, 2, p)
    assert [e for e in ev if e.get("action") == "CITIZEN_BORN"], ev
    assert s.money_minted - minted_before == 500  # legacy


# ---- L4: inventory-inclusive wealth tax

def test_l4_wealth_tax_includes_coop_assets():
    p = _params(wealth_tax={"threshold": 1000, "rate_bp": 1000, "include_inventory": True})
    s = _world(p)
    led = Ledger()
    _found(s, led, "bakery", ["a", "b"])
    coop = s.coops["bakery"]
    good, rec = next(iter(s.recipes.items()))
    # a is modest in balance but rich via coop share: treasury 2000 + inventory
    coop["treasury"] = 2000
    inv_value = sum(s.good_cost_baseline.get(g, 1) * q for g, q in rec["inputs"].items())
    coop["inventory"] = dict(rec["inputs"])
    # sanity: share pushes a over threshold even with low balance
    share = (2000 + inv_value) // 2
    s.balances["a"] = 100  # low liquid balance
    events = _wealth_tax_phase(s, 5, p)
    taxed = [e for e in events if e.get("citizen") == "a"]
    assert taxed, "coop wealth must be taxed"
    assert s.balances["a"] < 100  # taxed from liquid balance


def test_l4_off_by_default_replays():
    p = _params(wealth_tax={"threshold": 1000, "rate_bp": 1000})
    s = _world(p)
    led = Ledger()
    _found(s, led, "bakery", ["a", "b"])
    coop = s.coops["bakery"]
    coop["treasury"] = 50_000  # huge coop wealth, but flag absent
    s.balances["a"] = 100
    events = _wealth_tax_phase(s, 5, p)
    assert [e for e in events if e.get("citizen") == "a"] == []  # balances-only


# ---- L5: fair clearing default

def test_l5_fair_clearing_default_on():
    assert DEFAULT_RULESET_PARAMS.get("fair_clearing") is True
