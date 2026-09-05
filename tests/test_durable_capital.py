"""D19 / WP-breadth: durable capital (design-level flaw — machines were
CONSUMED per production run, pricing ~12.6 member-days of capital into
every 24-coal run, energy-rationing the whole breadth economy).
Machines/hand_tools are now OWNED EQUIPMENT with wear, not ingredients."""
import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from openboard.engine import _apply_produce, _validate_produce
from openboard.ledger import Ledger, Transaction
from openboard.rules import DEFAULT_RULESET_PARAMS
from openboard.state import genesis_state


def _params(**over):
    p = copy.deepcopy(DEFAULT_RULESET_PARAMS)
    p['money_cap'] = {'enabled': True, 'total': 2_100_000_000, 'units_per_credit': 100}
    if over.pop('durable', None) is None:
        p['durable_capital'] = {'enabled': True, 'goods': ['machines', 'hand_tools'], 'durability': 20}
    p.update(over)
    return p


def _world(p, n=3):
    s = genesis_state({f'c{i}': 500 for i in range(n)}, ruleset_params=p)
    # a coal recipe that consumes 1 machine per run in the legacy model
    s.recipes['coal_mining'] = {
        'inputs': {'machines': 1}, 'energy': 0, 'labor_hours': 10,
        'outputs': {'coal': 24},
    }
    s.coops['mine'] = {
        'members': ['c0'], 'treasury': 1_000_000,
        'inventory': {'machines': 2}, 'labor_pool_hours': 10_000,
        'recipe_intent': 'coal_mining', 'trade': 'coal_mining',
    }
    s.balances['c0'] = 100_000
    return s


def _tx(tick, runs, recipe_id='coal_mining'):
    return Transaction(tick=tick, sender='c0', action='PRODUCE',
                       payload={'coop_id': 'mine', 'recipe_id': recipe_id, 'runs': runs},
                       ruleset_version=1)


def test_one_machine_serves_many_runs():
    # legacy model: 50 runs need 50 machines. Durable: 2 owned suffice.
    p = _params()
    s = _world(p)
    assert _validate_produce(s, _tx(1, 50), p) is None


def test_legacy_mode_still_consumes_per_run():
    p = _params(durable={'enabled': False})
    s = _world(p)
    assert _validate_produce(s, _tx(1, 50), p) is not None  # 2 < 50 machines


def test_wear_consumes_one_unit_per_durability_runs():
    p = _params()
    s = _world(p)
    ev = _apply_produce(s, _tx(1, 30), p)  # durability 20 -> 1 machine worn out
    assert s.coops['mine']['inventory']['machines'] == 1
    assert s.capital_wear['mine']['machines'] == 10  # 30 - 20, carry-over


def test_no_consumption_below_durability():
    p = _params()
    s = _world(p)
    _apply_produce(s, _tx(1, 19), p)
    assert s.coops['mine']['inventory']['machines'] == 2  # untouched


def test_outputs_full_scale_regardless_of_machine_count():
    p = _params()
    s = _world(p)
    ev = _apply_produce(s, _tx(1, 40), p)
    assert ev['outputs']['coal'] == 24 * 40  # machines never capped output


def test_baseline_amortizes_capital_over_durability():
    p = _params()
    s = _world(p)
    s.good_cost_baseline['machines'] = 20_000  # 20k units per machine
    ev = _apply_produce(s, _tx(1, 20), p)
    # labor 10h*40runs*100upc = 40_000 ; capital 20_000/20*40 = 40_000 amortized
    # total 80_000 over 960 coal -> 84 (ceil)
    assert ev['cost_baselines']['coal'] == 84


def test_wear_resets_when_stock_gone():
    p = _params()
    s = _world(p)
    s.coops['mine']['inventory']['machines'] = 1
    _apply_produce(s, _tx(1, 25), p)  # machine worn out at 20, stock 0
    assert s.coops['mine']['inventory']['machines'] == 0
    assert s.capital_wear['mine']['machines'] == 0  # counter resets; validation will now fail
    assert _validate_produce(s, _tx(2, 1), p) is not None


def test_capital_wear_absent_in_legacy_worlds():
    # replay safety: worlds without the param never touch the new field
    p = _params(durable={'enabled': False})
    s = _world(p)
    _apply_produce(s, _tx(1, 1), p)
    assert s.capital_wear.get('mine') is None
