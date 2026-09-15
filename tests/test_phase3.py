"""Phase 3 tests: production — WORK mints wages, PRODUCE consumes
inputs and stamps cost baselines, money invariant holds."""

from __future__ import annotations

import random
from dataclasses import replace

import pytest

from openboard import (
    Ledger,
    Transaction,
    apply_tick,
    genesis_state,
    record_history,
    replay,
)

CITIZENS = {"alice": 1000, "bob": 800, "carol": 600, "dave": 400, "eve": 200}
IDS = list(CITIZENS.keys())
INITIAL_TOTAL = sum(CITIZENS.values())


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


def tx(tick, sender, action, payload, ruleset_version=1) -> Transaction:
    return Transaction(tick=tick, sender=sender, action=action, payload=payload, ruleset_version=ruleset_version)


def transfer(tick, sender, to, amount, ruleset_version=1):
    return tx(tick, sender, "TRANSFER", {"to": to, "amount": amount}, ruleset_version)


def found_coop(tick, sender, coop_id, members, ruleset_version=1):
    return tx(tick, sender, "FOUND_COOP", {"coop_id": coop_id, "name": coop_id, "members": members}, ruleset_version)


def work(tick, sender, coop_id, hours, ruleset_version=1):
    return tx(tick, sender, "WORK", {"coop_id": coop_id, "hours": hours}, ruleset_version)


def produce(tick, sender, coop_id, recipe_id, runs, ruleset_version=1):
    return tx(tick, sender, "PRODUCE", {"coop_id": coop_id, "recipe_id": recipe_id, "runs": runs}, ruleset_version)


def fresh_fishers() -> tuple:
    """Genesis + fishers co-op (alice, bob) with default endowment."""
    state = genesis_state(dict(CITIZENS))
    ledger = Ledger()
    apply_tick(state, ledger, [found_coop(1, "alice", "fishers", ["alice", "bob"])])
    assert ledger.accepted_count() == 1
    return state, ledger


# ------------------------------------------------------------------ ENDOWMENT


class TestEndowment:
    def test_founding_grants_endowment(self):
        state, ledger = fresh_fishers()
        inv = state.coops["fishers"]["inventory"]
        assert inv["water"] == 200
        assert inv["electricity"] == 500
        assert inv["hand_tools"] == 5
        assert inv["machines"] == 1
        assert state.coops["fishers"]["labor_pool_hours"] == 0

    def test_endowment_is_votable(self):
        # D7 demo: change the endowment via rules, new co-ops get the new grant
        state = genesis_state(dict(CITIZENS))
        ledger = Ledger()
        new_params = params_with(bootstrap_endowment={"water": 999})
        apply_tick(state, ledger, [tx(1, "alice", "RULE_CHANGE", {"params": new_params, "activation_tick": 2})])
        apply_tick(state, ledger, [found_coop(2, "carol", "co", ["carol", "dave"], ruleset_version=2)])
        assert state.coops["co"]["inventory"] == {"water": 999}


# ---------------------------------------------------------------------- WORK


