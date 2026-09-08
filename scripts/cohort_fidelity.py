#!/usr/bin/env python
"""Cohort fidelity probe: winning policy through the surrogate vs 1:1.

Doctrine rung 1 (docs/ideas/2026-09-08-scaling-doctrine-*.md): if the
986-agent K=100 world reproduces the equity/stability direction of the
full-population world under the SAME proven policy (wealth tax 400bp,
dividend share 3000bp — the harvest's recommended path), the surrogate
is calibrated for policy prediction at 98,600 represented people.

Fork rule (memory + project law): mutate the forked world's active
ruleset params IN PLACE, never bump the ruleset version (a version bump
makes the engine reject every bot tx as RULESET_MISMATCH).

Usage: python scripts/cohort_fidelity.py [ticks] [seed]
"""
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "dashboard"))
sys.path.insert(0, str(ROOT / "scripts"))

from openboard.metrics import top1_share_bp  # noqa: E402
from stage6_scale_gate import ESSENTIALS, drive, money_delta, scale_world  # noqa: E402
from harvest_rerun import holders  # noqa: E402  (private-wealth extraction, pool excluded)

TICKS = int(sys.argv[1]) if len(sys.argv) > 1 else 150
SEED = int(sys.argv[2]) if len(sys.argv) > 2 else 42
K = 100


def apply_winning_policy(run):
    """In-place param mutation on the active ruleset (fork rule).

    PITFALL (from the harvest): the wealth-tax threshold is ALREADY
    upc-scaled (x100) by the world constructor — never overwrite it here
    or the tax silently changes behavior. Only the rate and dividend
    share are set, exactly like harvest_rerun.py does."""
    params = run.state.rulesets[0]["params"]
    params.setdefault("wealth_tax", {})["rate_bp"] = 400
    params.setdefault("surplus_spending", {})["dividend_share_bp"] = 3000


def unmet_essentials(state):
    return sum(
        1 for un in state.unmet_needs.values()
        if any(un.get(g) for g in ESSENTIALS)
    )


def run_world(run, label):
    t0 = time.perf_counter()
    inv_bad = worst = streak = 0
    for t in range(run.state.tick + 1, TICKS + 1):
        drive(run, SEED, t, t)
        if money_delta(run) != 0:
            inv_bad += 1
        if unmet_essentials(run.state) > 0:
            streak += 1
            worst = max(worst, streak)
        else:
            streak = 0
        if t % 50 == 0:
            _h = holders(run.state)
            _frac = [v for v in _h if isinstance(v, float) and not v.is_integer()]
            _top1 = int(top1_share_bp(_h))
            if _frac:
                print(f"{label} t={t} WARNING {len(_frac)} fractional wealth vals, e.g. {_frac[:3]}", flush=True)
            print(
                f"{label} t={t} top1_bp={_top1:5d} "
                f"unmet={unmet_essentials(run.state):3d} inv_bad={inv_bad}",
                flush=True,
            )
    wall = time.perf_counter() - t0
    result = {
        "label": label,
        "ticks": TICKS,
        "top1_bp_end": int(top1_share_bp(holders(run.state))),
        "worst_streak": worst,
        "inv_bad": inv_bad,
        "wall_s": round(wall, 1),
    }
    print(f"RESULT {result}", flush=True)
    return result


def main():
    from server import Run

    # 1:1 world with the winning policy (reference = harvest conditions)
    run_full = Run(seed=SEED)
    scale_world(run_full, 1000)
    apply_winning_policy(run_full)
    r_full = run_world(run_full, "full_986")

    # cohort surrogate with the same per-capita policy
    run_coh = Run(seed=SEED)
    scale_world(run_coh, 1000)
    params = run_coh.state.rulesets[0]["params"]
    if "labor_pool_cap" in params:
        params["labor_pool_cap"] = int(params["labor_pool_cap"] * K)
    params["cohort_k"] = K
    apply_winning_policy(run_coh)
    r_coh = run_world(run_coh, "cohort_k100")

    delta = r_coh["top1_bp_end"] - r_full["top1_bp_end"]
    print(
        f"FIDELITY top1_delta_bp={delta} "
        f"full={r_full['top1_bp_end']} cohort={r_coh['top1_bp_end']} "
        f"worst_streak full/cohort={r_full['worst_streak']}/{r_coh['worst_streak']}"
    )


if __name__ == "__main__":
    main()