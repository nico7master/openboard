"""Audit 2026-09-20 P-ECON batch-2 regression battery.

B3  hash_v2 gate (absent = legacy snapshot = old replays bit-identical)
    + faithful clone()/ _clone_coop (loans, demand window, wear, wage-debt).
B7  default quotas carry NO unproducible goods (heating_fuel, medicine).
B9  money_total counts the foreign bucket exactly (conservation in trade worlds).
B10 insolvency backstop daily wage derived from rules (== 800 at defaults).
B11 opt-in post-crisis scarcity clamp (growth capped at decay for N ticks).
A7  opt-in whistleblower penalty: rotation farming goes net-negative.
"""
import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from openboard.breaksystem import money_total  # noqa: E402
from openboard.engine import _update_scarcity, apply_tick  # noqa: E402
from openboard.ledger import Ledger, Transaction  # noqa: E402
from openboard.rules import DEFAULT_RULESET_PARAMS, validate_params  # noqa: E402
from openboard.state import genesis_state  # noqa: E402


# ------------------------------------------------------------------ B7
def test_default_quotas_contain_only_producible_goods():
    from openboard.catalog import RECIPES
    outs = set()
    for r in RECIPES.values():
        outs.update(r.outputs)
    quota = DEFAULT_RULESET_PARAMS["essential_need_quota"]
    unproducible = [g for g in quota if g not in outs]
    assert unproducible == [], f"base catalog cannot produce: {unproducible}"
    validate_params(copy.deepcopy(DEFAULT_RULESET_PARAMS))


def test_hash_v2_is_an_accepted_optional_param():
    p = copy.deepcopy(DEFAULT_RULESET_PARAMS)
    p["hash_v2"] = {"enabled": True}
    validate_params(p)


# ------------------------------------------------------------------ B9
def test_money_total_counts_foreign_bucket_exactly():
    s = genesis_state({"c0": 1_000, "c1": 2_000})
    mt0 = money_total(s)
    assert mt0 == 3_000
    s.foreign_balance = -500  # we exported: the world owes us 500
    assert money_total(s) == mt0 - 500
    s.foreign_balance = 300   # we imported: we owe the world
    assert money_total(s) == mt0 + 300


# ------------------------------------------------------------------ B3
def test_hash_gate_off_by_default_and_on_with_rule():
    s = genesis_state({"c0": 1_000})
    assert s._hash_v2_active() is False
    s.recent_sales["bread"] = 5
    assert "recent_sales" not in s.snapshot_dict()  # legacy hash untouched

    p = copy.deepcopy(DEFAULT_RULESET_PARAMS)
    p["hash_v2"] = {"enabled": True}
    s2 = genesis_state({"c0": 1_000}, ruleset_params=p)
    assert s2._hash_v2_active() is True
    s2.recent_sales["bread"] = 5
    s2.demand_ema["bread"] = 3
    s2.capital_wear["k"] = {"machines": 4}
    snap = s2.snapshot_dict()
    assert snap["recent_sales"] == {"bread": 5}
    assert snap["demand_ema"] == {"bread": 3}
    assert snap["capital_wear"] == {"k": {"machines": 4}}


def test_clone_is_faithful_for_audit_b3_fields():
    p = copy.deepcopy(DEFAULT_RULESET_PARAMS)
    s = genesis_state({"c0": 5_000, "c1": 5_000}, ruleset_params=p)
    s.loans["c0"] = {"principal": 500, "defaulted": True}
    s.recent_sales["bread"] = 7
    s.unserved_bids["grain"] = 2_050
    s.demand_ema["bread"] = 6
    s.capital_wear["k"] = {"machines": 12}
    s.coops["k"] = {"name": "k", "members": ["c0"], "founded_tick": 0,
                    "inventory": {}, "treasury": 100,
                    "wage_debt": {"c0": 900}, "recipe_intent": "r1",
                    "last_produce_tick": 3}
    c = s.clone()
    assert c.loans == s.loans
    assert c.recent_sales == s.recent_sales
    assert c.unserved_bids == s.unserved_bids
    assert c.demand_ema == s.demand_ema
    assert c.capital_wear == s.capital_wear
    assert c.coops["k"]["wage_debt"] == {"c0": 900}
    assert c.coops["k"]["recipe_intent"] == "r1"
    assert c.coops["k"]["last_produce_tick"] == 3
    # deep-copy: mutating the clone must not touch the original
    c.recent_sales["bread"] = 99
    assert s.recent_sales["bread"] == 7


# ------------------------------------------------------------------ B10
def test_backstop_daily_wage_derived_from_rules():
    """units_per_credit=50 -> derived daily wage 400/member vs legacy 800:
    a 130,000 debt (2 members) crosses the derived 150x threshold (120k)
    but NOT the legacy one (240k) -> only the fixed engine assumes it."""
    p = copy.deepcopy(DEFAULT_RULESET_PARAMS)
    p["money_cap"] = {"enabled": True, "total": 2_100_000_000,
                      "units_per_credit": 50}
    p["wage_debt_repay"] = {"repay_bp": 5_000, "pool_backstop": True}
    s = genesis_state({"c0": 100, "c1": 100, "c2": 100}, ruleset_params=p)
    s.coops["k"] = {"name": "k", "members": ["c0", "c1"], "founded_tick": 0,
                    "inventory": {}, "treasury": 0,
                    "wage_debt": {"c0": 130_000}}
    s.surplus_pool = 200_000
    led = Ledger()
    apply_tick(s, led, [], current_tick=1)
    assumed = [e for e in s.applied if e.get("action") == "WAGE_DEBT_ASSUMED"]
    assert assumed and assumed[0]["assumed"] == 130_000
    assert s.surplus_pool == 200_000 - 130_000
    # default rules also seed citizens up to a 25,000u floor this tick;
    # pin the BACKSTOP DELTA (c0 has exactly the assumed debt on top of it)
    assert s.balances["c1"] == s.balances["c2"] == 25_000
    assert s.balances["c0"] == s.balances["c1"] + 130_000


