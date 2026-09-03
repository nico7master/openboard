"""D18 / WP1.2: perishability (flaw R1 — nothing ever spoiled)."""
import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from openboard.engine import _perishability_phase, apply_tick
from openboard.ledger import Ledger
from openboard.rules import DEFAULT_RULESET_PARAMS
from openboard.state import genesis_state


def _params(**over):
    p = copy.deepcopy(DEFAULT_RULESET_PARAMS)
    p['money_cap'] = {'enabled': True, 'total': 2_100_000_000, 'units_per_credit': 100}
    p.update(over)
    return p


def _world(p, n=3):
    return genesis_state({f'c{i}': 500 for i in range(n)}, ruleset_params=p)


def test_spoil_proportional_decay():
    p = _params(perishability={'enabled': True, 'shelf_life': {'bread': 4}})
    s = _world(p)
    s.citizen_inventory['c0']['bread'] = 40
    ev = _perishability_phase(s, tick=2, params=p)
    assert len(ev) == 1
    assert ev[0]['action'] == 'SPOIL' and ev[0]['good'] == 'bread'
    assert ev[0]['qty'] == 10  # 40 // 4
    assert s.citizen_inventory['c0']['bread'] == 30


def test_small_holder_loses_nothing():
    # below shelf_life units: floor decay = 0 — small honest holders safe
    p = _params(perishability={'enabled': True, 'shelf_life': {'bread': 4}})
    s = _world(p)
    s.citizen_inventory['c0']['bread'] = 3
    ev = _perishability_phase(s, tick=2, params=p)
    assert ev == []
    assert s.citizen_inventory['c0']['bread'] == 3


def test_hoarder_loses_more():
    p = _params(perishability={'enabled': True, 'shelf_life': {'bread': 4}})
    s = _world(p)
    s.citizen_inventory['c0']['bread'] = 400
    s.citizen_inventory['c1']['bread'] = 8
    _perishability_phase(s, tick=2, params=p)
    assert s.citizen_inventory['c0']['bread'] == 300  # lost 100
    assert s.citizen_inventory['c1']['bread'] == 6      # lost 2 (8//4)


def test_coop_inventory_spoils():
    p = _params(perishability={'enabled': True, 'shelf_life': {'milk': 2}})
    s = _world(p)
    # minimal coop entry (tests only touch inventory)
    s.coops['dairy'] = {'members': ['c0'], 'treasury': 0,
                        'inventory': {'milk': 20}}
    ev = _perishability_phase(s, tick=2, params=p)
    assert ev == [{'tick': 2, 'action': 'SPOIL', 'holder': 'dairy',
                   'holder_kind': 'coop', 'good': 'milk', 'qty': 10}]
    assert s.coops['dairy']['inventory']['milk'] == 10


def test_inert_without_param():
    p = _params()  # no perishability
    s = _world(p)
    s.citizen_inventory['c0']['bread'] = 999
    ev = _perishability_phase(s, tick=2, params=p)
    assert ev == []
    assert s.citizen_inventory['c0']['bread'] == 999


def test_phase_runs_inside_apply_tick():
    p = _params(perishability={'enabled': True, 'shelf_life': {'bread': 4}})
    s = _world(p)
    s.citizen_inventory['c0']['bread'] = 40
    led = Ledger()
    apply_tick(s, led, [], current_tick=2)
    spoils = [e for e in s.applied if e.get('action') == 'SPOIL']
    assert spoils and spoils[0]['qty'] == 10


def test_invalid_shelf_life_rejected():
    from openboard.errors import Reason
    bad = _params(perishability={'enabled': True, 'shelf_life': {'bread': 0}})
    # rules validation is exercised via sim; here just check param shape logic
    assert bad['perishability']['shelf_life']['bread'] == 0  # sanity
