"""Stage 4 breadth tests: recipes, cycles, fair clearing, quota coverage."""
import copy
import sys
from collections import Counter

import pytest

from openboard.catalog import EXTENDED_RECIPES, GOODS, RECIPES
from openboard.engine import apply_tick
from openboard.errors import Reason
from openboard.ledger import Ledger
from openboard.rules import DEFAULT_RULESET_PARAMS, validate_params
from openboard.state import genesis_state


def _state(params=None):
    p = copy.deepcopy(DEFAULT_RULESET_PARAMS)
    if params:
        p.update(params)
    citizens = {f"c{i}": 500 for i in range(6)}
    return genesis_state(citizens, ruleset_params=p)


# --------------------------------------------------------------- recipes


def test_new_recipes_exist_and_valid():
    for rid in ("heating_fuel_refining", "herbal_medicine", "primitive_toolmaking"):
        assert rid in EXTENDED_RECIPES, rid
        r = EXTENDED_RECIPES[rid]
        assert r.labor_hours > 0
        assert r.outputs
        for g in list(r.inputs) + list(r.outputs):
            assert g in GOODS, g


def test_every_good_has_a_producing_recipe():
    produced = set()
    for r in list(RECIPES.values()) + list(EXTENDED_RECIPES.values()):
        produced.update(r.outputs.keys())
    missing = [g for g in GOODS if g not in produced]
    assert not missing, f"goods with no recipe: {missing}"


def test_primitive_toolmaking_is_labor_only():
    r = EXTENDED_RECIPES["primitive_toolmaking"]
    assert not r.inputs
    assert r.outputs == {"hand_tools": 1}


# ------------------------------------------------------------ needs_cycle


def _full(**overrides):
    p = copy.deepcopy(DEFAULT_RULESET_PARAMS)
    p.update(overrides)
    return p


def test_needs_cycle_validation():
    goods = set(GOODS)
    assert validate_params(_full(needs_cycle={"meat": 25}), known_goods=goods) is None
    for bad in ({"meat": 0}, {"meat": -1}, {"meat": True}, {"meat": 1.5}, {"nope": 2}):
        assert validate_params(_full(needs_cycle=bad), known_goods=goods) == Reason.INVALID_RULESET


def test_needs_cycle_defers_consumption_to_cycle_day():
    # meat quota 2 every 25 ticks: no consumption on non-cycle days
    params = {
        "needs": {"meat": 2},
        "needs_cycle": {"meat": 25},
        "essential_need_quota": {"meat": 2},
        "triage_overrides": {"meat": "essential"},   }
    s = _state(params)
    s.citizen_inventory.setdefault("c0", {})["meat"] = 10
    for t in range(2, 25):  # ticks 2..24: no cycle day yet (cycle days: t%25==0)
        apply_tick(s, Ledger(), [], current_tick=t)
    assert s.citizen_inventory["c0"]["meat"] == 10  # nothing consumed yet
    apply_tick(s, Ledger(), [], current_tick=25)  # cycle day
    assert s.citizen_inventory["c0"]["meat"] == 8


def test_needs_cycle_off_replays_legacy():
    # without needs_cycle, quota 1 consumed every tick as before
    s = _state({"needs": {"meat": 1}})
    s.citizen_inventory["c0"]["meat"] = 5
    for t in range(2, 7):
        apply_tick(s, Ledger(), [], current_tick=t)
    assert s.citizen_inventory["c0"]["meat"] == 0


# ---------------------------------------------------------- fair clearing


def _scarce_world(fair: bool):
    # 4 citizens bid for 1 loaf per tick; deterministic FCFS vs rotation
    params = {
        "needs": {"bread": 1},
        "essential_need_quota": {"bread": 1},
        "fair_clearing": fair,
    }
    s = _state(params)
    # producer coop as a plain state dict (state.py stores coops as dicts)
    s.coops["bakery"] = {
        "coop_id": "bakery", "name": "bakery", "members": ["c9"],
        "founded_tick": 1, "inventory": {}, "labor_pool_hours": 0,
        "treasury": 0,
    }
    s.balances["c9"] = 0
    # drain the genesis bootstrap endowment — otherwise the common pool
    # supplies everyone and the world is not actually scarce
    s.common_pool.clear()
    return s


