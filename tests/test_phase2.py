"""Phase 2 tests: version pinning (THE gate), entities, catalog integrity,
and mixed-action fuzz with dynamic rules.
"""

from __future__ import annotations

import random
from dataclasses import replace

import pytest

from openboard import (
    DEFAULT_RULESET_PARAMS,
    GOODS,
    RECIPES,
    Ledger,
    Reason,
    Transaction,
    apply_tick,
    genesis_state,
    record_history,
    replay,
    validate_catalog,
)

CITIZENS = {"alice": 1000, "bob": 800, "carol": 600, "dave": 400, "eve": 200}
IDS = list(CITIZENS.keys())


def tx(tick, sender, action, payload, ruleset_version=1) -> Transaction:
    return Transaction(tick=tick, sender=sender, action=action, payload=payload, ruleset_version=ruleset_version)


def transfer(tick, sender, to, amount, ruleset_version=1):
    return tx(tick, sender, "TRANSFER", {"to": to, "amount": amount}, ruleset_version)


def rule_change(tick, sender, params, activation_tick, ruleset_version=1):
    return tx(tick, sender, "RULE_CHANGE", {"params": params, "activation_tick": activation_tick}, ruleset_version)


def found_coop(tick, sender, coop_id, members, name=None, ruleset_version=1):
    return tx(tick, sender, "FOUND_COOP", {"coop_id": coop_id, "name": name or coop_id, "members": members}, ruleset_version)


def join_coop(tick, sender, coop_id, ruleset_version=1):
    return tx(tick, sender, "JOIN_COOP", {"coop_id": coop_id}, ruleset_version)


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


# ------------------------------------------------------------------ CATALOG


class TestCatalog:
    def test_catalog_healthy(self):
        problems = validate_catalog()
        assert problems == [], problems

    def test_39_goods(self):
        assert len(GOODS) == 39

    def test_all_goods_valid_triage(self):
        for gid, g in GOODS.items():
            assert g["triage"] in ("market", "essential", "emergency"), gid

    def test_essentials_flagged(self):
        for essential in ("grain", "bread", "housing", "water", "healthcare", "electricity", "heating_fuel"):
            assert GOODS[essential]["triage"] == "essential", essential

    def test_medicine_transport_market_default(self):
        assert GOODS["medicine"]["triage"] == "market"
        assert GOODS["transport"]["triage"] == "market"

    def test_recipes_reference_known_goods_only(self):
        for recipe in RECIPES.values():
            for good in list(recipe.inputs.keys()) + list(recipe.outputs.keys()):
                assert good in GOODS, f"{recipe.recipe_id} -> {good}"

    def test_recipes_integer_quantities(self):
        for recipe in RECIPES.values():
            for qty in list(recipe.inputs.values()) + list(recipe.outputs.values()):
                assert isinstance(qty, int) and not isinstance(qty, bool) and qty > 0, recipe.recipe_id
            assert recipe.labor_hours > 0 or recipe.inputs, recipe.recipe_id

    def test_no_floats_in_catalog(self):
        import json

        blob = json.dumps({k: r.to_dict() for k, r in RECIPES.items()})
        assert ".0" not in blob and "float" not in blob.lower()


# ------------------------------------------------------------ RULE_CHANGES


