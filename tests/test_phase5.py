"""Phase 5 tests: governance — PROPOSE, VOTE, ROLLBACK, two-phase
constitution, asymmetric recovery, and the constitutional guards."""

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
IDS = list(CITIZENS.keys())


def tx(tick, sender, action, payload, ruleset_version=1) -> Transaction:
    return Transaction(tick=tick, sender=sender, action=action, payload=payload, ruleset_version=ruleset_version)


def propose(tick, sender, params, activation_tick, ruleset_version=2):
    return tx(tick, sender, "PROPOSE", {"params": params, "activation_tick": activation_tick}, ruleset_version)


def vote(tick, sender, proposal_id, choice, ruleset_version=2):
    return tx(tick, sender, "VOTE", {"proposal_id": proposal_id, "choice": choice}, ruleset_version)


def rollback(tick, sender, target_version, ruleset_version=2):
    return tx(tick, sender, "ROLLBACK", {"target_version": target_version}, ruleset_version)


def rule_change(tick, sender, params, activation_tick, ruleset_version=1):
    return tx(tick, sender, "RULE_CHANGE", {"params": params, "activation_tick": activation_tick}, ruleset_version)


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


def gov_with(**overrides) -> dict:
    """Complete governance sub-params, enabled by default."""
    gov = {
        "enabled": True,
        "vote_window_ticks": 2,
        "quorum_bp": 5_000,  # 50% of 5 citizens -> 3
        "trial_period_ticks": 10,
    }
    gov.update(overrides)
    return gov


def enable_governance(tick=1, activation=2, **gov_over):
    """Bootstrap RULE_CHANGE that switches governance on."""
    return rule_change(tick, "alice", params_with(governance=gov_with(**gov_over)), activation)


def gov_state(**gov_over):
    """Genesis state + applied governance switch (v2 active from tick 2)."""
    state = genesis_state(dict(CITIZENS))
    ledger = Ledger()
    apply_tick(state, ledger, [enable_governance(**gov_over)])
    return state, ledger


def settled_events(state):
    return [e for e in state.applied if e.get("action") == "PROPOSAL_SETTLED"]


