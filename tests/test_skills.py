"""D18 / WP1.3: skills — learning-by-doing, output bonus, wage premium.
User scope: 'someone working for an industry may have good skills and more
output, so a bit higher pay is fine.'"""
import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from openboard.engine import (
    _apply_produce,
    _apply_work,
    _skill_decay,
    _skill_level,
    apply_tick,
)
from openboard.ledger import Ledger, Transaction
from openboard.rules import DEFAULT_RULESET_PARAMS
from openboard.state import genesis_state


def _params(**over):
    p = copy.deepcopy(DEFAULT_RULESET_PARAMS)
    p['money_cap'] = {'enabled': True, 'total': 2_100_000_000, 'units_per_credit': 100}
    if over.pop('skills', None) is None:
        p['skills'] = {'enabled': True, 'hours_per_level': 100, 'max_level': 5,
                       'output_bonus_bp': 500, 'wage_bonus_bp': 300}
    p.update(over)
    return p


def _world(p, n=3):
    return genesis_state({f'c{i}': 500 for i in range(n)}, ruleset_params=p)


def _found(s, led):
    apply_tick(s, led, [Transaction(tick=1, sender='c0', action='FOUND_COOP',
        payload={'coop_id': 'bakery', 'name': 'bakery', 'members': ['c0', 'c1']},
        ruleset_version=1)], current_tick=1)
    assert 'bakery' in s.coops


def _work_tx(tick, who):
    return Transaction(tick=tick, sender=who, action='WORK',
                       payload={'coop_id': 'bakery', 'hours': 8},
                       ruleset_version=1)


def test_skill_accrues_from_work():
    p = _params()
    s = _world(p)
    led = Ledger()
    _found(s, led)
    apply_tick(s, led, [_work_tx(2, 'c0')], current_tick=2)
    assert s.skills.get('c0|bakery') == 8
    assert s.skills.get('c1|bakery', 0) == 0
    assert _skill_level(s, 'c0', 'bakery', p) == 0  # 8 hours << 100


def test_level_up_and_wage_premium():
    p = _params()
    s = _world(p)
    led = Ledger()
    _found(s, led)
    # give c0 max-level skill hours (600; tick-start decay takes 1% -> 594,
    # still level 5) — level applies at work time
    s.skills['c0|bakery'] = 600
    s.coops['bakery']['treasury'] = 100_000 * 100
    apply_tick(s, led, [_work_tx(2, 'c0'), _work_tx(2, 'c1')], current_tick=2)
    # c1 unskilled: base wage; c0 skilled: +3% (integer bp)
    w = [e for e in s.applied if e.get('action') == 'WORK']
    by = {e['sender']: e for e in w}
    assert by['c1']['wage_credits'] == by['c0']['wage_credits'] * 10_000 // 10_300


def test_output_bonus_scales_with_average_skill():
    p = _params()
    s = _world(p)
    led = Ledger()
    _found(s, led)
    # both members at level 2 (200 hours each) -> avg level 2 -> +10% output
    s.skills['c0|bakery'] = 200
    s.skills['c1|bakery'] = 200
    coop = s.coops['bakery']
    # pick any recipe (labor pool is topped up below) and stock inputs for 1 run
    rid = next(iter(s.recipes))
    rec = s.recipes[rid]
    for g, q in rec['inputs'].items():
        coop['inventory'][g] = coop['inventory'].get(g, 0) + q
    if rec['energy']:
        coop['inventory']['electricity'] = coop['inventory'].get('electricity', 0) + rec['energy']
    coop['labor_pool_hours'] = rec['labor_hours'] * 10
    tx = Transaction(tick=2, sender='c0', action='PRODUCE',
                     payload={'coop_id': 'bakery', 'recipe_id': rid, 'runs': 1},
                     ruleset_version=1)
    ev = _apply_produce(s, tx, p)
    for good, base in rec['outputs'].items():
        expected = base + base * 10 // 100  # +10%
        assert coop['inventory'][good] >= expected


def test_skill_decay_when_idle():
    p = _params()
    s = _world(p)
    s.skills['c0|bakery'] = 100
    _skill_decay(s, p)
    assert s.skills['c0|bakery'] == 99  # lost 1% (1)


def test_inert_without_param():
    p = _params(skills=None)
    p.pop('skills', None)
    s = _world(p)
    led = Ledger()
    _found(s, led)
    apply_tick(s, led, [_work_tx(2, 'c0')], current_tick=2)
    assert s.skills == {}  # no skill tracking when disabled


def test_snapshot_omits_empty_skills():
    s = _world(_params())
    assert 'skills' not in s.snapshot_dict()  # old-world hash compat
    s.skills['c0|bakery'] = 50
    assert s.snapshot_dict()['skills'] == {'c0|bakery': 50}


def test_level_capped_at_max():
    p = _params()
    s = _world(p)
    s.skills['c0|bakery'] = 10_000
    assert _skill_level(s, 'c0', 'bakery', p) == 5


def test_decay_runs_inside_apply_tick():
    p = _params()
    s = _world(p)
    led = Ledger()
    _found(s, led)
    s.skills['c0|bakery'] = 1000
    apply_tick(s, led, [], current_tick=2)
    assert s.skills['c0|bakery'] == 990
