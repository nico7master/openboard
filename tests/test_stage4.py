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
    # true-need balance: on the cycle day the kcal group is short (2 meat
    # = 500 kcal < 2900), so the compensating pass eats up to the 2x
    # preference ceiling (the buy-ahead pairing): 2 + 2 = 4 eaten.
    # Meat alone still can't meet the budget -> 'food' streak recorded.
    assert s.citizen_inventory["c0"]["meat"] == 6
    assert "food" in s.unmet_needs["c0"]


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
    """Audit 2026-09-20 B7 (updated contract): every default-quota good must
    be PRODUCIBLE by the base catalog. Coverage alone was the old pin — but
    heating_fuel/medicine sat in the quotas with NO base recipe, recording
    permanent fake unmet in base-catalog worlds. Quota coverage that the
    economy cannot satisfy is fake starvation, not coverage."""
    from openboard.catalog import RECIPES
    q = DEFAULT_RULESET_PARAMS["essential_need_quota"]
    outs = set()
    for r in RECIPES.values():
        outs.update(r.outputs)
    for g in ("transport", "clothing", "education", "childcare", "books",
              "furniture", "household_goods", "maintenance"):
        assert g in q, f"need-good {g} missing from essential_need_quota — silently unbought"
    unproducible = [g for g in q if g not in outs]
    assert unproducible == [],         f"quota goods the base catalog cannot produce: {unproducible} (fake unmet)"


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


# --------------------------------------------- cold-start bridges (Stage 4)

def test_primitive_extraction_bridges_exist_and_labor_only():
    for rid, out in (
        ("primitive_iron_mining", "iron_ore"),
        ("primitive_coal_mining", "coal"),
        ("primitive_logging", "timber"),
        ("primitive_quarrying", "stone"),
        ("primitive_sand_extraction", "sand"),
    ):
        assert rid in EXTENDED_RECIPES, rid
        r = EXTENDED_RECIPES[rid]
        assert not r.inputs, f"{rid} must be labor-only"
        assert r.outputs == {out: r.outputs[out]}


def test_primitive_bridges_are_worse_than_capital_production():
    # per-unit labor must exceed the capital recipe's, so bridges retire
    # naturally once real capital circulates
    def labor_per_unit(r):
        return r.labor_hours / sum(r.outputs.values())
    assert labor_per_unit(EXTENDED_RECIPES["primitive_iron_mining"]) > labor_per_unit(RECIPES["iron_mining"])
    assert labor_per_unit(EXTENDED_RECIPES["primitive_coal_mining"]) > labor_per_unit(RECIPES["coal_mining"])
    assert labor_per_unit(EXTENDED_RECIPES["primitive_logging"]) > labor_per_unit(RECIPES["logging"])


def test_specialist_falls_back_when_capital_missing():
    # endowment-free world: the miner bot must PRODUCE via the primitive
    # bridge when machines are absent and unlisted
    from openboard.sim import make_specialist
    import random
    s = _state({"extended_catalog": True})
    s.coops["c0coop"] = {
        "members": ["c0"], "treasury": 0, "labor_pool_hours": 10_000,
        "inventory": {}, "recipe_intent": None,
    }
    # map c0 into the coop
    s.coops["c0coop"]["members"].append("c0")
    bot = make_specialist("coal_mining", "coal", {}, stock_target=10,
                          fallback_recipe_id="primitive_coal_mining")
    txs = bot("c0", s, s.active_ruleset_params(), 2, random.Random(1))
    produces = [t for t in txs if t.action == "PRODUCE"]
    assert produces, "miner never produced"
    assert produces[0].payload["recipe_id"] == "primitive_coal_mining"


def test_specialist_uses_capital_recipe_when_listed():
    # with machines listed and affordable, the same bot must use the REAL
    # recipe (bridge must not fire while capital is buyable)
    from openboard.sim import make_specialist
    import random
    s = _state({"extended_catalog": True})
    s.coops["c0coop"] = {
        "members": ["c0"], "treasury": 10_000, "labor_pool_hours": 10_000,
        "inventory": {"hand_tools": 2, "machines": 1, "electricity": 500}, "recipe_intent": None,
    }
    bot = make_specialist("coal_mining", "coal", {}, stock_target=10,
                          fallback_recipe_id="primitive_coal_mining")
    txs = bot("c0", s, s.active_ruleset_params(), 2, random.Random(1))
    produces = [t for t in txs if t.action == "PRODUCE"]
    assert produces
    assert produces[0].payload["recipe_id"] == "coal_mining"


