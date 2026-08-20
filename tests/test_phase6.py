"""Phase 6 tests: oversight — anomaly detection (D9), council gating,
the three interventions, common-pool draw, conservation, determinism."""

from __future__ import annotations

import random

from openboard import (
    Ledger,
    Transaction,
    apply_tick,
    genesis_state,
    record_history,
)

CITIZENS = {"alice": 1000, "bob": 800, "carol": 600, "dave": 400, "eve": 200}


def tx(tick, sender, action, payload, ruleset_version=1) -> Transaction:
    return Transaction(tick=tick, sender=sender, action=action, payload=payload, ruleset_version=ruleset_version)


def vote(tick, sender, proposal_id, choice, ruleset_version=2):
    return tx(tick, sender, "VOTE", {"proposal_id": proposal_id, "choice": choice}, ruleset_version)


def intervene(tick, sender, intervention, ruleset_version=2):
    return tx(tick, sender, "INTERVENE", {"intervention": intervention}, ruleset_version)


def rule_change(tick, sender, params, activation_tick, ruleset_version=1):
    return tx(tick, sender, "RULE_CHANGE", {"params": params, "activation_tick": activation_tick}, ruleset_version)


def found_coop(tick, sender, coop_id, members, ruleset_version=2):
    return tx(tick, sender, "FOUND_COOP", {"coop_id": coop_id, "name": coop_id, "members": members}, ruleset_version)


def list_good(tick, sender, coop_id, good, qty, ruleset_version=2):
    return tx(tick, sender, "LIST_GOOD", {"coop_id": coop_id, "good": good, "qty": qty}, ruleset_version)


def buy_essential(tick, sender, good, qty, ruleset_version=2):
    return tx(tick, sender, "BUY_ESSENTIAL", {"good": good, "qty": qty}, ruleset_version)


def params_with(**overrides) -> dict:
    params = {
        "transfer_limit": 0,
        "max_coop_members": 12,
        "min_coop_members": 2,
        "triage_overrides": {},
        "wage_multiplier_bp": 10_000,
        "energy_price": 2,
        "max_work_hours_per_tick": 8,
        "bootstrap_endowment": {
            "water": 200,
            "electricity": 500,
            "hand_tools": 5,
            "machines": 1,
        },
        "essential_need_quota": {
            "grain": 10,
            "bread": 4,
            "water": 10,
        },
        "surplus_reserve_cap": 5_000,
        "governance": {
            "enabled": False,
            "vote_window_ticks": 3,
            "quorum_bp": 5_000,
            "trial_period_ticks": 10,
        },
        "constitution_phase": "bootstrap",
        "oversight": {
            "hoard_multiplier": 3,
            "market_power_share_bp": 7_000,
            "free_rider_min_hours": 5,
            "council_members": [],
        },
    }
    params.update(overrides)
    return params


COUNCIL = ["carol", "dave"]


def gov_params(council=None, **ov_over):
    """Params with governance on + council elected."""
    ov = {
        "hoard_multiplier": 3,
        "market_power_share_bp": 7_000,
        "free_rider_min_hours": 5,
        "council_members": council if council is not None else COUNCIL,
    }
    ov.update(ov_over)
    return params_with(
        governance={"enabled": True, "vote_window_ticks": 2, "quorum_bp": 5_000, "trial_period_ticks": 10},
        oversight=ov,
    )


def setup_state(**ov_over):
    """Genesis + governance/council switch applied (v2 active from tick 2)."""
    state = genesis_state(dict(CITIZENS))
    ledger = Ledger()
    apply_tick(state, ledger, [rule_change(1, "alice", gov_params(**ov_over), 2)])
    return state, ledger


def flags_of(state, kind):
    return [f for f in state.flags if f["kind"] == kind]


def flag_events(state, kind):
    return [e for e in state.applied if e.get("action") == "OVERSIGHT_FLAG" and e.get("kind") == kind]


def pass_proposal(state, ledger, pid, tick, for_voters, ruleset_version=2):
    """Cast the for-votes at `tick`; settle at tick+1 (window 2)."""
    apply_tick(state, ledger, [vote(tick, v, pid, "for", ruleset_version) for v in for_voters], current_tick=tick)
    apply_tick(state, ledger, [], current_tick=tick + 1)


