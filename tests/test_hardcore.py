"""Hard Core A4: 2,000-tick long-run survival gate.

The 500-tick circular-flow gate could not see the t~800 freeze (capital
depletion -> utility cascade). This gate runs 3 seeds x 2,000 ticks and
requires the economy to stay alive the whole way.
"""
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "dashboard"))

from server import Run  # noqa: E402
from openboard.metrics import gini  # noqa: E402


class TestLongRunSurvival:
    def _run_world(self, seed: int, ticks: int = 2_000) -> Run:
        run = Run(seed=seed)
        for t in range(2, ticks + 1):
            actions = []
            for name, meta in sorted(run.bots.items()):
                rng = random.Random(f"{seed}:{t}:{name}")
                actions.extend(
                    meta["fn"](name, run.state, run.state.active_ruleset_params(), t, rng)
                )
            run._apply_batch(t, actions)
            run._record_timeline()
        return run

    def test_long_run_survival_gate(self):
        for seed in (42, 7, 123):
            run = self._run_world(seed)
            s = run.state

            # (a) zero unmet needs over the final 500 ticks
            assert max(run.timeline["unmet"][-500:]) == 0, f"seed {seed}: unmet needs returned"

            # (b) utilities above floors: the circular chain stays fed
            assert s.coops["miners"]["inventory"].get("machines", 0) >= 1, f"seed {seed}: miners out of machines"
            assert s.coops["power_plant"]["inventory"].get("electricity", 0) >= 50, f"seed {seed}: power stock low"
            assert s.coops["water_works"]["inventory"].get("water", 0) >= 50, f"seed {seed}: water stock low"

            # (c) solvency: essential chain must be solvent; every coop
            # must at least be non-deadlocked. A coop with no current
            # demand (e.g. iron_miners when steelworks is fully stocked)
            # legitimately idles at treasury ~0 while members keep earning
            # minted wages — that is NOT bankruptcy. Deadlock = no money,
            # no sellable stock, no way to earn when demand returns.
            ESSENTIAL_CHAIN = {"farmers", "farmers_north", "millers", "bakers",
                               "city_bakers", "miners", "power_plant",
                               "water_works", "wind_farm"}
            for cid, c in s.coops.items():
                tr = c.get("treasury", 0)
                if cid in ESSENTIAL_CHAIN:
                    assert tr > 0, f"seed {seed}: {cid} (essential chain) bankrupt"
                    continue
                has_stock = any(q > 0 for g, q in c.get("inventory", {}).items()
                                if g not in ("water", "electricity"))
                assert tr > 0 or has_stock,                     f"seed {seed}: {cid} deadlocked (no treasury, no stock)"

            # (d) Gini bounded
            wealth = list(s.balances.values()) + [s.surplus_pool, s.capital_fund] + [
                c.get("treasury", 0) for c in s.coops.values()
            ]
            assert gini(wealth) <= 5_000, f"seed {seed}: gini {gini(wealth)/10000:.3f} > 0.5"

            # (e) loop closure
            bought = sum(run.totals["bought"].values())
            consumed = sum(s.consumed_totals.values())
            assert bought > 0 and consumed / bought >= 0.6, f"seed {seed}: loop {consumed/bought:.2f}"

            # (f) money invariant, exact
            total = (
                sum(s.balances.values()) + s.surplus_pool + s.capital_fund
                + sum(c.get("treasury", 0) for c in s.coops.values())
            )
            from server import BASELINE_TREASURIES
            expected = (500 * len(s.balances)
                        + sum(BASELINE_TREASURIES.values())
                        + s.money_minted - s.money_retired)
            assert total == expected, f"seed {seed}: money invariant broken"

            # (g) capital fund sustained replacement (machines alive)
            assert s.capital_burned.get("miners", 0) > 0, f"seed {seed}: no capital burn tracked"


class TestExploits:
    def test_zombie_wage_farming_is_bounded(self):
        """Two citizens found a coop, log hours, never produce. Minted
        income must converge under the progressive wealth tax (steady state
        ~5,400 cr at 8/tick with 2% above 5,000)."""
        from openboard.engine import apply_tick  # noqa: E402
        from openboard.ledger import Transaction  # noqa: E402
        from openboard.state import genesis_state  # noqa: E402

        params = {
            "needs": {},
            "wealth_tax": {"threshold": 5_000, "rate_bp": 200},
            "max_work_hours_per_tick": 8,
        }
        s = genesis_state({"zed_a": 500, "zed_b": 500}, ruleset_params=params)
        led = __import__("openboard.ledger", fromlist=["Ledger"]).Ledger()
        v = s.ruleset_version
        apply_tick(s, led, [Transaction(tick=1, sender="zed_a", action="FOUND_COOP",
                                        payload={"coop_id": "zombies", "name": "zombies",
                                                 "members": ["zed_a", "zed_b"]},
                                        ruleset_version=v)], current_tick=1)
        assert "zombies" in s.coops, "founding rejected"
        for t in range(2, 1_002):
            batch = [
                Transaction(tick=t, sender=w, action="WORK",
                            payload={"coop_id": "zombies", "hours": 8},
                            ruleset_version=v)
                for w in ("zed_a", "zed_b")
            ]
            apply_tick(s, led, batch, current_tick=t)

        for w in ("zed_a", "zed_b"):
            bal = s.balances[w]
            assert bal < 7_000, f"{w} farming unbounded: {bal}"
        assert any(e and e.get("action") == "WEALTH_TAX" for e in s.applied)

    def test_multiple_work_per_tick_capped(self):
        """An attacker submitting many WORK txs in one tick must not mint
        beyond max_work_hours_per_tick cumulative hours."""
        from openboard.engine import apply_tick  # noqa: E402
        from openboard.ledger import Ledger, Transaction  # noqa: E402
        from openboard.state import genesis_state  # noqa: E402

        params = {"needs": {}, "max_work_hours_per_tick": 8, "max_work_hours_cumulative": 8}
        s = genesis_state({"greed": 500, "mule": 500}, ruleset_params=params)
        led = Ledger()
        v = s.ruleset_version
        apply_tick(s, led, [Transaction(tick=1, sender="greed", action="FOUND_COOP",
                                        payload={"coop_id": "sweatshop", "name": "sweatshop",
                                                 "members": ["greed", "mule"]},
                                        ruleset_version=v)], current_tick=1)
        assert "sweatshop" in s.coops
        # attack A: identical txs -> all duplicates after the first hash
        # attack B: distinct txs (8,7,6,5,4,3,2,1 = 36h) -> dedup-proof
        hours_list = [8, 8, 8, 7, 6, 5, 4, 3, 2, 1]
        apply_tick(s, led, [
            Transaction(tick=2, sender="greed", action="WORK",
                        payload={"coop_id": "sweatshop", "hours": h}, ruleset_version=v)
            for h in hours_list
        ], current_tick=2)
        # cumulative minted hours this tick must stay <= cap (8), not 44;
        # deterministic hash-sort admits a subset (e.g. 1+2+3=6), never more
        minted = s.balances["greed"] - 500
        assert 0 < minted <= 8, minted
        assert s.coops["sweatshop"]["labor_pool_hours"] == minted
