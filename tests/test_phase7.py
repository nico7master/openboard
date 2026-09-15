"""Phase 7 gates: bot simulations — the "prove it" battery (D13, spec §10)."""

from __future__ import annotations

from openboard import genesis_state
from openboard.bots import (
    ARCHETYPES,
    champion_voter,
    collusive_faction,
    free_rider,
    hoarder,
    honest_worker,
    innovator,
    price_manipulator,
)
from openboard.metrics import gini
from openboard.sim import make_specialist, run_simulation, total_money


def default_params(**overrides):
    from openboard.rules import DEFAULT_RULESET_PARAMS

    params = dict(DEFAULT_RULESET_PARAMS)
    params["triage_overrides"] = {}
    params.update(overrides)
    return params


def gov_params(**overrides):
    """Governance live from genesis (v1)."""
    params = default_params()
    params["governance"] = {
        "enabled": True,
        "vote_window_ticks": 2,
        "quorum_bp": 5_000,
        "trial_period_ticks": 10,
    }
    params.update(overrides)
    return params


FARMER = make_specialist("grain_farming", "grain", {})
MILLER = make_specialist("grain_to_flour", "flour", {"grain": 10})
BAKER = make_specialist("flour_to_bread", "bread", {"flour": 5})

COOPS = [
    {"coop_id": "farmers", "members": ["farmer_a", "farmer_b"]},
    {"coop_id": "millers", "members": ["miller_a", "miller_b"]},
    {"coop_id": "bakers", "members": ["baker_a", "baker_b"]},
]
TREASURIES = {"millers": 600, "bakers": 600}


def baseline_cast(extra=()):
    cast = [
        ("farmer_a", FARMER), ("farmer_b", FARMER),
        ("miller_a", MILLER), ("miller_b", MILLER),
        ("baker_a", BAKER), ("baker_b", BAKER),
        ("worker_a", honest_worker), ("worker_b", honest_worker),
    ]
    cast.extend(extra)
    # workers need a coop: they join the farmers coop via membership
    coops = [
        {"coop_id": "farmers", "members": ["farmer_a", "farmer_b", "worker_a", "worker_b"]},
        {"coop_id": "millers", "members": ["miller_a", "miller_b"]},
        {"coop_id": "bakers", "members": ["baker_a", "baker_b"]},
    ]
    return cast, coops


class TestGini:
    def test_hand_computed_values(self):
        assert gini([10, 10, 10, 10]) == 0
        assert gini([0, 0, 0, 40]) == 7_500  # max for n=4 is (n-1)/n
        assert gini([0, 0, 20, 20]) == 5_000
        assert gini([]) == 0
        assert gini([7]) == 0


class TestBaselineEconomy:
    def test_hundred_ticks_stable(self):
        cast, coops = baseline_cast()
        state, ledger, metrics = run_simulation(
            cast, coops, ticks=100, seed=1,
            ruleset_params=default_params(), seed_treasuries=TREASURIES,
        )
        initial = 500 * len(cast) + sum(TREASURIES.values())
        assert total_money(state) == initial + state.money_minted - state.money_retired
        assert all(b >= 0 for b in state.balances.values())
        assert state.tick == 100

        # essentials actually consumed
        bread_eaten = sum(inv.get("bread", 0) for inv in state.citizen_inventory.values())
        assert bread_eaten > 0

        # the chain flowed: some market clearing happened
        assert metrics.clearing_prices, "no market activity at all"

        # moderate inequality (not a plutocracy, not forced equality)
        assert metrics.gini_bp[-1] < 8_000

    def test_same_seed_same_hash(self):
        cast, coops = baseline_cast()
        s1, _, _ = run_simulation(cast, coops, 30, 7, default_params(), TREASURIES)
        s2, _, _ = run_simulation(cast, coops, 30, 7, default_params(), TREASURIES)
        assert s1.state_hash() == s2.state_hash()

    def test_different_seed_different_world(self):
        cast, coops = baseline_cast()
        s1, _, _ = run_simulation(cast, coops, 30, 7, default_params(), TREASURIES)
        s2, _, _ = run_simulation(cast, coops, 30, 8, default_params(), TREASURIES)
        assert s1.state_hash() != s2.state_hash()


