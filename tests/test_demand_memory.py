"""D18 / WP1.4: demand memory (flaw R4 — myopic demand).
Remembered shortage pain keeps buy-ahead elevated AFTER recovery."""
import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from openboard.engine import _memory_bump, _memory_decay, apply_tick
from openboard.ledger import Ledger
from openboard.rules import DEFAULT_RULESET_PARAMS
from openboard.state import genesis_state


def _params(**over):
    p = copy.deepcopy(DEFAULT_RULESET_PARAMS)
    p['money_cap'] = {'enabled': True, 'total': 2_100_000_000, 'units_per_credit': 100}
    if over.pop('dm', None) is None:
        p['demand_memory'] = {'enabled': True, 'bump': 250, 'ceiling_bonus_bp': 5_000}
    p.update(over)
    return p


def _world(p, n=3):
    return genesis_state({f'c{i}': 500 for i in range(n)}, ruleset_params=p)


def test_bump_on_unmet_streak():
    p = _params()
    s = _world(p)
    _memory_bump(s, 'c0', 'cheese', p)
    _memory_bump(s, 'c0', 'cheese', p)
    assert s.shortage_memory['c0|cheese'] == 500


def test_bump_capped_at_1000():
    p = _params()
    s = _world(p)
    for _ in range(10):
        _memory_bump(s, 'c0', 'cheese', p)
    assert s.shortage_memory['c0|cheese'] == 1000


def test_memory_decays_one_percent():
    p = _params()
    s = _world(p)
    s.shortage_memory['c0|cheese'] = 1000
    _memory_decay(s, p)
    assert s.shortage_memory['c0|cheese'] == 990
    # fades to nothing eventually (del when 0)
    for _ in range(2000):
        _memory_decay(s, p)
    assert 'c0|cheese' not in s.shortage_memory


def test_inert_without_param():
    p = _params(dm=None)
    p.pop('demand_memory', None)
    s = _world(p)
    _memory_bump(s, 'c0', 'cheese', p)
    assert s.shortage_memory == {}


def test_snapshot_omits_empty_memory():
    s = _world(_params())
    assert 'shortage_memory' not in s.snapshot_dict()
    s.shortage_memory['c0|cheese'] = 250
    assert s.snapshot_dict()['shortage_memory'] == {'c0|cheese': 250}


def test_unmet_streak_bumps_memory_in_engine():
    p = _params()
    s = _world(p)
    # true-need balance: cheese is a kcal-group food — foods report the
    # single 'food' key, no per-food bumps. Use water (per-good need).
    s.citizen_inventory['c1']['water'] = 0
    needs = (s.active_ruleset_params().get('needs') or {})
    if not needs or 'water' not in needs:
        needs = {'water': 2}
        s.active_ruleset_params()['needs'] = needs
    led = Ledger()
    apply_tick(s, led, [], current_tick=2)
    assert s.shortage_memory.get('c1|water', 0) == 250