class TestRuleChange:
    def test_valid_rule_change_records_new_version(self):
        state = genesis_state(dict(CITIZENS))
        ledger = Ledger()
        new_params = params_with(transfer_limit=100)
        apply_tick(state, ledger, [rule_change(1, "alice", new_params, activation_tick=3)])
        assert len(state.rulesets) == 2
        assert state.rulesets[1]["version"] == 2
        assert state.rulesets[1]["activated_at"] == 3
        assert state.rulesets[1]["params"]["transfer_limit"] == 100
        assert state.rulesets[1]["change_tx_hash"] != "genesis"

    def test_activation_in_past_rejected(self):
        state = genesis_state(dict(CITIZENS))
        ledger = Ledger()
        apply_tick(state, ledger, [rule_change(1, "alice", params_with(transfer_limit=100), activation_tick=1)])
        assert ledger.rejected_count() == 1
        assert ledger.records[0].reason == "ACTIVATION_IN_PAST"

    def test_activation_same_tick_rejected(self):
        state = genesis_state(dict(CITIZENS))
        ledger = Ledger()
        apply_tick(state, ledger, [rule_change(1, "alice", params_with(transfer_limit=100), activation_tick=0)])
        assert ledger.records[0].reason in ("ACTIVATION_IN_PAST", "INVALID_PAYLOAD")

    def test_invalid_params_rejected(self):
        state = genesis_state(dict(CITIZENS))
        ledger = Ledger()
        # missing required key
        bad = {"transfer_limit": 5}
        apply_tick(state, ledger, [rule_change(1, "alice", bad, activation_tick=5)])
        assert ledger.records[0].reason == "INVALID_RULESET"

    def test_unknown_good_in_override_rejected(self):
        state = genesis_state(dict(CITIZENS))
        ledger = Ledger()
        bad = params_with(triage_overrides={"unobtanium": "essential"})
        apply_tick(state, ledger, [rule_change(1, "alice", bad, activation_tick=5)])
        assert ledger.records[0].reason == "INVALID_RULESET"

    def test_two_versions_same_activation_tick_deterministic(self):
        state = genesis_state(dict(CITIZENS))
        ledger = Ledger()
        a = rule_change(1, "alice", params_with(transfer_limit=100), activation_tick=5)
        b = rule_change(1, "bob", params_with(transfer_limit=200), activation_tick=5)
        # both accepted; deterministic winner = higher version (= later in sort order)
        apply_tick(state, ledger, [a, b])
        assert ledger.accepted_count() == 2
        versions = {rs["version"]: rs for rs in state.rulesets}
        assert versions[2]["params"]["transfer_limit"] == 100  # alice sorts first
        assert versions[3]["params"]["transfer_limit"] == 200  # bob second -> v3
        # v3 wins at tick 5 (higher version, same activation)
        assert state.ruleset_version == 1  # still v1 during tick 1


class TestVersionPinning:
    """THE Phase 2 gate: transactions execute under the tick's active version."""

    def test_transfer_limit_flips_across_activation(self):
        state = genesis_state(dict(CITIZENS))
        ledger = Ledger()

        # tick 1: propose limit=100 activating at tick 3 (v2)
        apply_tick(state, ledger, [rule_change(1, "alice", params_with(transfer_limit=100), activation_tick=3)])

        # tick 2: still v1 (unlimited) — a 500 transfer passes
        apply_tick(state, ledger, [transfer(2, "bob", "carol", 500)])
        assert ledger.accepted_count() == 2

        # tick 3: v2 active — 500 violates the limit, 100 passes (same batch)
        apply_tick(state, ledger, [
            transfer(3, "bob", "carol", 500, ruleset_version=2),
            transfer(3, "bob", "carol", 100, ruleset_version=2),
        ])
        assert ledger.accepted_count() == 3
        assert ledger.rejected_count() == 1
        assert ledger.records[-1].reason == "RULE_VIOLATION"

    def test_transfer_limit_flip_replays_identically(self):
        batches = {
            1: [rule_change(1, "alice", params_with(transfer_limit=100), activation_tick=3)],
            2: [transfer(2, "bob", "carol", 500)],
            3: [transfer(3, "bob", "carol", 500, ruleset_version=2)],
            4: [transfer(4, "bob", "carol", 100, ruleset_version=2)],
        }
        log, ledger, state = record_history(dict(CITIZENS), batches)
        result = replay(log)
        assert result.ok, f"mismatch at {result.mismatch_tick}"
        assert result.final_state_hash == state.state_hash()
        # the rejected 500-transfer at tick 3 is part of the public record
        assert ledger.rejected_count() == 1

    def test_pinning_mismatch_rejected(self):
        state = genesis_state(dict(CITIZENS))
        ledger = Ledger()
        # tx declaring v2 while v1 is active
        apply_tick(state, ledger, [transfer(1, "bob", "carol", 10, ruleset_version=2)])
        assert ledger.records[0].reason == "RULESET_MISMATCH"

    def test_stale_version_after_change_rejected(self):
        state = genesis_state(dict(CITIZENS))
        ledger = Ledger()
        apply_tick(state, ledger, [rule_change(1, "alice", params_with(transfer_limit=100), activation_tick=2)])
        # tick 2: v2 active; tx pinned to v1 (stale) -> rejected
        apply_tick(state, ledger, [transfer(2, "bob", "carol", 10, ruleset_version=1)])
        assert ledger.records[-1].reason == "RULESET_MISMATCH"

    def test_triage_override_via_rule_change(self):
        state = genesis_state(dict(CITIZENS))
        ledger = Ledger()
        # default: medicine is market
        assert state.effective_triage("medicine") == "market"

        new_params = params_with(triage_overrides={"medicine": "emergency"})
        apply_tick(state, ledger, [rule_change(1, "alice", new_params, activation_tick=2)])
        # tick 2: override active
        apply_tick(state, ledger, [transfer(2, "bob", "carol", 1, ruleset_version=2)])

        assert state.effective_triage("medicine") == "emergency"
        assert state.effective_triage("bread") == "essential"  # untouched

    def test_triage_override_replay_stable(self):
        batches = {
            1: [rule_change(1, "alice", params_with(triage_overrides={"medicine": "emergency"}), activation_tick=2)],
            2: [transfer(2, "bob", "carol", 5, ruleset_version=2)],
            3: [transfer(3, "carol", "bob", 3, ruleset_version=2)],
        }
        log, _, state = record_history(dict(CITIZENS), batches)
        result = replay(log)
        assert result.ok

        # re-derive effective triage from the replayed state
        replayed_state = genesis_state(dict(CITIZENS))
        rledger = Ledger()
        for tick in sorted(log.batches.keys()):
            apply_tick(replayed_state, rledger, log.batches[tick], current_tick=tick)
        assert replayed_state.effective_triage("medicine") == "emergency"
        assert replayed_state.state_hash() == state.state_hash()