class TestLifecycle:
    def test_proposal_lifecycle(self):
        state, ledger = gov_state()  # v2 (governance on) from tick 2
        new_params = params_with(transfer_limit=100, governance=gov_with())

        apply_tick(state, ledger, [propose(2, "alice", new_params, 6)], current_tick=2)
        assert state.proposals["p1"]["status"] == "open"

        apply_tick(state, ledger, [
            vote(3, "alice", "p1", "for"),
            vote(3, "bob", "p1", "for"),
            vote(3, "carol", "p1", "for"),
        ], current_tick=3)

        apply_tick(state, ledger, [], current_tick=4)  # window closes; settlement
        assert state.proposals["p1"]["status"] == "passed"

        # passed proposal appends v3 activating at its declared tick
        assert len(state.rulesets) == 3
        v3 = state.rulesets[2]
        assert v3["version"] == 3
        assert v3["params"]["transfer_limit"] == 100
        assert v3["activated_at"] == 6
        assert state.ruleset_version == 2  # not yet active at tick 4

        apply_tick(state, ledger, [], current_tick=5)
        assert state.ruleset_version == 2  # still v2 (v3 starts at 6)
        apply_tick(state, ledger, [], current_tick=6)
        assert state.ruleset_version == 3
        assert state.active_ruleset_params()["transfer_limit"] == 100
        evt = settled_events(state)[0]
        assert evt["result"] == "passed" and evt["votes_for"] == 3

    def test_one_vote_per_citizen(self):
        state, ledger = gov_state()
        new_params = params_with(transfer_limit=100, governance=gov_with())
        apply_tick(state, ledger, [propose(2, "alice", new_params, 6)], current_tick=2)

        apply_tick(state, ledger, [
            vote(3, "alice", "p1", "for"),
            vote(3, "alice", "p1", "against"),  # rejected: ALREADY_VOTED
        ], current_tick=3)

        assert any(not r.accepted and r.reason == "ALREADY_VOTED" for r in ledger.records)
        assert state.proposals["p1"]["ballots"]["alice"] == "for"  # first ballot stands

    def test_quorum_enforced(self):
        state, ledger = gov_state(quorum_bp=6_000)  # 60% of 5 -> 3 citizens
        new_params = params_with(transfer_limit=100, governance=gov_with(quorum_bp=6_000))

        apply_tick(state, ledger, [propose(2, "alice", new_params, 6)], current_tick=2)
        apply_tick(state, ledger, [vote(3, "alice", "p1", "for"), vote(3, "bob", "p1", "for")], current_tick=3)
        apply_tick(state, ledger, [], current_tick=4)
        assert state.proposals["p1"]["status"] == "failed"  # 2 < quorum 3

        apply_tick(state, ledger, [propose(5, "alice", new_params, 9)], current_tick=5)
        apply_tick(state, ledger, [
            vote(6, "alice", "p2", "for"), vote(6, "bob", "p2", "for"), vote(6, "carol", "p2", "for"),
        ], current_tick=6)
        apply_tick(state, ledger, [], current_tick=7)
        assert state.proposals["p2"]["status"] == "passed"

    def test_majority_and_tie(self):
        state, ledger = gov_state()
        new_params = params_with(transfer_limit=100, governance=gov_with())

        # tie 2-2 -> fails (status-quo bias)
        apply_tick(state, ledger, [propose(2, "alice", new_params, 6)], current_tick=2)
        apply_tick(state, ledger, [
            vote(3, "alice", "p1", "for"), vote(3, "bob", "p1", "for"),
            vote(3, "carol", "p1", "against"), vote(3, "dave", "p1", "against"),
        ], current_tick=3)
        apply_tick(state, ledger, [], current_tick=4)
        assert state.proposals["p1"]["status"] == "failed"

        # clear majority 3-2 -> passes
        apply_tick(state, ledger, [propose(5, "alice", new_params, 9)], current_tick=5)
        apply_tick(state, ledger, [
            vote(6, "alice", "p2", "for"), vote(6, "bob", "p2", "for"), vote(6, "carol", "p2", "for"),
            vote(6, "dave", "p2", "against"), vote(6, "eve", "p2", "against"),
        ], current_tick=6)
        apply_tick(state, ledger, [], current_tick=7)
        assert state.proposals["p2"]["status"] == "passed"

    def test_hardened_two_thirds(self):
        state = genesis_state(dict(CITIZENS))
        ledger = Ledger()
        hardened = params_with(
            governance=gov_with(trial_period_ticks=5),
            constitution_phase="hardened",
        )
        apply_tick(state, ledger, [rule_change(1, "alice", hardened, activation_tick=2)])
        new_params = params_with(transfer_limit=100, governance=gov_with(trial_period_ticks=5), constitution_phase="hardened")

        # 3 for / 2 against < 2/3 -> fails
        apply_tick(state, ledger, [propose(2, "alice", new_params, 6)], current_tick=2)
        apply_tick(state, ledger, [
            vote(3, "alice", "p1", "for"), vote(3, "bob", "p1", "for"), vote(3, "carol", "p1", "for"),
            vote(3, "dave", "p1", "against"), vote(3, "eve", "p1", "against"),
        ], current_tick=3)
        apply_tick(state, ledger, [], current_tick=4)
        assert state.proposals["p1"]["status"] == "failed"

        # 4 for / 1 against >= 2/3 -> passes
        apply_tick(state, ledger, [propose(5, "alice", new_params, 9)], current_tick=5)
        apply_tick(state, ledger, [
            vote(6, "alice", "p2", "for"), vote(6, "bob", "p2", "for"), vote(6, "carol", "p2", "for"), vote(6, "dave", "p2", "for"),
            vote(6, "eve", "p2", "against"),
        ], current_tick=6)
        apply_tick(state, ledger, [], current_tick=7)
        assert state.proposals["p2"]["status"] == "passed"

    def test_rollback_in_trial_simple_majority(self):
        """Asymmetric recovery: rollback inside the trial period needs only
        a simple majority, restoring a prior governance-era version."""
        state, ledger = gov_state(trial_period_ticks=8)  # v2 active from tick 2

        # v3 comes from a PASSED proposal (RULE_CHANGE is locked now)
        v3_params = params_with(transfer_limit=999, governance=gov_with(trial_period_ticks=8))
        apply_tick(state, ledger, [propose(2, "alice", v3_params, 6)], current_tick=2)
        apply_tick(state, ledger, [
            vote(3, "alice", "p1", "for"), vote(3, "bob", "p1", "for"), vote(3, "carol", "p1", "for"),
        ], current_tick=3)
        apply_tick(state, ledger, [], current_tick=4)  # p1 settles; v3 activates at 6
        apply_tick(state, ledger, [], current_tick=6)
        assert state.ruleset_version == 3
        assert state.active_ruleset_params()["transfer_limit"] == 999

        # rollback to v2 (governance-era version -> allowed by the ratchet)
        apply_tick(state, ledger, [rollback(7, "alice", 2, ruleset_version=3)], current_tick=7)  # p2, closes 9
        assert state.proposals["p2"]["is_rollback"] is True

        apply_tick(state, ledger, [
            vote(8, "alice", "p2", "for", ruleset_version=3), vote(8, "bob", "p2", "for", ruleset_version=3), vote(8, "carol", "p2", "against", ruleset_version=3),
        ], current_tick=8)
        apply_tick(state, ledger, [], current_tick=9)  # settle: v3 activated 6, trial ends 14 -> in trial
        assert state.proposals["p2"]["status"] == "passed"  # simple majority sufficed

        v4 = state.rulesets[-1]
        assert v4["version"] == 4
        assert v4["params"]["transfer_limit"] == 0  # v2's value restored

    def test_rule_change_locked_once_governance_on(self):
        state, ledger = gov_state()
        apply_tick(state, ledger, [rule_change(2, "alice", params_with(transfer_limit=999), 3, ruleset_version=2)], current_tick=2)
        assert any(not r.accepted and r.reason == "GOVERNANCE_LOCKED" for r in ledger.records)
        assert len(state.rulesets) == 2  # nothing appended

    def test_determinism_vote_order(self):
        """Shuffled ballot order must produce the identical state hash."""
        rng = random.Random(42)
        new_params = params_with(transfer_limit=100, governance=gov_with())

        def build(shuffle_seed):
            r = random.Random(shuffle_seed)
            votes = [
                vote(3, "alice", "p1", "for"), vote(3, "bob", "p1", "for"),
                vote(3, "carol", "p1", "against"), vote(3, "dave", "p1", "for"),
                vote(3, "eve", "p1", "for"),
            ]
            r.shuffle(votes)
            return {
                1: [enable_governance()],
                2: [propose(2, "alice", new_params, 6, ruleset_version=2)],
                3: votes,
                4: [],
                5: [],
            }

        _, _, s1 = record_history(dict(CITIZENS), build(1))
        _, _, s2 = record_history(dict(CITIZENS), build(2))
        assert s1.state_hash() == s2.state_hash()
        assert s1.proposals["p1"]["status"] == "passed"


