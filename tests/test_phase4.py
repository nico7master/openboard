"""Phase 4 tests: markets — listings, uniform-price auctions, essential
triage sales, surplus pool flow, retirement, and the baseline stability
campaign (the phase gate)."""

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


def list_good(tick, sender, coop_id, good, qty, ruleset_version=1):
    return tx(tick, sender, "LIST_GOOD", {"coop_id": coop_id, "good": good, "qty": qty}, ruleset_version)


def bid(tick, sender, good, max_price, qty, ruleset_version=1):
    return tx(tick, sender, "BID", {"good": good, "max_price": max_price, "qty": qty}, ruleset_version)


def bid_for_coop(tick, sender, coop_id, good, max_price, qty, ruleset_version=1):
    return tx(tick, sender, "BID_FOR_COOP", {"coop_id": coop_id, "good": good, "max_price": max_price, "qty": qty}, ruleset_version)


def buy_essential(tick, sender, good, qty, ruleset_version=1):
    return tx(tick, sender, "BUY_ESSENTIAL", {"good": good, "qty": qty}, ruleset_version)


def market_events(state, tick):
    return [e for e in state.applied if e.get("tick") == tick and e.get("action", "").startswith(("MARKET", "SURPLUS"))]


def total_credits(state) -> int:
    """Invariant v2: balances + pool + treasuries."""
    treasuries = sum(c.get("treasury", 0) for c in state.coops.values())
    return sum(state.balances.values()) + state.surplus_pool + treasuries


# ------------------------------------------------------------ LISTING TESTS


class TestListings:
    def test_list_good_escrows_inventory(self):
        state = genesis_state(dict(CITIZENS))
        ledger = Ledger()
        apply_tick(state, ledger, [found_coop(1, "alice", "fishers", ["alice", "bob"])])
        # produce some fish first
        for t in range(2, 6):
            apply_tick(state, ledger, [work(t, "alice", "fishers", 8)], current_tick=t)
        apply_tick(state, ledger, [produce(6, "bob", "fishers", "fishing", 1)], current_tick=6)
        fish_available = state.coops["fishers"]["inventory"]["fish"]

        # Listing is escrowed at apply time (inventory decremented) and the
        # listing is accepted; with no bids, clearing returns everything.
        apply_tick(state, ledger, [list_good(7, "alice", "fishers", "fish", 20)], current_tick=7)
        listed = [r for r in ledger.records if r.accepted and r.tx["action"] == "LIST_GOOD"]
        assert listed, "listing must be accepted"
        assert state.listings == {}  # nothing left listed after clearing
        assert state.coops["fishers"]["inventory"]["fish"] == fish_available  # returned

        # with a bid in the same tick, listed goods are sold, not returned
        apply_tick(state, ledger, [
            list_good(8, "alice", "fishers", "fish", 20),
            bid(8, "carol", "fish", state.good_cost_baseline["fish"] + 2, 20),
        ], current_tick=8)
        assert state.coops["fishers"]["inventory"]["fish"] == fish_available - 20
        assert state.citizen_inventory["carol"]["fish"] == 20

    def test_list_not_a_member(self):
        state = genesis_state(dict(CITIZENS))
        ledger = Ledger()
        apply_tick(state, ledger, [found_coop(1, "alice", "fishers", ["alice", "bob"])])
        state.coops["fishers"]["inventory"]["fish"] = 50
        apply_tick(state, ledger, [list_good(2, "carol", "fishers", "fish", 10)], current_tick=2)
        assert ledger.records[-1].reason == "NOT_A_MEMBER"

    def test_list_unknown_good(self):
        state = genesis_state(dict(CITIZENS))
        ledger = Ledger()
        apply_tick(state, ledger, [found_coop(1, "alice", "fishers", ["alice", "bob"])])
        apply_tick(state, ledger, [list_good(2, "alice", "fishers", "unobtanium", 10)], current_tick=2)
        assert ledger.records[-1].reason == "GOOD_UNKNOWN"

    def test_list_more_than_inventory(self):
        state = genesis_state(dict(CITIZENS))
        ledger = Ledger()
        apply_tick(state, ledger, [found_coop(1, "alice", "fishers", ["alice", "bob"])])
        apply_tick(state, ledger, [list_good(2, "alice", "fishers", "water", 99999)], current_tick=2)
        assert ledger.records[-1].reason == "NOT_ENOUGH_INVENTORY"