# ------------------------------------------------------------------- CO-OPS


class TestCoops:
    def test_found_coop_happy_path(self):
        state = genesis_state(dict(CITIZENS))
        ledger = Ledger()
        apply_tick(state, ledger, [found_coop(1, "alice", "farmers", ["alice", "bob"])])
        assert "farmers" in state.coops
        assert state.coops["farmers"]["members"] == ["alice", "bob"]
        assert state.coops["farmers"]["founded_tick"] == 1
        # Phase 3: founding grants the votable bootstrap endowment
        assert state.coops["farmers"]["inventory"]["water"] > 0
        assert state.coops["farmers"]["labor_pool_hours"] == 0

    def test_sender_must_be_member(self):
        state = genesis_state(dict(CITIZENS))
        ledger = Ledger()
        apply_tick(state, ledger, [found_coop(1, "alice", "farmers", ["bob", "carol"])])
        assert ledger.records[0].reason == "NOT_A_MEMBER"

    def test_single_member_too_small(self):
        state = genesis_state(dict(CITIZENS))
        ledger = Ledger()
        apply_tick(state, ledger, [found_coop(1, "alice", "solo", ["alice"])])
        assert ledger.records[0].reason == "COOP_TOO_SMALL"

    def test_coop_exists(self):
        state = genesis_state(dict(CITIZENS))
        ledger = Ledger()
        apply_tick(state, ledger, [found_coop(1, "alice", "farmers", ["alice", "bob"])])
        apply_tick(state, ledger, [found_coop(2, "carol", "farmers", ["carol", "dave"])], current_tick=2)
        assert ledger.records[-1].reason == "COOP_EXISTS"

    def test_member_already_in_coop(self):
        state = genesis_state(dict(CITIZENS))
        ledger = Ledger()
        apply_tick(state, ledger, [found_coop(1, "alice", "farmers", ["alice", "bob"])])
        apply_tick(state, ledger, [found_coop(2, "carol", "miners", ["carol", "bob"])], current_tick=2)
        assert ledger.records[-1].reason == "ALREADY_IN_COOP"

    def test_join_coop_happy_path(self):
        state = genesis_state(dict(CITIZENS))
        ledger = Ledger()
        apply_tick(state, ledger, [found_coop(1, "alice", "farmers", ["alice", "bob"])])
        apply_tick(state, ledger, [join_coop(2, "carol", "farmers")], current_tick=2)
        assert "carol" in state.coops["farmers"]["members"]

    def test_join_nonexistent_coop(self):
        state = genesis_state(dict(CITIZENS))
        ledger = Ledger()
        apply_tick(state, ledger, [join_coop(1, "carol", "ghost_coop")])
        assert ledger.records[0].reason == "COOP_NOT_FOUND"

    def test_join_when_already_member(self):
        state = genesis_state(dict(CITIZENS))
        ledger = Ledger()
        apply_tick(state, ledger, [found_coop(1, "alice", "farmers", ["alice", "bob"])])
        apply_tick(state, ledger, [join_coop(2, "alice", "farmers")], current_tick=2)
        assert ledger.records[-1].reason == "ALREADY_IN_COOP"

    def test_coop_full_from_rule_params(self):
        # max members = 2 via rules
        state = genesis_state(dict(CITIZENS), ruleset_params=params_with(max_coop_members=2))
        ledger = Ledger()
        apply_tick(state, ledger, [found_coop(1, "alice", "farmers", ["alice", "bob"])])
        apply_tick(state, ledger, [join_coop(2, "carol", "farmers")], current_tick=2)
        assert ledger.records[-1].reason == "COOP_FULL"

    def test_coop_size_limit_changeable_by_rules(self):
        """Rules demonstrably drive entity behavior (D7 in action)."""
        state = genesis_state(dict(CITIZENS))
        ledger = Ledger()
        # v1: max 3
        genesis = params_with(max_coop_members=3)
        state2 = genesis_state(dict(CITIZENS), ruleset_params=genesis)
        # found with 2, join makes 3 — fine under v1
        apply_tick(state2, ledger, [found_coop(1, "alice", "farmers", ["alice", "bob"])])
        apply_tick(state2, ledger, [join_coop(2, "carol", "farmers")], current_tick=2)
        # now lower to max 2 (v2, activates tick 4)
        apply_tick(
            state2,
            ledger,
            [rule_change(3, "alice", params_with(max_coop_members=2), activation_tick=4)],
            current_tick=3,
        )
        # dave tries to join at tick 4 under v2 -> full
        apply_tick(state2, ledger, [join_coop(4, "dave", "farmers", ruleset_version=2)], current_tick=4)
        assert ledger.records[-1].reason == "COOP_FULL"

    def test_founding_with_too_many_members(self):
        # genesis rules cap co-ops at 3 members
        state = genesis_state(dict(CITIZENS), ruleset_params=params_with(max_coop_members=3))
        ledger = Ledger()
        apply_tick(state, ledger, [found_coop(1, "alice", "everyone", IDS)])
        assert ledger.records[0].reason == "COOP_FULL"

    def test_unknown_member_rejected(self):
        state = genesis_state(dict(CITIZENS))
        ledger = Ledger()
        apply_tick(state, ledger, [found_coop(1, "alice", "ghosts", ["alice", "ghost"])])
        assert ledger.records[0].reason == "UNKNOWN_CITIZEN"