def test_backstop_still_800_in_legacy_non_cap_worlds():
    p = copy.deepcopy(DEFAULT_RULESET_PARAMS)
    p.pop("money_cap", None)
    p["wage_debt_repay"] = {"repay_bp": 5_000, "pool_backstop": True}
    s = genesis_state({"c0": 100, "c1": 100}, ruleset_params=p)
    s.coops["k"] = {"name": "k", "members": ["c0", "c1"], "founded_tick": 0,
                    "inventory": {}, "treasury": 0,
                    "wage_debt": {"c0": 130_000}}  # < 2*800*150 = 240k
    s.surplus_pool = 200_000
    led = Ledger()
    apply_tick(s, led, [], current_tick=1)
    assert not [e for e in s.applied if e.get("action") == "WAGE_DEBT_ASSUMED"]


# ------------------------------------------------------------------ B11
def _scar_state(crisis=None):
    s = genesis_state({"c0": 1_000})
    s.crisis = crisis or {}
    return s


def test_scarcity_grows_at_full_step_without_clamp_key():
    s = _scar_state()
    p = {"scarcity_pricing": {"enabled": True, "max_markup_bp": 2_500,
                              "step_bp": 500, "decay_bp": 250}}
    _update_scarcity(s, {"bread": 10}, {"bread": 0}, p, tick=50)
    assert s.scarcity_signal["bread"] == 500


def test_post_crisis_clamp_caps_growth_at_decay_rate():
    p = {"scarcity_pricing": {"enabled": True, "max_markup_bp": 2_500,
                              "step_bp": 500, "decay_bp": 250,
                              "post_crisis_clamp_ticks": 10}}
    s = _scar_state({"active": False, "ended_tick": 40})
    _update_scarcity(s, {"bread": 10}, {"bread": 0}, p, tick=45)  # inside window
    assert s.scarcity_signal["bread"] == 250
    _update_scarcity(s, {"bread": 10}, {"bread": 0}, p, tick=60)  # window over
    assert s.scarcity_signal["bread"] == 250 + 500


def test_active_crisis_still_zeroes_signal():
    p = {"scarcity_pricing": {"enabled": True, "max_markup_bp": 2_500,
                              "step_bp": 500, "decay_bp": 250,
                              "post_crisis_clamp_ticks": 10}}
    s = _scar_state({"active": True})
    s.scarcity_signal["bread"] = 900
    _update_scarcity(s, {"bread": 10}, {"bread": 0}, p, tick=5)
    assert s.scarcity_signal.get("bread", 0) == 0


# ------------------------------------------------------------------ A7
def _wb_world(extra_wb):
    p = copy.deepcopy(DEFAULT_RULESET_PARAMS)
    p["scarcity_pricing"] = {"enabled": False, "max_markup_bp": 2_500,
                             "step_bp": 500, "decay_bp": 250}
    p["whistleblower"] = {"enabled": True, "reward_credits": 500,
                          "max_per_tick": 10, **extra_wb}
    s = genesis_state({"c0": 100_000, "c1": 100_000, "c2": 1_200},
                      ruleset_params=p)
    s.surplus_pool = 100_000
    s.flags.append({"tick": 1, "kind": "HOARD", "target": "c2",
                    "good": "bread", "held": 100, "threshold": 50})
    return s, Ledger()


def test_penalty_taken_from_flagged_into_pool():
    s, led = _wb_world({"penalty_credits": 1_000})
    pool0, v0, r0 = s.surplus_pool, s.balances["c2"], s.balances["c0"]
    r = _R(s, led)
    r.run([r.tx("c0", "REPORT", {"kind": "HOARD", "target": "c2"})])
    assert led.records[-1].accepted
    paid = [e for e in s.applied if e.get("action") == "WHISTLEBLOWER_PAID"]
    assert paid and paid[0]["penalty_taken"] == 1_000
    assert s.balances["c0"] == r0 + 500          # bounty
    assert s.balances["c2"] == v0 - 1_000        # penalty
    assert s.surplus_pool == pool0 - 500 + 1_000  # net +500 per caught rotation


def test_penalty_clamped_at_balance_no_negatives():
    s, led = _wb_world({"penalty_credits": 5_000})
    v0 = s.balances["c2"]  # 1,200
    r = _R(s, led)
    r.run([r.tx("c0", "REPORT", {"kind": "HOARD", "target": "c2"})])
    assert led.records[-1].accepted
    assert s.balances["c2"] == 0
    paid = [e for e in s.applied if e.get("action") == "WHISTLEBLOWER_PAID"]
    assert paid[0]["penalty_taken"] == v0


def test_no_penalty_key_replays_legacy():
    s, led = _wb_world({})
    v0 = s.balances["c2"]
    r = _R(s, led)
    r.run([r.tx("c0", "REPORT", {"kind": "HOARD", "target": "c2"})])
    assert led.records[-1].accepted
    assert s.balances["c2"] == v0  # untouched
    paid = [e for e in s.applied if e.get("action") == "WHISTLEBLOWER_PAID"]
    assert paid[0]["penalty_taken"] == 0


class _R:
    def __init__(self, s, led):
        self.s, self.led = s, led
        self.now = s.tick

    def run(self, txs):
        self.now += 1
        apply_tick(self.s, self.led, txs, current_tick=self.now)

    def tx(self, sender, action, payload):
        return Transaction(tick=self.now + 1, sender=sender, action=action,
                           payload=payload, ruleset_version=self.s.ruleset_version)