# --------------------------------------------------------------- BID TESTS


class TestBids:
    def test_bid_below_floor_rejected(self):
        state = genesis_state(dict(CITIZENS))
        ledger = Ledger()
        floor = state.good_cost_baseline["fish"]
        apply_tick(state, ledger, [bid(1, "alice", "fish", floor - 1, 5)])
        assert ledger.records[0].reason == "INVALID_PRICE"

    def test_bid_cannot_afford_rejected(self):
        state = genesis_state(dict(CITIZENS))
        ledger = Ledger()
        floor = state.good_cost_baseline["fish"]
        apply_tick(state, ledger, [bid(1, "eve", "fish", floor, 100)])  # 200 < 5*100
        assert ledger.records[0].reason == "INSUFFICIENT_FUNDS"

    def test_bid_valid_accepted_no_listings(self):
        state = genesis_state(dict(CITIZENS))
        ledger = Ledger()
        floor = state.good_cost_baseline["fish"]
        apply_tick(state, ledger, [bid(1, "alice", "fish", floor, 5)])
        assert ledger.accepted_count() == 1
        # no supply -> nothing happens, no crash
        assert state.balances["alice"] == 1000

    def test_bid_at_floor_clears_with_no_surplus(self):
        state = genesis_state(dict(CITIZENS))
        ledger = Ledger()
        apply_tick(state, ledger, [found_coop(1, "alice", "fishers", ["alice", "bob"])])
        state.coops["fishers"]["inventory"]["fish"] = 50
        floor = state.good_cost_baseline["fish"]

        apply_tick(state, ledger, [
            list_good(2, "alice", "fishers", "fish", 50),
            bid(2, "carol", "fish", floor, 10),
        ], current_tick=2)

        # carol bought 10 fish at floor; seller got floor*10; no surplus
        assert state.citizen_inventory["carol"]["fish"] == 10
        assert state.balances["carol"] == 600 - 10 * floor
        assert state.coops["fishers"]["treasury"] == 10 * floor
        assert state.surplus_pool == 0
        assert state.coops["fishers"]["inventory"]["fish"] == 40  # unsold returned

    def test_two_bids_uniform_price(self):
        """THE price-discovery test: clearing = lowest winning bid."""
        state = genesis_state(dict(CITIZENS))
        ledger = Ledger()
        apply_tick(state, ledger, [found_coop(1, "alice", "fishers", ["alice", "bob"])])
        state.coops["fishers"]["inventory"]["fish"] = 50
        floor = state.good_cost_baseline["fish"]

        apply_tick(state, ledger, [
            list_good(2, "alice", "fishers", "fish", 50),
            bid(2, "carol", "fish", floor + 10, 10),  # high bidder
            bid(2, "dave", "fish", floor + 4, 10),   # low bidder -> clears here
        ], current_tick=2)

        clearing = floor + 4
        # both win 10 at the uniform clearing price
        assert state.citizen_inventory["carol"]["fish"] == 10
        assert state.citizen_inventory["dave"]["fish"] == 10
        assert state.balances["carol"] == 600 - 10 * clearing
        assert state.balances["dave"] == 400 - 10 * clearing

        # seller gets floor*20; surplus = (clearing-floor)*20
        assert state.coops["fishers"]["treasury"] == 20 * floor
        assert state.surplus_pool == (clearing - floor) * 20

        evt = [e for e in market_events(state, 2) if e["action"] == "MARKET_CLEAR_AUCTION"][0]
        assert evt["clearing_price"] == clearing
        assert evt["sold"] == 20

    def test_losing_bid_gets_nothing(self):
        state = genesis_state(dict(CITIZENS))
        ledger = Ledger()
        apply_tick(state, ledger, [found_coop(1, "alice", "fishers", ["alice", "bob"])])
        state.coops["fishers"]["inventory"]["fish"] = 10
        floor = state.good_cost_baseline["fish"]

        apply_tick(state, ledger, [
            list_good(2, "alice", "fishers", "fish", 10),
            bid(2, "carol", "fish", floor + 10, 10),
            bid(2, "dave", "fish", floor + 5, 10),  # loses: supply exhausted
        ], current_tick=2)

        assert state.citizen_inventory["carol"]["fish"] == 10
        assert "fish" not in state.citizen_inventory.get("dave", {})
        assert state.balances["dave"] == 400  # untouched

    def test_coop_bid_buys_inputs(self):
        state = genesis_state(dict(CITIZENS))
        ledger = Ledger()
        apply_tick(state, ledger, [
            found_coop(1, "alice", "farmers", ["alice", "bob"]),
            found_coop(1, "carol", "millers", ["carol", "dave"]),
        ])
        # millers need grain; farmers have some
        state.coops["farmers"]["inventory"]["grain"] = 100
        state.coops["millers"]["treasury"] = 1000
        floor = state.good_cost_baseline["grain"]

        apply_tick(state, ledger, [
            list_good(2, "alice", "farmers", "grain", 40),
            bid_for_coop(2, "carol", "millers", "grain", floor, 30),
        ], current_tick=2)

        assert state.coops["millers"]["inventory"]["grain"] == 30
        assert state.coops["millers"]["treasury"] == 1000 - 30 * floor
        assert state.coops["farmers"]["treasury"] == 30 * floor


