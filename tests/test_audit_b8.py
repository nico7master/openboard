"""Audit 2026-09-20 B8 (founder design, 2026-09-21): input-advance
entitlement decay/recovery.

Founder: "Make it reduce the grant every month. So that he will need to
look for work soon again. Not lifetime but just simple reduction. Let's
say 5% a month. And for every month he worked normally the grant
recovers again 5% up to Max."

Pins: monthly (not per-event) decay on rescue months; same-month repeats
never stack; clean-work months recover 5% up to max; the entitlement
floor starves serial dependents; absent knobs = pure legacy identity.
"""
import copy
import sys

import pytest

from openboard.engine import _input_advance_phase
from openboard.errors import Reason
from openboard.rules import DEFAULT_RULESET_PARAMS, validate_params
from openboard.state import genesis_state, _clone_coop

sys.path.insert(0, "src")

DECAY = {"max_per_coop": 500, "decay_bp_per_month": 500, "recover_bp_per_month": 500}


def _state(ia=DECAY, pool=1_000_000):
    p = copy.deepcopy(DEFAULT_RULESET_PARAMS)
    p["capital_backstop"] = {"interval_ticks": 1, "input_advance": copy.deepcopy(ia)}
    s = genesis_state({f"c{i}": 500 for i in range(4)}, ruleset_params=p)
    s.surplus_pool = pool
    s.coops["w1"] = {"name": "w1", "members": ["c0", "c1"], "founded_tick": 1,
                     "inventory": {}, "labor_pool_hours": 0, "wage_remainder_bp": 0,
                     "treasury": 10, "recipe_intent": "book_printing"}
    return s


def _ent(s):
    return s.coops["w1"].get("advance_entitlement_bp", 10_000)


# ------------------------------------------------------------- legacy

def test_absent_knobs_is_pure_legacy():
    s = _state(ia={"max_per_coop": 500})
    ev = _input_advance_phase(s, 10, s.active_ruleset_params())
    assert len(ev) == 1
    assert "entitlement_bp" not in ev[0]
    coop = s.coops["w1"]
    assert "advance_entitlement_bp" not in coop
    assert "advance_acct_month" not in coop
    assert "advance_last_rescue_month" not in coop
    assert s.surplus_pool == 1_000_000 - ev[0]["amount"]


def test_validator_accepts_new_keys_and_keeps_legacy_shape():
    base = copy.deepcopy(DEFAULT_RULESET_PARAMS)
    base["capital_backstop"] = {"interval_ticks": 10, "input_advance": copy.deepcopy(DECAY)}
    assert validate_params(base) != Reason.INVALID_RULESET
    legacy = copy.deepcopy(DEFAULT_RULESET_PARAMS)
    legacy["capital_backstop"] = {"interval_ticks": 10, "input_advance": {"max_per_coop": 500}}
    assert validate_params(legacy) != Reason.INVALID_RULESET


@pytest.mark.parametrize("bad", [-1, 10_001, True, "5", 1.5])
def test_validator_rejects_bad_knobs(bad):
    p = copy.deepcopy(DEFAULT_RULESET_PARAMS)
    p["capital_backstop"] = {"interval_ticks": 10,
                             "input_advance": {"max_per_coop": 500, "decay_bp_per_month": bad}}
    assert validate_params(p) is Reason.INVALID_RULESET


def test_clone_preserves_entitlement_fields():
    s = _state()
    _input_advance_phase(s, 10, s.active_ruleset_params())
    c = _clone_coop(s.coops["w1"])
    assert c["advance_entitlement_bp"] == s.coops["w1"]["advance_entitlement_bp"]
    assert c["advance_acct_month"] == s.coops["w1"]["advance_acct_month"]
    assert c["advance_last_rescue_month"] == s.coops["w1"]["advance_last_rescue_month"]


# ------------------------------------------------------------- decay

