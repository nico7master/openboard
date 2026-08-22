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

            # (c) all co-ops solvent
            for cid, c in s.coops.items():
                assert c.get("treasury", 0) > 0, f"seed {seed}: {cid} bankrupt"

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
            expected = 14 * 500 + 4 * 600 + s.money_minted - s.money_retired
            assert total == expected, f"seed {seed}: money invariant broken"

            # (g) capital fund sustained replacement (machines alive)
            assert s.capital_burned.get("miners", 0) > 0, f"seed {seed}: no capital burn tracked"