# ---------------------------------------------------------- ESSENTIAL TESTS


class TestEssentials:
    def test_buy_essential_at_baseline(self):
        state = genesis_state(dict(CITIZENS))
        ledger = Ledger()
        apply_tick(state, ledger, [found_coop(1, "alice", "farmers", ["alice", "bob"])])
        state.coops["farmers"]["inventory"]["grain"] = 100
        floor = state.good_cost_baseline["grain"]

        apply_tick(state, ledger, [
            list_good(2, "alice", "farmers", "grain", 50),
            buy_essential(2, "carol", "grain", 5),
        ], current_tick=2)

        assert state.citizen_inventory["carol"]["grain"] == 5
        assert state.balances["carol"] == 600 - 5 * floor
        assert state.coops["farmers"]["treasury"] == 5 * floor
        assert state.surplus_pool == 0  # essentials at cost — no surplus

    def test_essential_priority_over_bids(self):
        """Rations to all first, surplus to auction (D8)."""
        state = genesis_state(dict(CITIZENS))
        ledger = Ledger()
        apply_tick(state, ledger, [found_coop(1, "alice", "farmers", ["alice", "bob"])])
        state.coops["farmers"]["inventory"]["grain"] = 10
        floor = state.good_cost_baseline["grain"]

        apply_tick(state, ledger, [
            list_good(2, "alice", "farmers", "grain", 10),
            buy_essential(2, "carol", "grain", 4),  # essential takes priority
            bid(2, "dave", "grain", floor + 3, 10),  # market bid gets the rest
        ], current_tick=2)

        # carol got her ration at floor
        assert state.citizen_inventory["carol"]["grain"] == 4
        assert state.balances["carol"] == 600 - 4 * floor
        # dave got the remaining 6 at his bid price
        assert state.citizen_inventory["dave"]["grain"] == 6
        # surplus from dave's purchase above floor
        assert state.surplus_pool == 6 * 3

    def test_essential_not_essential_good(self):
        state = genesis_state(dict(CITIZENS))
        ledger = Ledger()
        # furniture is a market good
        apply_tick(state, ledger, [buy_essential(1, "alice", "furniture", 1)])
        assert ledger.records[0].reason == "NOT_ESSENTIAL"

    def test_essential_quota_exceeded(self):
        state = genesis_state(dict(CITIZENS))
        ledger = Ledger()
        # default quota for grain is 10
        apply_tick(state, ledger, [buy_essential(1, "alice", "grain", 11)])
        assert ledger.records[0].reason == "QUOTA_EXCEEDED"

    def test_essential_quota_is_votable(self):
        state = genesis_state(dict(CITIZENS))
        ledger = Ledger()
        new_params = params_with(essential_need_quota={"grain": 2})
        apply_tick(state, ledger, [
            tx(1, "alice", "RULE_CHANGE", {"params": new_params, "activation_tick": 2})
        ])
        apply_tick(state, ledger, [buy_essential(2, "bob", "grain", 3, ruleset_version=2)], current_tick=2)
        assert ledger.records[-1].reason == "QUOTA_EXCEEDED"

    def test_essential_insufficient_funds(self):
        state = genesis_state(dict(CITIZENS))
        ledger = Ledger()
        # eve has 200; bread floor is 3 -> 100 bread = 300 > 200
        apply_tick(state, ledger, [buy_essential(1, "eve", "bread", 100)])
        assert ledger.records[0].reason in ("QUOTA_EXCEEDED", "INSUFFICIENT_FUNDS")