def test_first_rescue_month_decays_five_percent():
    s = _state()
    ev = _input_advance_phase(s, 10, s.active_ruleset_params())
    assert ev[0]["entitlement_bp"] == 9_500
    assert _ent(s) == 9_500


def test_same_month_repeats_do_not_stack():
    s = _state()
    _input_advance_phase(s, 10, s.active_ruleset_params())
    s.coops["w1"]["treasury"] = 0
    ev2 = _input_advance_phase(s, 12, s.active_ruleset_params())
    assert ev2[0]["entitlement_bp"] == 9_500  # still month 0


def test_each_new_rescue_month_decays_again():
    s = _state()
    _input_advance_phase(s, 10, s.active_ruleset_params())   # month 0 -> 9500
    s.coops["w1"]["treasury"] = 0
    ev = _input_advance_phase(s, 35, s.active_ruleset_params())  # month 1 -> 9000
    assert ev[0]["entitlement_bp"] == 9_000


def test_entitlement_floor_starves_serial_dependents():
    s = _state()
    for m in range(20):  # 20 rescue months -> 0 bp
        s.coops["w1"]["treasury"] = 0
        ev = _input_advance_phase(s, m * 30 + 5, s.active_ruleset_params())
        if m < 20:
            assert _ent(s) == max(0, 10_000 - (m + 1) * 500)
    assert _ent(s) == 0
    # entitlement 0 -> cap 0 -> no grant, pool untouched
    pool_before = s.surplus_pool
    s.coops["w1"]["treasury"] = 0
    ev = _input_advance_phase(s, 20 * 30 + 5, s.active_ruleset_params())
    assert ev == []
    assert s.surplus_pool == pool_before


# ---------------------------------------------------------- recovery

def test_clean_work_month_recovers_five_percent():
    s = _state()
    _input_advance_phase(s, 10, s.active_ruleset_params())   # m0 rescue -> 9500
    s.coops["w1"]["last_produce_tick"] = 45                  # worked in m1, no rescue in m1
    _input_advance_phase(s, 75, s.active_ruleset_params())   # m2 accounting: m1 clean
    assert _ent(s) == 10_000                                  # 9500 + 500, capped at max


def test_rescued_month_is_not_a_clean_month():
    s = _state()
    _input_advance_phase(s, 10, s.active_ruleset_params())   # m0 rescue -> 9500
    s.coops["w1"]["last_produce_tick"] = 15                  # produced in the RESCUE month
    s.coops["w1"]["treasury"] = 0                            # needs rescue again in m1
    ev = _input_advance_phase(s, 45, s.active_ruleset_params())
    assert ev, "month-1 rescue must fire"
    # m0 was rescued (no recovery for it) and m1's own rescue decays:
    # 9500 -> 9000 (work in a rescued month doesn't heal)
    assert _ent(s) == 9_000


def test_recovery_never_exceeds_max():
    # asymmetric knobs: one rescue (9500) then clean work months at +800bp —
    # uncapped that overshoots max; the cap must hold at 10_000
    s = _state(ia={"max_per_coop": 500, "decay_bp_per_month": 500,
                   "recover_bp_per_month": 800})
    _input_advance_phase(s, 10, s.active_ruleset_params())   # m0 rescue -> 9500
    assert _ent(s) == 9_500
    s.coops["w1"]["last_produce_tick"] = 45                  # worked cleanly in m1
    s.coops["w1"]["treasury"] = 10**9                        # never needs rescue again
    for t in (75, 105):
        _input_advance_phase(s, t, s.active_ruleset_params())
        assert _ent(s) <= 10_000
    assert _ent(s) == 10_000  # 9500 + 800 would be 10300: capped at max


# ------------------------------------------------------- conservation

def test_grant_conservation_exact():
    s = _state()
    ev = _input_advance_phase(s, 10, s.active_ruleset_params())
    assert s.surplus_pool == 1_000_000 - ev[0]["amount"]
    assert s.coops["w1"]["treasury"] == 10 + ev[0]["amount"]
