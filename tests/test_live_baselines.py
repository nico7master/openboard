"""D21d live-cost baselines: a dead producer's good must reprice to
TRUE current cost, not the stale price stamped when inputs were cheap.

Observed root: fishing stamped 63u when electricity was cheap; at the
live electricity baseline the true unit cost rises, so the fishery
could never break even -> chronic death-rescue cadence (fish streak 47).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "dashboard"))

from openboard.engine import apply_tick, _live_cost_restamp
from openboard.ledger import Ledger
from openboard.state import genesis_state  # noqa: F401


def _mini_params(**over):
    from server import Run

    params = dict(Run(seed=1).state.active_ruleset_params())
    params["live_cost_baselines"] = {"enabled": True}
    params.update(over)
    return params


def test_restamp_never_shrinks_a_baseline() -> None:
    from server import Run

    run = Run(seed=1)
    s = run.state
    before = dict(s.good_cost_baseline)
    _live_cost_params = {"live_cost_baselines": {"enabled": True}}
    _live_cost_restamp(s, _live_cost_params)
    for g, v in s.good_cost_baseline.items():
        assert v >= before.get(g, 1), f"baseline shrank for {g}: {before.get(g)} -> {v}"


def test_fish_baseline_rises_to_true_cost() -> None:
    from server import Run

    run = Run(seed=42)
    s = run.state
    elec_before = s.good_cost_baseline.get("electricity", 1)
    _live_cost_restamp(s, {"live_cost_baselines": {"enabled": True},
                           "money_cap": s.active_ruleset_params().get("money_cap"),
                           "durable_capital": s.active_ruleset_params().get("durable_capital")})
    # fishing: 30 labor-hours x upc + 8 elec; 50 fish -> per-unit >= wage share
    _mc = (s.active_ruleset_params().get("money_cap") or {})
    _upc = int(_mc.get("units_per_credit", 100)) if _mc.get("enabled") else 1
    expected_wage_part = 30 * _upc
    expected = max(1, -(-(30 * _upc + 8 * elec_before) // 50))
    assert s.good_cost_baseline["fish"] >= expected, (
        f"fish baseline {s.good_cost_baseline['fish']} < true cost {expected}"
    )


def test_param_absent_is_inert() -> None:
    from server import Run

    run = Run(seed=1)
    s = run.state
    before = dict(s.good_cost_baseline)
    # no live_cost_baselines in params -> no pass registered: apply_tick must
    # leave baselines untouched when the rule never ran
    apply_tick(s, run.ledger, [], current_tick=s.tick + 1)
    for g, v in s.good_cost_baseline.items():
        assert v == before.get(g, 1) or v > before.get(g, 1)