class TestDetection:
    def test_hoard_flagged(self):
        state, ledger = setup_state()
        # carol holds 40 grain; quota 10 x multiplier 3 = 30 -> hoard
        state.citizen_inventory["carol"] = {"grain": 40}
        apply_tick(state, ledger, [], current_tick=2)
        flags = flags_of(state, "HOARD")
        assert any(f["target"] == "carol" and f["good"] == "grain" for f in flags)
        assert flag_events(state, "HOARD")  # public event emitted

    def test_market_power_flagged(self):
        state, ledger = setup_state()
        apply_tick(state, ledger, [
            found_coop(2, "alice", "bigfish", ["alice", "bob"]),
            found_coop(2, "carol", "smallfish", ["carol", "dave"]),
        ], current_tick=2)
        # bigfish lists 80 of 100 total fish -> 80% > 70%
        state.coops["bigfish"]["inventory"]["fish"] = 80
        state.coops["smallfish"]["inventory"]["fish"] = 20
        apply_tick(state, ledger, [
            list_good(3, "alice", "bigfish", "fish", 80),
            list_good(3, "carol", "smallfish", "fish", 20),
        ], current_tick=3)
        flags = flags_of(state, "MARKET_POWER")
        assert any(f["target"] == "bigfish" and f["good"] == "fish" for f in flags)

    def test_free_rider_flagged(self):
        state, ledger = setup_state()
        # eve has consumption but almost no lifetime labor
        state.citizen_inventory["eve"] = {"bread": 2}
        state.labor_hours["eve"] = 1
        apply_tick(state, ledger, [], current_tick=2)
        assert any(f["target"] == "eve" for f in flags_of(state, "FREE_RIDER"))

    def test_no_duplicate_flags(self):
        state, ledger = setup_state()
        state.citizen_inventory["carol"] = {"grain": 40}
        apply_tick(state, ledger, [], current_tick=2)
        apply_tick(state, ledger, [], current_tick=3)
        assert len(flags_of(state, "HOARD")) == 1  # append-once per (kind,target,good)


class TestCouncilGating:
    def test_non_council_rejected(self):
        state, ledger = setup_state()
        apply_tick(state, ledger, [intervene(2, "alice", {"type": "FINE", "target": "bob", "amount": 10})], current_tick=2)
        assert any(not r.accepted and r.reason == "NOT_COUNCIL_MEMBER" for r in ledger.records)

    def test_unknown_intervention_type(self):
        state, ledger = setup_state()
        apply_tick(state, ledger, [intervene(2, "carol", {"type": "MAGIC"})], current_tick=2)
        assert any(not r.accepted and r.reason == "INTERVENTION_TYPE_UNKNOWN" for r in ledger.records)

    def test_bad_schema_rejected(self):
        state, ledger = setup_state()
        apply_tick(state, ledger, [intervene(2, "carol", {"type": "FINE", "target": "bob"})], current_tick=2)
        assert any(not r.accepted and r.reason == "INVALID_INTERVENTION" for r in ledger.records)


