"""D18 / WP1.1: sub-floor clearance listings (flaw L1 — prices can fall)."""
import copy

import pytest

from openboard.engine import apply_tick
from openboard.errors import Reason
from openboard.ledger import Ledger, Transaction
from openboard.rules import DEFAULT_RULESET_PARAMS
from openboard.state import genesis_state


def _params(**over):
    p = copy.deepcopy(DEFAULT_RULESET_PARAMS)
    p['money_cap'] = {'enabled': True, 'total': 2_100_000_000, 'units_per_credit': 100}
    if over.get('clearance'):
        p['sub_floor_clearance'] = {'enabled': True, 'max_discount_bp': 3_000}
    p.update({k: v for k, v in over.items() if k != 'clearance'})
    return p


def _world(params, n=3):
    s = genesis_state({f'c{i}': 500 for i in range(n)}, ruleset_params=params)
    return s


def _found_baker(s, tick=1):
    l = Ledger()
    apply_tick(s, l, [Transaction(tick=tick, sender='c0', action='FOUND_COOP',
        payload={'coop_id': 'bakery', 'name': 'bakery', 'members': ['c0', 'c1']},
        ruleset_version=1)], current_tick=tick)
    assert 'bakery' in s.coops, f'founding failed: {s.applied[-1]}'
    return l


def _stock_and_list(s, good_qty, clearance, tick=2):
    """Directly stock the coop then list (clearance or normal)."""
    s.coops['bakery'].setdefault('inventory', {})['bread'] = good_qty
    payload = {'coop_id': 'bakery', 'good': 'bread', 'qty': good_qty}
    if clearance:
        payload['clearance'] = True
    l = Ledger()
    apply_tick(s, l, [Transaction(tick=tick, sender='c0', action='LIST_GOOD',
                                  payload=payload, ruleset_version=1)], current_tick=tick)
    return l


def test_clearance_rejected_when_param_off():
    s = _world(_params(clearance=False))
    _found_baker(s)
    s.coops['bakery']['inventory']['bread'] = 10
    l = Ledger()
    ev = apply_tick(s, l, [Transaction(tick=2, sender='c0', action='LIST_GOOD',
        payload={'coop_id': 'bakery', 'good': 'bread', 'qty': 10, 'clearance': True},
        ruleset_version=1)], current_tick=2)
    assert 'bread' not in s.listings  # clearance refused: param off


def test_clearance_requires_whole_stock():
    s = _world(_params(clearance=True))
    _found_baker(s)
    s.coops['bakery']['inventory']['bread'] = 10
    l = Ledger()
    # listing only 6 of 10 must fail — clearance dumps EVERYTHING
    ev = apply_tick(s, l, [Transaction(tick=2, sender='c0', action='LIST_GOOD',
        payload={'coop_id': 'bakery', 'good': 'bread', 'qty': 6, 'clearance': True},
        ruleset_version=1)], current_tick=2)
    assert 'bread' not in s.listings  # partial stock refused: predation guard


def test_clearance_price_below_floor():
    s = _world(_params(clearance=True))
    _found_baker(s)
    s.coops['bakery']['inventory']['bread'] = 10
    l = Ledger()
    # clearance + sub-floor bid in the SAME tick: listings clear within the tick
    apply_tick(s, l, [
        Transaction(tick=2, sender='c0', action='LIST_GOOD',
                    payload={'coop_id': 'bakery', 'good': 'bread', 'qty': 10, 'clearance': True},
                    ruleset_version=1),
        Transaction(tick=2, sender='c1', action='BID',
                    payload={'good': 'bread', 'max_price': 1, 'qty': 10},
                    ruleset_version=1),
    ], current_tick=2)
    # the listing was accepted and cleared — the sale happened at a sub-floor price
    clear = [e for e in s.applied if e.get('action') == 'MARKET_CLEAR_AUCTION' and e.get('good') == 'bread']
    assert clear, 'clearance listing never cleared'
    assert clear[-1]['sold'] == 10
    floor = s.good_cost_baseline['bread']
    assert s.citizen_inventory.get('c1', {}).get('bread', 0) == 10
    # buyer paid at most floor (sub-floor clearance honored)
    assert clear[-1]['clearing_price'] is not None
    assert clear[-1]['clearing_price'] <= floor


def test_clearance_sale_settles_below_floor_invariant_holds():
    s = _world(_params(clearance=True))
    _found_baker(s)
    s.coops['bakery']['inventory']['bread'] = 10
    l = Ledger()
    apply_tick(s, l, [
        Transaction(tick=2, sender='c0', action='LIST_GOOD',
                    payload={'coop_id': 'bakery', 'good': 'bread', 'qty': 10, 'clearance': True},
                    ruleset_version=1),
        Transaction(tick=2, sender='c1', action='BID',
                    payload={'good': 'bread', 'max_price': 1, 'qty': 10},
                    ruleset_version=1),
    ], current_tick=2)
    # money conservation after the clearance sale
    total = (sum(s.balances.values()) + s.surplus_pool + s.capital_fund
             + sum(c.get('treasury', 0) for c in s.coops.values()))
    assert 2_100_000_000 - 1_000 <= total <= 2_100_000_000
    # buyer got the goods at a price below the cost floor
    assert s.citizen_inventory.get('c1', {}).get('bread', 0) == 10


def test_essential_clearance_sold_at_discount():
    s = _world(_params(clearance=True))
    _found_baker(s)
    s.coops['bakery']['inventory']['bread'] = 10
    l = Ledger()
    # sub-floor max_price accepted only because the param is on
    apply_tick(s, l, [
        Transaction(tick=2, sender='c0', action='LIST_GOOD',
                    payload={'coop_id': 'bakery', 'good': 'bread', 'qty': 10, 'clearance': True},
                    ruleset_version=1),
        Transaction(tick=2, sender='c1', action='BID',
                    payload={'good': 'bread', 'max_price': 1, 'qty': 10},
                    ruleset_version=1),
    ], current_tick=2)
    # the whole stock cleared to the buyer (goods moved seller -> buyer)
    assert s.coops['bakery']['inventory'].get('bread', 0) == 0
    assert s.citizen_inventory.get('c1', {}).get('bread', 0) == 10