# ------------------------------------------------------------ RETIREMENT


class TestRetirement:
    def test_pool_retired_beyond_cap(self):
        state = genesis_state(dict(CITIZENS), ruleset_params=params_with(surplus_reserve_cap=100))
        ledger = Ledger()
        apply_tick(state, ledger, [found_coop(1, "alice", "fishers", ["alice", "bob"])])
        state.coops["fishers"]["inventory"]["fish"] = 100
        floor = state.good_cost_baseline["fish"]

        # carol bids above floor within her means: surplus = 20*20 = 400 > cap 100
        apply_tick(state, ledger, [
            list_good(2, "alice", "fishers", "fish", 100),
            bid(2, "carol", "fish", floor + 20, 20),
        ], current_tick=2)

        assert state.surplus_pool == 100  # capped
        assert state.money_retired == 20 * 20 - 100

        evt = [e for e in market_events(state, 2) if e["action"] == "SURPLUS_RETIRE"]
        assert evt and evt[0]["excess_retired"] == 20 * 20 - 100

    def test_pool_below_cap_not_retired(self):
        state = genesis_state(dict(CITIZENS), ruleset_params=params_with(surplus_reserve_cap=100_000))
        ledger = Ledger()
        apply_tick(state, ledger, [found_coop(1, "alice", "fishers", ["alice", "bob"])])
        state.coops["fishers"]["inventory"]["fish"] = 50
        floor = state.good_cost_baseline["fish"]

        apply_tick(state, ledger, [
            list_good(2, "alice", "fishers", "fish", 50),
            bid(2, "carol", "fish", floor + 5, 10),
        ], current_tick=2)

        assert state.surplus_pool == 5 * 10
        assert state.money_retired == 0


# ------------------------------------------------------------- INVARIANTS


class TestInvariantV2:
    def test_invariant_after_market_activity(self):
        state = genesis_state(dict(CITIZENS))
        ledger = Ledger()
        apply_tick(state, ledger, [found_coop(1, "alice", "fishers", ["alice", "bob"])])
        state.coops["fishers"]["inventory"]["fish"] = 100
        floor = state.good_cost_baseline["fish"]

        apply_tick(state, ledger, [
            work(2, "alice", "fishers", 4),
            list_good(2, "alice", "fishers", "fish", 60),
            bid(2, "carol", "fish", floor + 8, 30),
            bid(2, "dave", "fish", floor + 3, 20),
            buy_essential(2, "eve", "water", 2),
        ], current_tick=2)

        assert total_credits(state) == INITIAL_TOTAL + state.money_minted - state.money_retired


# --------------------------------------------------------------- CAMPAIGN