# --------------------------------------------------------------------- FUZZ


def mixed_fuzz(seed=2027, ticks=60, per_tick=40) -> dict[int, list[Transaction]]:
    """Mixed-action fuzz with dynamic rule changes."""
    rng = random.Random(seed)
    batches: dict[int, list[Transaction]] = {}

    # track sim-side state to make mostly-valid actions
    active_version = 1
    coop_members: set[str] = set()
    coop_exists = False
    next_activation = 2

    for t in range(1, ticks + 1):
        if t == next_activation:
            active_version += 1
        batch: list[Transaction] = []
        for _ in range(per_tick):
            roll = rng.random()
            sender = rng.choice(IDS)
            if roll < 0.70:
                to = rng.choice([c for c in IDS if c != sender])
                amount = rng.randint(1, 50)
                batch.append(transfer(t, sender, to, amount, ruleset_version=active_version))
            elif roll < 0.80:
                free = [c for c in IDS if c not in coop_members]
                if not free:
                    to = rng.choice([c for c in IDS if c != sender])
                    batch.append(transfer(t, sender, to, rng.randint(1, 30), ruleset_version=active_version))
                    continue
                target = rng.choice(free)
                batch.append(tx(t, target, "JOIN_COOP", {"coop_id": "the_coop"}, ruleset_version=active_version))
            elif roll < 0.90:
                if coop_exists:
                    free = [c for c in IDS if c not in coop_members]
                    to = rng.choice([c for c in IDS if c != sender])
                    batch.append(transfer(t, sender, to, rng.randint(1, 30), ruleset_version=active_version))
                    continue
                # found a coop with a random valid member set
                free = [c for c in IDS if c not in coop_members]
                if len(free) >= 2:
                    members = rng.sample(free, rng.randint(2, min(4, len(free))))
                    if sender not in members:
                        members[0] = sender
                    batch.append(found_coop(t, members[0], "the_coop", members, ruleset_version=active_version))
                    coop_exists = True  # optimistic; rejection is fine too
            else:
                # occasional rule change (limit toggles 0/25)
                limit = rng.choice([0, 25, 60])
                batch.append(
                    rule_change(
                        t,
                        sender,
                        params_with(transfer_limit=limit),
                        activation_tick=t + 2,
                        ruleset_version=active_version,
                    )
                )
                next_activation = max(next_activation, t + 2)
        batches[t] = batch
    return batches


