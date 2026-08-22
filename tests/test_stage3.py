"""Stage 3: competition & real capital.

- extended catalog activates only via rule param (replay compat)
- capital goods list at any stock (no consumable buffer)
- coops buy tools/machines on the market; replacements happen
- second producers exist in grain/bread/power sectors
"""
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "dashboard"))

from openboard.catalog import EXTENDED_RECIPES, RECIPES  # noqa: E402
from openboard.engine import apply_tick  # noqa: E402
from openboard.ledger import Ledger, Transaction  # noqa: E402
from openboard.state import genesis_state  # noqa: E402


def _tx(t, who, action, payload, version=1):
    return Transaction(tick=t, sender=who, action=action, payload=payload,
                       ruleset_version=version)


# ---------------------------------------------------------------- catalog


def test_extended_catalog_gated():
    base = genesis_state({"a": 100})
    ext = genesis_state({"a": 100}, ruleset_params={
        "extended_catalog": True, "triage_overrides": {}})
    assert "machine_building_batch" not in base.recipes
    assert "machine_building_batch" in ext.recipes
    assert len(ext.recipes) == len(RECIPES) + len(EXTENDED_RECIPES)
    # baselines reflect market reality under the extension
    assert ext.good_cost_baseline["machines"] == 160
    assert ext.good_cost_baseline["hand_tools"] == 25
    # legacy book values unchanged without the param
    assert base.good_cost_baseline["machines"] == 1_500


def test_old_world_replay_unchanged():
    """A pre-Stage-3 world must hash identically to its recorded history."""
    from openboard.replay import InputLog, record_history, replay

    def build(t):
        return [_tx(t, "a", "WORK", {"coop_id": "farmers", "hours": 8}, 1)]

    log, _, _ = record_history(
        {"a": 500, "b": 500},
        {t: build(t) for t in range(2, 12)},
    )
    result = replay(log)
    assert result.ok, f"replay broke: tick {result.mismatch_tick}"


# ------------------------------------------------------- capital listing


def _world_with_capital_coop(params=None):
    p = dict(params or {})
    p.setdefault("triage_overrides", {})
    s = genesis_state({"w": 5_000, "m": 100, "m2": 100}, ruleset_params=p)
    led = Ledger()
    apply_tick(s, led, [
        _tx(1, "w", "FOUND_COOP", {"coop_id": "toolworks",
                                    "name": "toolworks",
                                    "members": ["w", "m"]}),
    ], current_tick=1)
    s.coops["toolworks"]["inventory"]["hand_tools"] = 4
    return s, led


def test_capital_goods_list_below_buffer():
    """machine_works held 8 machines and could never list them — deadlock.
    Capital goods must list at any stock."""
    from openboard.sim import make_specialist

    bot = make_specialist("hand_tools_craft", "hand_tools",
                          {"steel": 2, "lumber": 1}, stock_target=60)
    s, led = _world_with_capital_coop(
        {"extended_catalog": True})
    s.coops["toolworks"]["inventory"]["hand_tools"] = 4
    acts = bot("w", s, s.active_ruleset_params(), 2, random.Random(1))
    lists = [a for a in acts if a.action == "LIST_GOOD"]
    assert lists, "capital coop with 4 units refused to list (buffer bug)"
    assert lists[0].payload["qty"] == 4


# ------------------------------------------------------------ market flow


def test_coop_buys_machine_on_market():
    """End-to-end: a producer coop lists machines, a consumer coop buys one
    via BID_FOR_COOP, treasury moves, inventory moves. No rule needed."""
    p = {"extended_catalog": True, "triage_overrides": {}}
    s = genesis_state({"seller": 100, "seller2": 100, "buyer": 10_000,
                       "buyer2": 100}, ruleset_params=p)
    led = Ledger()
    apply_tick(s, led, [
        _tx(1, "seller", "FOUND_COOP", {"coop_id": "mach", "name": "mach",
                                        "members": ["seller", "seller2"]}),
        _tx(1, "buyer", "FOUND_COOP", {"coop_id": "mine", "name": "mine",
                                       "members": ["buyer", "buyer2"]}),
    ], current_tick=1)
    s.coops["mach"]["inventory"]["machines"] = 8
    s.coops["mine"]["treasury"] = 5_000  # coop bids pay from treasury
    apply_tick(s, led, [
        _tx(2, "seller", "LIST_GOOD", {"coop_id": "mach", "good": "machines",
                                       "qty": 8}),
        _tx(2, "buyer", "BID_FOR_COOP", {"coop_id": "mine", "good": "machines",
                                         "max_price": 200, "qty": 1}),
    ], current_tick=2)
    assert s.coops["mine"]["inventory"].get("machines") == 1
    assert s.coops["mach"].get("treasury", 0) > 0
    assert s.coops["mach"]["inventory"].get("machines") == 7