class TestInterventions:
    def test_dissolve_hoard(self):
        state, ledger = setup_state()
        state.citizen_inventory["carol"] = {"grain": 40}  # allowed 30
        apply_tick(state, ledger, [intervene(2, "carol", {"type": "DISSOLVE_HOARD", "target": "carol", "good": "grain"})], current_tick=2)
        pass_proposal(state, ledger, "p1", 3, ["alice", "bob", "carol"])

        assert state.proposals["p1"]["status"] == "passed"
        assert state.citizen_inventory["carol"]["grain"] == 30  # threshold kept
        assert state.common_pool["grain"] == 10  # excess reclaimed
        executed = [e for e in state.applied if e.get("action") == "INTERVENTION_EXECUTED"]
        assert executed and executed[0]["executed"]["excess_moved"] == 10

    def test_dissolve_hoard_no_excess_noop(self):
        state, ledger = setup_state()
        state.citizen_inventory["carol"] = {"grain": 5}  # below threshold
        apply_tick(state, ledger, [intervene(2, "carol", {"type": "DISSOLVE_HOARD", "target": "carol", "good": "grain"})], current_tick=2)
        pass_proposal(state, ledger, "p1", 3, ["alice", "bob", "carol"])
        assert state.citizen_inventory["carol"]["grain"] == 5
        assert state.common_pool.get("grain", 0) == 0

    def test_fine_moves_credits_to_pool(self):
        state, ledger = setup_state()
        before_total = sum(state.balances.values()) + state.surplus_pool
        bob_before = state.balances["bob"]

        apply_tick(state, ledger, [intervene(2, "carol", {"type": "FINE", "target": "bob", "amount": 100})], current_tick=2)
        pass_proposal(state, ledger, "p1", 3, ["alice", "bob", "carol"])

        assert state.balances["bob"] == bob_before - 100
        assert state.surplus_pool == 100
        # conservation: fine moved, not destroyed
        assert sum(state.balances.values()) + state.surplus_pool == before_total

    def test_fine_capped_at_balance(self):
        state, ledger = setup_state()
        eve_before = state.balances["eve"]
        apply_tick(state, ledger, [intervene(2, "carol", {"type": "FINE", "target": "eve", "amount": 10_000})], current_tick=2)
        pass_proposal(state, ledger, "p1", 3, ["alice", "bob", "carol"])
        assert state.balances["eve"] == 0  # never negative
        assert state.surplus_pool == eve_before

    def test_emergency_triage_appends_version(self):
        state, ledger = setup_state()
        apply_tick(state, ledger, [intervene(2, "carol", {"type": "EMERGENCY_TRIAGE", "good": "medicine"})], current_tick=2)
        pass_proposal(state, ledger, "p1", 3, ["alice", "bob", "carol"])

        v3 = state.rulesets[-1]
        assert v3["params"]["triage_overrides"]["medicine"] == "emergency"
        assert v3["activated_at"] == 5  # settled at 4; strictly-future activation

    def test_failed_intervention_executes_nothing(self):
        state, ledger = setup_state()
        state.citizen_inventory["carol"] = {"grain": 40}
        apply_tick(state, ledger, [intervene(2, "carol", {"type": "DISSOLVE_HOARD", "target": "carol", "good": "grain"})], current_tick=2)
        # only one vote -> quorum fails
        apply_tick(state, ledger, [vote(3, "alice", "p1", "for")], current_tick=3)
        apply_tick(state, ledger, [], current_tick=4)
        assert state.proposals["p1"]["status"] == "failed"
        assert state.citizen_inventory["carol"]["grain"] == 40  # untouched
        assert not [e for e in state.applied if e.get("action") == "INTERVENTION_EXECUTED"]


class TestCommonPool:
    def test_essential_buy_draws_from_pool(self):
        state, ledger = setup_state()
        state.common_pool["grain"] = 10
        eve_before = state.balances["eve"]
        floor = state.good_cost_baseline["grain"]

        apply_tick(state, ledger, [buy_essential(2, "eve", "grain", 4)], current_tick=2)
        assert state.citizen_inventory["eve"]["grain"] == 4
        assert state.common_pool["grain"] == 6
        assert state.balances["eve"] == eve_before - 4 * floor
        assert state.surplus_pool == 4 * floor  # paid to society at cost


class TestDeterminism:
    def test_shuffle_equivalence_with_oversight(self):
        def build(seed):
            r = random.Random(seed)
            votes = [
                vote(3, "alice", "p1", "for"),
                vote(3, "bob", "p1", "for"),
                vote(3, "carol", "p1", "for"),
            ]
            r.shuffle(votes)
            return {
                1: [rule_change(1, "alice", gov_params(), 2)],
                2: [intervene(2, "carol", {"type": "FINE", "target": "bob", "amount": 50})],
                3: votes,
                4: [],
            }

        _, _, s1 = record_history(dict(CITIZENS), build(1))
        _, _, s2 = record_history(dict(CITIZENS), build(2))
        assert s1.state_hash() == s2.state_hash()
        assert s1.surplus_pool == 50