def _run_scarce(s):
    led = Ledger()
    got = Counter()
    from openboard.ledger import Transaction
    for t in range(2, 22):
        # the bakery produces one loaf per tick
        s.coops["bakery"]["inventory"]["bread"] = 1
        txs = [Transaction(tick=t, sender="c9", action="LIST_GOOD",
                           payload={"coop_id": "bakery", "good": "bread", "qty": 1},
                           ruleset_version=s.ruleset_version)]
        txs += [Transaction(tick=t, sender=f"c{i}", action="BUY_ESSENTIAL",
                            payload={"good": "bread", "qty": 1},
                            ruleset_version=s.ruleset_version) for i in range(4)]
        pre = len(led.records)
        apply_tick(s, led, txs, current_tick=t)
        # deliveries are recorded on MARKET_CLEAR_ESSENTIAL events;
        # bought bread is consumed same-tick so inventories net to zero
        for e in s.applied:
            if e.get("action") == "MARKET_CLEAR_ESSENTIAL" and e.get("tick") == t:
                for b in e.get("buyers", []):
                    got[b["bidder"]] += b["qty"]
    return got


def test_fair_clearing_rotates_scarce_bread():
    s = _scarce_world(fair=True)
    got = _run_scarce(s)
    # rotation: every citizen actually received bread within 20 ticks
    assert set(got.keys()) == {"c0", "c1", "c2", "c3"}


def test_legacy_clearing_stays_fcfs_when_off():
    s = _scarce_world(fair=False)
    got = _run_scarce(s)
    # legacy FCFS: c0 always first in line, others starve
    assert set(got.keys()) == {"c0"}


def test_fair_clearing_validation():
    assert validate_params(_full(fair_clearing=True)) is None
    assert validate_params(_full(fair_clearing="yes")) == Reason.INVALID_RULESET


# ---------------------------------------------------------- quota coverage


def test_default_quota_covers_stage4_need_goods():
    q = DEFAULT_RULESET_PARAMS["essential_need_quota"]
    for g in ("transport", "clothing", "education", "childcare", "books",
              "furniture", "household_goods", "maintenance", "medicine"):
        assert g in q, f"need-good {g} missing from essential_need_quota — silently unbought"


def test_extended_catalog_gate_keeps_old_saves_replaying():
    # extended recipes absent when the rule is off
    from openboard.state import genesis_state as gs
    p = copy.deepcopy(DEFAULT_RULESET_PARAMS)
    p["extended_catalog"] = False
    s = gs({"a": 500}, ruleset_params=p)
    assert "primitive_toolmaking" not in s.recipes


def test_treasuries_never_negative_and_baselines_positive():
    """Regression: overdraft paths pushed treasuries negative (-3,744 on
    dairy), which poisoned VWAP baselines to negative values (-279 cheese).
    All charge sites clamp at 0; stamped baselines clamp at >=1."""
    import random
    sys.path.insert(0, 'dashboard')
    from server import Run
    run = Run(seed=1)
    s, led = run.state, run.ledger
    for t in range(2, 302):
        actions = []
        for name, meta in sorted(run.bots.items()):
            r2 = random.Random(f"1:{t}:{name}")
            actions.extend(meta['fn'](name, s, s.active_ruleset_params(), t, r2))
        apply_tick(s, led, actions, current_tick=t)
        assert all(c.get('treasury', 0) >= 0 for c in s.coops.values()), f"t{t}: negative treasury"
        assert all(v >= 1 for v in s.good_cost_baseline.values()), f"t{t}: non-positive baseline"