class TestMixedFuzz:
    def test_mixed_fuzz_deterministic_replay(self):
        batches = mixed_fuzz(seed=11)
        log, ledger, state = record_history(dict(CITIZENS), batches)
        assert ledger.verify_chain()
        result = replay(log)
        assert result.ok, f"mismatch at tick {result.mismatch_tick}"
        assert result.final_state_hash == state.state_hash()

    def test_mixed_fuzz_shuffled_equivalence(self):
        rng = random.Random(202)
        batches = mixed_fuzz(seed=12, ticks=15, per_tick=12)
        shuffled = {t: rng.sample(b, len(b)) for t, b in batches.items()}
        _, _, s1 = record_history(dict(CITIZENS), batches)
        _, _, s2 = record_history(dict(CITIZENS), shuffled)
        assert s1.state_hash() == s2.state_hash()

    def test_mixed_fuzz_credits_conserved(self):
        batches = mixed_fuzz(seed=13)
        _, _, state = record_history(dict(CITIZENS), batches)
        assert sum(state.balances.values()) == sum(CITIZENS.values())

    def test_mixed_fuzz_multiple_seeds(self):
        for seed in (21, 22, 23):
            batches = mixed_fuzz(seed=seed, ticks=30, per_tick=20)
            log, ledger, state = record_history(dict(CITIZENS), batches)
            assert ledger.verify_chain(), f"seed {seed}: chain broken"
            result = replay(log)
            assert result.ok, f"seed {seed}: mismatch at {result.mismatch_tick}"

    def test_mixed_fuzz_rule_versions_grow(self):
        batches = mixed_fuzz(seed=24, ticks=20, per_tick=10)
        _, _, state = record_history(dict(CITIZENS), batches)
        # rule changes actually happened in this history
        assert len(state.rulesets) >= 2

    def test_tampered_rule_change_detected(self):
        batches = mixed_fuzz(seed=25, ticks=40, per_tick=25)
        log, ledger, _ = record_history(dict(CITIZENS), batches)
        # locate a rule change that was ACCEPTED (only accepted txs shape state)
        accepted_rc_hashes = {
            rec.tx_hash for rec in ledger.records if rec.accepted and rec.tx["action"] == "RULE_CHANGE"
        }
        assert accepted_rc_hashes, "fuzz history contains no accepted rule change"

        for tick, batch in log.batches.items():
            for i, t in enumerate(batch):
                if t.action == "RULE_CHANGE" and t.content_hash() in accepted_rc_hashes:
                    bad_params = params_with(transfer_limit=99999)
                    forged = replace(t, payload={"params": bad_params, "activation_tick": t.payload["activation_tick"]})
                    log.batches[tick] = [forged if j == i else orig for j, orig in enumerate(batch)]
                    result = replay(log)
                    assert result.ok is False
                    return
        pytest.fail("accepted RULE_CHANGE not found in log batches")