class TestWork:
    def test_work_mints_wage_and_fills_pool(self):
        state, ledger = fresh_fishers()
        apply_tick(state, ledger, [work(2, "alice", "fishers", 5)], current_tick=2)
        assert ledger.accepted_count() == 2
        assert state.balances["alice"] == 1005  # 5 hours x 1.0x
        assert state.coops["fishers"]["labor_pool_hours"] == 5
        assert state.labor_hours["alice"] == 5
        assert state.money_minted == 5

    def test_wage_remainder_accumulates(self):
        # 0.5x multiplier: 1 hour -> 0 credits now, 1 credit after 2nd hour
        state = genesis_state(dict(CITIZENS), ruleset_params=params_with(wage_multiplier_bp=5_000))
        ledger = Ledger()
        apply_tick(state, ledger, [found_coop(1, "alice", "half", ["alice", "bob"])])
        apply_tick(state, ledger, [work(2, "alice", "half", 1)], current_tick=2)
        assert state.balances["alice"] == 1000
        assert state.coops["half"]["wage_remainder_bp"] == 5_000
        apply_tick(state, ledger, [work(3, "alice", "half", 1)], current_tick=3)
        assert state.balances["alice"] == 1001
        assert state.coops["half"]["wage_remainder_bp"] == 0

    def test_work_unknown_coop(self):
        state, ledger = fresh_fishers()
        apply_tick(state, ledger, [work(2, "carol", "ghost", 1)], current_tick=2)
        assert ledger.records[-1].reason == "COOP_NOT_FOUND"

    def test_work_not_a_member(self):
        state, ledger = fresh_fishers()
        apply_tick(state, ledger, [work(2, "carol", "fishers", 1)], current_tick=2)
        assert ledger.records[-1].reason == "NOT_A_MEMBER"

    def test_work_zero_hours(self):
        state, ledger = fresh_fishers()
        apply_tick(state, ledger, [work(2, "alice", "fishers", 0)], current_tick=2)
        assert ledger.records[-1].reason == "INVALID_HOURS"

    def test_work_over_limit(self):
        state, ledger = fresh_fishers()
        apply_tick(state, ledger, [work(2, "alice", "fishers", 9)], current_tick=2)
        assert ledger.records[-1].reason == "INVALID_HOURS"

    def test_work_float_hours(self):
        state, ledger = fresh_fishers()
        apply_tick(state, ledger, [work(2, "alice", "fishers", 1.5)], current_tick=2)
        assert ledger.records[-1].reason == "INVALID_HOURS"


# ------------------------------------------------------------------- PRODUCE