# ------------------------------------------------------------ competition


def test_competition_cast_exists():
    from server import BASELINE_BOTS, BASELINE_COOPS
    names = [b[0] for b in BASELINE_BOTS]
    for n in ("farmer_c", "farmer_d", "baker_c", "baker_d",
              "wind_a", "wind_b"):
        assert n in names, f"competition citizen {n} missing"
    coop_ids = {c["coop_id"] for c in BASELINE_COOPS}
    assert {"farmers_north", "city_bakers", "wind_farm"} <= coop_ids
    # two producers per competed sector
    farmers = [c for c in BASELINE_COOPS if c["coop_id"] in ("farmers", "farmers_north")]
    assert len(farmers) == 2


def test_wind_farm_produces_without_inputs():
    """wind_farm recipe is labor-only: renewable power with zero material
    inputs — real competition for coal power."""
    r = EXTENDED_RECIPES["wind_farm"]
    assert r.inputs == {}
    assert r.outputs == {"electricity": 100}


# ------------------------------------------------------- capital backstop


def test_capital_backstop_un_deadlocks_burned_out_coop():
    """A coop that burned its last machine and cannot afford a new one is
    structurally deadlocked (no capital -> no output -> no income). The
    capital fund must provide recipe-required replacement, booked as
    retirement. Coops whose proven recipes need no capital get nothing."""
    p = {"extended_catalog": True, "triage_overrides": {},
         "capital_backstop": {"interval_ticks": 10}}
    s = genesis_state({"m1": 500, "m2": 500}, ruleset_params=p)
    led = Ledger()
    apply_tick(s, led, [
        _tx(1, "m1", "FOUND_COOP", {"coop_id": "miners", "name": "miners",
                                    "members": ["m1", "m2"]}),
    ], current_tick=1)
    # establish proven production: run coal_mining once (needs tools+machine)
    s.coops["miners"]["inventory"].update({"hand_tools": 1, "machines": 1,
                                           "electricity": 100})
    s.coops["miners"]["labor_pool_hours"] = 60
    apply_tick(s, led, [
        _tx(2, "m1", "PRODUCE", {"coop_id": "miners",
                                 "recipe_id": "coal_mining", "runs": 1}),
    ], current_tick=2)
    assert any(e.get("action") == "PRODUCE" and e.get("coop_id") == "miners"
               for e in s.applied), "setup: production failed"
    # now the deadlock: machine burned, treasury below machine price
    s.coops["miners"]["inventory"]["machines"] = 0
    s.coops["miners"]["treasury"] = 50
    s.capital_fund = 5_000
    retired_before = s.money_retired
    for t in range(11, 32):
        apply_tick(s, led, [], current_tick=t)
    assert s.coops["miners"]["inventory"].get("machines", 0) >= 1
    assert s.money_retired > retired_before
    evs = [e for e in s.applied if e.get("action") == "CAPITAL_BACKSTOP"
           and e.get("coop_id") == "miners"]
    assert evs, "no backstop event recorded"


def test_capital_backstop_inert_without_param():
    """Replay compat: no param -> phase never fires."""
    p = {"extended_catalog": True, "triage_overrides": {}}
    s = genesis_state({"m1": 500, "m2": 500}, ruleset_params=p)
    led = Ledger()
    apply_tick(s, led, [
        _tx(1, "m1", "FOUND_COOP", {"coop_id": "miners", "name": "miners",
                                    "members": ["m1", "m2"]}),
    ], current_tick=1)
    s.coops["miners"]["inventory"]["machines"] = 0
    s.coops["miners"]["treasury"] = 50
    s.capital_fund = 5_000
    for t in range(11, 32):
        apply_tick(s, led, [], current_tick=t)
    assert not any(e.get("action") == "CAPITAL_BACKSTOP" for e in s.applied)