class TestAdversarials:
    def test_hoarder_flagged(self):
        cast, coops = baseline_cast(extra=[("greta", hoarder)])
        coops[0]["members"].append("greta")  # she works minimally
        state, _, _ = run_simulation(
            cast, coops, 30, 2, default_params(), TREASURIES,
        )
        kinds = {f["kind"] for f in state.flags}
        assert "HOARD" in kinds

    def test_free_rider_flagged(self):
        cast, coops = baseline_cast(extra=[("freddy", free_rider)])
        state, _, _ = run_simulation(
            cast, coops, 30, 3, default_params(), TREASURIES,
        )
        kinds = {f["kind"] for f in state.flags}
        assert "FREE_RIDER" in kinds

    def test_price_manipulator_flagged(self):
        cast, coops = baseline_cast(extra=[("manny", price_manipulator)])
        coops[0]["members"].append("manny")  # his coop lists; he wash-bids
        state, _, _ = run_simulation(
            cast, coops, 40, 4, default_params(), TREASURIES,
        )
        kinds = {f["kind"] for f in state.flags}
        assert "WASH_BID" in kinds


class TestGovernanceAttacks:
    def test_faction_capture_fails_quorum(self):
        cast = [
            ("champ", champion_voter),
            ("fact_a", collusive_faction),
            ("fact_b", collusive_faction),
            ("inno", innovator),
            ("w1", honest_worker), ("w2", honest_worker),
            ("w3", honest_worker), ("w4", honest_worker),
        ]
        coops = [{"coop_id": "commune", "members": [c for c, _ in cast]}]
        state, ledger, metrics = run_simulation(
            cast, coops, 26, 5, gov_params(), {"commune": 1000},
        )
        # the champion proposed at tick 20; window closed; quorum 4 of 8
        assert metrics.proposals_failed >= 1
        assert metrics.proposals_passed == 0
        # the self-serving quota never activated
        assert state.active_ruleset_params()["essential_need_quota"].get("bread", 4) < 20

    def test_council_can_dissolve_hoard_via_vote(self):
        from openboard import Ledger, Transaction, apply_tick

        # council: carol+dave; hoarder: eve accumulates grain
        params = gov_params()
        params["oversight"] = {
            "hoard_multiplier": 3,
            "market_power_share_bp": 7_000,
            "free_rider_min_hours": 5,
            "council_members": ["carol", "dave"],
        }
        citizens = {"alice": 500, "bob": 500, "carol": 500, "dave": 500, "eve": 500}
        state = genesis_state(citizens, ruleset_params=params)
        ledger = Ledger()
        # true-need balance: bread quota 1 -> hoard threshold 3x1=3
        state.citizen_inventory["eve"] = {"bread": 4}  # 4 > threshold 3

        apply_tick(state, ledger, [Transaction(
            tick=1, sender="carol", action="INTERVENE",
            payload={"intervention": {"type": "DISSOLVE_HOARD", "target": "eve", "good": "bread"}},
            ruleset_version=1,
        )], current_tick=1)
        apply_tick(state, ledger, [
            Transaction(tick=2, sender="alice", action="VOTE", payload={"proposal_id": "p1", "choice": "for"}, ruleset_version=1),
            Transaction(tick=2, sender="bob", action="VOTE", payload={"proposal_id": "p1", "choice": "for"}, ruleset_version=1),
            Transaction(tick=2, sender="carol", action="VOTE", payload={"proposal_id": "p1", "choice": "for"}, ruleset_version=1),
        ], current_tick=2)
        apply_tick(state, ledger, [], current_tick=3)  # settle

        assert state.citizen_inventory["eve"]["bread"] == 3
        assert state.common_pool["bread"] == 1