class TestProduce:
    def test_produce_fishing(self):
        state, ledger = fresh_fishers()
        # 4 ticks of work to fill 30 labor hours (max 8/tick)
        for t in range(2, 6):
            apply_tick(state, ledger, [work(t, "alice", "fishers", 8)], current_tick=t)
        assert state.coops["fishers"]["labor_pool_hours"] == 32

        apply_tick(state, ledger, [produce(6, "bob", "fishers", "fishing", 1)], current_tick=6)
        assert ledger.accepted_count() == 6
        inv = state.coops["fishers"]["inventory"]
        # fishing batch rescaled 50 -> 200 (true-need balance, 2026-09-15):
        # daily-draw kcal demand needs city-scale batches
        assert inv["fish"] == 200
        assert inv["electricity"] == 500 - 8
        assert state.coops["fishers"]["labor_pool_hours"] == 2

    def test_produce_baseline_math_hand_tools(self):
        # hand_tools_craft: 20 labor + 5 energy + (2 steel@80 + 1 lumber@25)
        # = 20 + 10 + 185 = 215 for 5 tools -> 43 per tool
        state = genesis_state(dict(CITIZENS))
        ledger = Ledger()
        apply_tick(state, ledger, [found_coop(1, "alice", "smiths", ["alice", "bob"])])
        # give smiths the inputs they need
        state.coops["smiths"]["inventory"]["steel"] = 2
        state.coops["smiths"]["inventory"]["lumber"] = 1
        for t in range(2, 6):
            apply_tick(state, ledger, [work(t, "alice", "smiths", 8)], current_tick=t)
        apply_tick(state, ledger, [produce(6, "alice", "smiths", "hand_tools_craft", 1)], current_tick=6)
        assert state.coops["smiths"]["inventory"]["hand_tools"] == 5 + 5  # endowment + produced
        assert state.good_cost_baseline["hand_tools"] == 43

    def test_produce_not_enough_labor(self):
        state, ledger = fresh_fishers()
        apply_tick(state, ledger, [work(2, "alice", "fishers", 8)], current_tick=2)
        apply_tick(state, ledger, [produce(3, "bob", "fishers", "fishing", 1)], current_tick=3)
        assert ledger.records[-1].reason == "NOT_ENOUGH_LABOR"

    def test_produce_not_enough_energy(self):
        state, ledger = fresh_fishers()
        for t in range(2, 6):
            apply_tick(state, ledger, [work(t, "alice", "fishers", 8)], current_tick=t)
        # burn the electricity
        state.coops["fishers"]["inventory"]["electricity"] = 0
        apply_tick(state, ledger, [produce(6, "bob", "fishers", "fishing", 1)], current_tick=6)
        assert ledger.records[-1].reason == "NOT_ENOUGH_ENERGY"

    def test_produce_not_enough_inputs(self):
        state = genesis_state(dict(CITIZENS))
        ledger = Ledger()
        apply_tick(state, ledger, [found_coop(1, "alice", "farmers", ["alice", "bob"])])
        for t in range(2, 8):
            apply_tick(state, ledger, [work(t, "alice", "farmers", 8)], current_tick=t)
        # grain_farming needs 5 water; endowment has 200 — remove it
        state.coops["farmers"]["inventory"]["water"] = 0
        apply_tick(state, ledger, [produce(8, "alice", "farmers", "grain_farming", 1)], current_tick=8)
        assert ledger.records[-1].reason == "NOT_ENOUGH_INPUTS"

    def test_produce_recipe_not_found(self):
        state, ledger = fresh_fishers()
        apply_tick(state, ledger, [produce(2, "alice", "fishers", "magic", 1)], current_tick=2)
        assert ledger.records[-1].reason == "RECIPE_NOT_FOUND"

    def test_produce_invalid_runs(self):
        state, ledger = fresh_fishers()
        apply_tick(state, ledger, [produce(2, "alice", "fishers", "fishing", 0)], current_tick=2)
        assert ledger.records[-1].reason == "INVALID_RUNS"

    def test_produce_not_a_member(self):
        state, ledger = fresh_fishers()
        apply_tick(state, ledger, [produce(2, "carol", "fishers", "fishing", 1)], current_tick=2)
        assert ledger.records[-1].reason == "NOT_A_MEMBER"

    def test_produce_consumes_inputs(self):
        state, ledger = fresh_fishers()
        for t in range(2, 6):
            apply_tick(state, ledger, [work(t, "alice", "fishers", 8)], current_tick=t)
        apply_tick(state, ledger, [produce(6, "bob", "fishers", "fishing", 1)], current_tick=6)
        # second run fails: only 2 labor hours left
        apply_tick(state, ledger, [produce(7, "bob", "fishers", "fishing", 1)], current_tick=7)
        assert ledger.records[-1].reason == "NOT_ENOUGH_LABOR"


# ----------------------------------------------------------- MONEY INVARIANT


class TestMoneyInvariant:
    def test_money_invariant_after_work(self):
        state, ledger = fresh_fishers()
        for t in range(2, 10):
            apply_tick(state, ledger, [work(t, "alice", "fishers", 8), work(t, "bob", "fishers", 6)], current_tick=t)
        total = sum(state.balances.values())
        assert total == INITIAL_TOTAL + state.money_minted - state.money_retired
        assert state.money_minted == 8 * 8 + 8 * 6  # ticks 2..9 inclusive

    def test_money_invariant_after_transfers_and_work(self):
        state, ledger = fresh_fishers()
        apply_tick(state, ledger, [
            work(2, "alice", "fishers", 8),
            transfer(2, "bob", "carol", 100),
            work(2, "bob", "fishers", 4),
        ], current_tick=2)
        total = sum(state.balances.values())
        assert total == INITIAL_TOTAL + state.money_minted


# --------------------------------------------------------------------- FUZZ