class TestRejectReasons:
    def test_vote_window_closed(self):
        state, ledger = gov_state()
        new_params = params_with(transfer_limit=100, governance=gov_with())
        apply_tick(state, ledger, [propose(2, "alice", new_params, 6)], current_tick=2)
        apply_tick(state, ledger, [], current_tick=4)  # settlement
        assert state.proposals["p1"]["status"] == "failed"
        apply_tick(state, ledger, [vote(5, "alice", "p1", "for")], current_tick=5)
        assert any(not r.accepted and r.reason == "VOTE_WINDOW_CLOSED" for r in ledger.records)

    def test_invalid_choice(self):
        state, ledger = gov_state()
        new_params = params_with(transfer_limit=100, governance=gov_with())
        apply_tick(state, ledger, [propose(2, "alice", new_params, 6)], current_tick=2)
        apply_tick(state, ledger, [vote(3, "alice", "p1", "maybe")], current_tick=3)
        assert any(not r.accepted and r.reason == "INVALID_CHOICE" for r in ledger.records)

    def test_proposal_not_found(self):
        state, ledger = gov_state()
        apply_tick(state, ledger, [vote(2, "alice", "p999", "for")], current_tick=2)
        assert any(not r.accepted and r.reason == "PROPOSAL_NOT_FOUND" for r in ledger.records)

    def test_governance_disabled_rejects(self):
        state = genesis_state(dict(CITIZENS))
        ledger = Ledger()
        apply_tick(state, ledger, [propose(1, "alice", params_with(), 3, ruleset_version=1)])
        assert any(not r.accepted and r.reason == "GOVERNANCE_DISABLED" for r in ledger.records)
        apply_tick(state, ledger, [vote(1, "alice", "p1", "for", ruleset_version=1)])
        assert any(not r.accepted and r.reason == "GOVERNANCE_DISABLED" for r in ledger.records)
        apply_tick(state, ledger, [rollback(1, "alice", 1, ruleset_version=1)])
        assert any(not r.accepted and r.reason == "GOVERNANCE_DISABLED" for r in ledger.records)

    def test_target_version_not_found(self):
        state, ledger = gov_state()
        apply_tick(state, ledger, [rollback(2, "alice", 999)], current_tick=2)
        assert any(not r.accepted and r.reason == "TARGET_VERSION_NOT_FOUND" for r in ledger.records)

    def test_proposal_cannot_disable_governance(self):
        """Constitutional guard: no vote may turn governance off."""
        state, ledger = gov_state()
        bad = params_with(governance={"enabled": False, "vote_window_ticks": 2, "quorum_bp": 5_000, "trial_period_ticks": 10})
        apply_tick(state, ledger, [propose(2, "alice", bad, 6)], current_tick=2)
        assert any(not r.accepted and r.reason == "CONSTITUTIONAL_GUARD" for r in ledger.records)

    def test_rollback_to_pre_governance_blocked(self):
        """Ratchet: restoring a version that predates governance-on is blocked."""
        state, ledger = gov_state()
        apply_tick(state, ledger, [rollback(2, "alice", 1)], current_tick=2)
        assert any(not r.accepted and r.reason == "CONSTITUTIONAL_GUARD" for r in ledger.records)

    def test_propose_activation_must_follow_window(self):
        state, ledger = gov_state()
        new_params = params_with(transfer_limit=100, governance=gov_with())
        # window closes at 4; activation at 4 is not strictly after
        apply_tick(state, ledger, [propose(2, "alice", new_params, 4)], current_tick=2)
        assert any(not r.accepted and r.reason == "ACTIVATION_IN_PAST" for r in ledger.records)

    def test_proposal_params_must_be_complete(self):
        state, ledger = gov_state()
        bad = params_with(transfer_limit=100, governance=gov_with())
        del bad["surplus_reserve_cap"]
        apply_tick(state, ledger, [propose(2, "alice", bad, 6)], current_tick=2)
        assert any(not r.accepted and r.reason == "INVALID_RULESET" for r in ledger.records)