def test_coop_recipe_intent_includes_extended_recipes():
    # steelworks/machine_works declare *_batch recipes from the extended
    # catalog — intent=None froze them at treasury 0 (first-run advance
    # skipped them). The lookup must accept extended recipes.
    import sys
    sys.path.insert(0, "dashboard")
    from server import _coop_recipe_intent, SPECIALISTS
    plan = {"members": ["steel_a"]}
    assert _coop_recipe_intent(plan) == "steelmaking_batch"
    plan = {"members": ["mach_a"]}
    assert _coop_recipe_intent(plan) == "machine_building_batch"
    plan = {"members": ["miner_a"]}
    assert _coop_recipe_intent(plan) == "coal_mining"


# --------------------------------------- producer input priority (Stage 4)

def _mk_state_for_pip():
    s = _state({"extended_catalog": True, "fair_clearing": True,
                "producer_input_priority": {"enabled": True, "share_cap_bp": 5_000}})
    s.coops["bakers"] = {
        "members": ["c0"], "treasury": 1_000, "labor_pool_hours": 0,
        "inventory": {"bread": 100}, "recipe_intent": "flour_to_bread",
    }
    s.coops["kitchen"] = {
        "members": ["c1"], "treasury": 1_000, "labor_pool_hours": 0,
        "inventory": {}, "recipe_intent": "meal_service",
    }
    s.balances["c0"] = 500
    s.balances["c1"] = 500
    s.good_cost_baseline["bread"] = 3
    s.listings["bread"] = [{"coop_id": "bakers", "qty": 10, "floor": 3, "listed_tick": 2}]
    return s


def test_producer_input_priority_serves_producer_first():
    from openboard.ledger import Ledger
    from openboard.engine import Transaction
    s = _mk_state_for_pip()
    # kitchen bids 10 bread (coop), citizen bids 10 bread (essential)
    txs = [
        Transaction(2, "c1", "BID_FOR_COOP", {"coop_id": "kitchen", "good": "bread", "max_price": 3, "qty": 10}),
        Transaction(2, "c0", "BUY_ESSENTIAL", {"good": "bread", "qty": 1}),
    ]
    led = Ledger()
    apply_tick(s, led, txs, current_tick=2)
    # producer claimed its share (5 of 10) at floor; citizen got the rest
    assert s.coops["kitchen"]["inventory"].get("bread", 0) >= 5
    assert s.coops["kitchen"]["treasury"] < 1_000


def test_producer_input_priority_inert_without_rule():
    from openboard.ledger import Ledger
    from openboard.engine import Transaction
    s = _mk_state_for_pip()
    s.active_ruleset_params()["producer_input_priority"] = None
    txs = [
        Transaction(2, "c1", "BID_FOR_COOP", {"coop_id": "kitchen", "good": "bread", "max_price": 3, "qty": 10}),
    ]
    led = Ledger()
    apply_tick(s, led, txs, current_tick=2)
    # without the rule the producer claim pass never runs: essential/auction
    # ordering is unchanged (replay-safe)
    evs = [e for e in s.applied if e.get("action") == "PRODUCER_INPUT_CLEAR"]
    assert not evs


def test_producer_input_priority_no_self_dealing():
    from openboard.ledger import Ledger
    from openboard.engine import Transaction
    s = _mk_state_for_pip()
    # bakers bid on their OWN bread listing: must not buy from themselves
    txs = [
        Transaction(2, "c0", "BID_FOR_COOP", {"coop_id": "bakers", "good": "bread", "max_price": 3, "qty": 10}),
    ]
    led = Ledger()
    apply_tick(s, led, txs, current_tick=2)
    # self-bid bought nothing: treasury untouched, and the (synthetic)
    # listing's 10 unsold units returned to inventory: 100 + 10
    assert s.coops["bakers"]["treasury"] == 1_000
    assert s.coops["bakers"]["inventory"].get("bread", 0) == 110
    evs = [e for e in s.applied if e.get("action") == "PRODUCER_INPUT_CLEAR"]
    assert not evs