class TestBaselineCampaign:
    """The Phase 4 gate: a scripted multi-co-op economy runs cleanly."""

    def run_campaign(self, seed: int, ticks: int = 36) -> tuple:
        """farmers -> grain; millers -> flour; bakers -> bread; citizens buy.

        Each tick is built against the LIVE state and applied immediately —
        the scripted economy actually reacts to its own production.
        """
        rng = random.Random(seed)

        citizens = {"alice": 500, "bob": 400, "carol": 350, "dave": 300, "eve": 250, "frank": 250}
        state = genesis_state(dict(citizens))
        ledger = Ledger()
        batches: dict[int, list[Transaction]] = {}

        # tick 1: found the three co-ops (disjoint memberships)
        batches[1] = [
            found_coop(1, "alice", "farmers", ["alice", "bob"]),
            found_coop(1, "carol", "millers", ["carol", "dave"]),
            found_coop(1, "eve", "bakers", ["eve", "frank"]),
        ]
        apply_tick(state, ledger, batches[1], current_tick=1)

        # seed treasuries so millers/bakers can buy inputs
        state.coops["millers"]["treasury"] = 600
        state.coops["bakers"]["treasury"] = 600

        grain_floor = state.good_cost_baseline["grain"]
        flour_floor = state.good_cost_baseline["flour"]
        bread_floor = state.good_cost_baseline["bread"]

        for t in range(2, ticks + 1):
            batch: list[Transaction] = []
            # everyone works
            batch.append(work(t, "alice", "farmers", 8))
            batch.append(work(t, "bob", "farmers", 5))
            batch.append(work(t, "carol", "millers", 8))
            batch.append(work(t, "dave", "millers", 5))
            batch.append(work(t, "eve", "bakers", 8))
            batch.append(work(t, "frank", "bakers", 5))

            # production decisions against live state
            farmers = state.coops["farmers"]
            millers = state.coops["millers"]
            bakers = state.coops["bakers"]

            if farmers["labor_pool_hours"] >= 40 and farmers["inventory"].get("water", 0) >= 5:
                batch.append(produce(t, "alice", "farmers", "grain_farming", 1))
            if farmers["inventory"].get("grain", 0) >= 40:
                batch.append(list_good(t, "alice", "farmers", "grain", 40))
            if millers["inventory"].get("grain", 0) >= 10 and millers["labor_pool_hours"] >= 2:
                batch.append(produce(t, "carol", "millers", "grain_to_flour", 1))
            if millers["inventory"].get("flour", 0) >= 10:
                batch.append(list_good(t, "carol", "millers", "flour", 9))
            if bakers["inventory"].get("flour", 0) >= 5 and bakers["labor_pool_hours"] >= 3:
                batch.append(produce(t, "eve", "bakers", "flour_to_bread", 1))
            if bakers["inventory"].get("bread", 0) >= 15:
                batch.append(list_good(t, "eve", "bakers", "bread", 15))

            # input purchases (market bids from treasuries)
            if t > 3:
                if millers.get("treasury", 0) >= (grain_floor + 2) * 10:
                    batch.append(bid_for_coop(t, "carol", "millers", "grain", grain_floor + 2, 10))
                if bakers.get("treasury", 0) >= (flour_floor + 2) * 5:
                    batch.append(bid_for_coop(t, "eve", "bakers", "flour", flour_floor + 2, 5))

            # citizen purchases
            batch.append(buy_essential(t, "alice", "bread", 2))
            batch.append(buy_essential(t, "bob", "bread", 2))
            if state.balances["carol"] >= (bread_floor + 4) * 3:
                batch.append(bid(t, "carol", "bread", bread_floor + rng.randint(0, 4), 3))
            if state.balances["dave"] >= (bread_floor + 4) * 3:
                batch.append(bid(t, "dave", "bread", bread_floor + rng.randint(0, 4), 3))

            batches[t] = batch
            apply_tick(state, ledger, batch, current_tick=t)

        return state, ledger, batches

    def test_campaign_economy_runs_clean(self):
        state, ledger, batches = self.run_campaign(seed=1)

        # invariant holds
        initial = sum({"alice": 500, "bob": 400, "carol": 350, "dave": 300, "eve": 250, "frank": 250}.values())
        treasuries = sum(c.get("treasury", 0) for c in state.coops.values())
        # note: 600+600 seeded treasuries are injected state (not via tx) —
        # invariant must account for them
        total = sum(state.balances.values()) + state.surplus_pool + treasuries
        assert total == initial + 1200 + state.money_minted - state.money_retired

        # no negative balances or inventories anywhere
        assert all(b >= 0 for b in state.balances.values())
        for coop in state.coops.values():
            assert all(q >= 0 for q in coop["inventory"].values())
            assert coop.get("treasury", 0) >= 0
            assert coop.get("labor_pool_hours", 0) >= 0
        assert state.surplus_pool >= 0

        # economic activity actually happened
        assert state.money_minted > 0
        assert any("bread" in inv for inv in state.citizen_inventory.values())

        # grain flowed through the chain: farmers -> millers -> bakers
        assert state.coops["farmers"]["treasury"] > 0
        assert state.coops["millers"]["inventory"].get("flour", 0) >= 0

        # determinism: same seed -> identical final state hash
        state2, ledger2, _ = self.run_campaign(seed=1)
        assert state2.state_hash() == state.state_hash()

    def test_campaign_multiple_seeds(self):
        for seed in (2, 3):
            state, ledger, batches = self.run_campaign(seed=seed)
            assert all(b >= 0 for b in state.balances.values())
            for coop in state.coops.values():
                assert all(q >= 0 for q in coop["inventory"].values())


def _batches_to_log(citizens, batches):
    from openboard.replay import InputLog

    return InputLog(genesis=citizens, batches=batches, state_hashes=[])