def production_fuzz(seed=77, ticks=40, per_tick=12) -> dict[int, list[Transaction]]:
    """Mixed fuzz: found, join, work, produce fishing, transfers."""
    rng = random.Random(seed)
    batches: dict[int, list[Transaction]] = {}
    founded = False
    members: set[str] = set()

    for t in range(1, ticks + 1):
        batch: list[Transaction] = []
        for _ in range(per_tick):
            roll = rng.random()
            sender = rng.choice(IDS)
            if not founded and roll < 0.5:
                batch.append(found_coop(t, "alice", "fishers", ["alice", "bob"]))
                founded = True
                members.update(["alice", "bob"])
            elif founded and sender not in members and roll < 0.2:
                batch.append(tx(t, sender, "JOIN_COOP", {"coop_id": "fishers"}))
                # optimistic; rejection fine
                if sender not in ("alice", "bob"):
                    members.add(sender)
            elif sender in members and roll < 0.6:
                batch.append(work(t, sender, "fishers", rng.randint(1, 8)))
            elif sender in members and roll < 0.8:
                batch.append(produce(t, sender, "fishers", "fishing", rng.randint(1, 2)))
            else:
                to = rng.choice([c for c in IDS if c != sender])
                batch.append(transfer(t, sender, to, rng.randint(1, 40)))
        batches[t] = batch
    return batches


class TestProductionFuzz:
    def test_production_fuzz_deterministic_replay(self):
        batches = production_fuzz(seed=77)
        log, ledger, state = record_history(dict(CITIZENS), batches)
        assert ledger.verify_chain()
        result = replay(log)
        assert result.ok, f"mismatch at tick {result.mismatch_tick}"
        assert result.final_state_hash == state.state_hash()

    def test_production_fuzz_shuffled_equivalence(self):
        rng = random.Random(5)
        batches = production_fuzz(seed=78, ticks=15, per_tick=8)
        shuffled = {t: rng.sample(b, len(b)) for t, b in batches.items()}
        _, _, s1 = record_history(dict(CITIZENS), batches)
        _, _, s2 = record_history(dict(CITIZENS), shuffled)
        assert s1.state_hash() == s2.state_hash()

    def test_production_fuzz_money_invariant(self):
        batches = production_fuzz(seed=79)
        _, _, state = record_history(dict(CITIZENS), batches)
        total = sum(state.balances.values())
        assert total == INITIAL_TOTAL + state.money_minted - state.money_retired
        assert state.money_minted > 0  # work actually happened

    def test_production_fuzz_produced_goods(self):
        batches = production_fuzz(seed=80)
        _, _, state = record_history(dict(CITIZENS), batches)
        fish = state.coops["fishers"]["inventory"].get("fish", 0)
        assert fish > 0  # fishing actually ran

    def test_production_fuzz_multiple_seeds(self):
        for seed in (81, 82, 83):
            batches = production_fuzz(seed=seed, ticks=25, per_tick=10)
            log, ledger, state = record_history(dict(CITIZENS), batches)
            assert ledger.verify_chain(), f"seed {seed}: chain broken"
            result = replay(log)
            assert result.ok, f"seed {seed}: mismatch at {result.mismatch_tick}"

    def test_tampered_produce_detected(self):
        batches = production_fuzz(seed=84, ticks=20, per_tick=10)
        log, ledger, _ = record_history(dict(CITIZENS), batches)
        accepted_hashes = {
            rec.tx_hash for rec in ledger.records if rec.accepted and rec.tx["action"] == "PRODUCE"
        }
        assert accepted_hashes, "no accepted PRODUCE in history"
        for tick, batch in log.batches.items():
            for i, t in enumerate(batch):
                if t.action == "PRODUCE" and t.content_hash() in accepted_hashes:
                    forged = replace(t, payload={
                        "coop_id": t.payload["coop_id"],
                        "recipe_id": t.payload["recipe_id"],
                        "runs": t.payload["runs"] + 3,
                    })
                    log.batches[tick] = [forged if j == i else orig for j, orig in enumerate(batch)]
                    result = replay(log)
                    assert result.ok is False
                    return
        pytest.fail("accepted PRODUCE not found")
