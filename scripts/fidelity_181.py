#!/usr/bin/env python
"""Reduced-agent fidelity: 181-citizen unequal world vs 986-citizen harvest.

The REAL billions-ladder rung (doctrine correction 2026-09-08): the
existing cohort K world is denomination scaling only (same agents, K
label) — delta vs the 1:1 world is trivially 0. A surrogate claim needs
fewer AGENTS under the same per-capita law.

This probe runs the DEFAULT 181-citizen unequal world under the exact
winning policy (wealth tax 400bp, dividend share 3000bp, threshold
untouched — already upc-scaled) for the harvest's 1500-tick window and
compares the normalized top-1 share trajectory against the banked
986-citizen harvest run (sweeps/unequal_rerun/tax0400_div3000_s42.json).

Usage: python scripts/fidelity_181.py [ticks] [seed]
"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "dashboard"))
sys.path.insert(0, str(ROOT / "scripts"))

from openboard.metrics import top1_share_bp  # noqa: E402
from harvest_rerun import holders  # noqa: E402
from stage6_scale_gate import ESSENTIALS, drive, money_delta  # noqa: E402

TICKS = int(sys.argv[1]) if len(sys.argv) > 1 else 1500
SEED = int(sys.argv[2]) if len(sys.argv) > 2 else 42


def apply_winning_policy(run):
    """In-place mutation, fork rule; threshold NEVER touched (upc-scaled)."""
    params = run.state.rulesets[0]["params"]
    params.setdefault("wealth_tax", {})["rate_bp"] = 400
    params.setdefault("surplus_spending", {})["dividend_share_bp"] = 3000


def unmet_essentials(state):
    return sum(
        1 for un in state.unmet_needs.values()
        if any(un.get(g) for g in ESSENTIALS)
    )


def main():
    from server import Run

    run = Run(seed=SEED, scenario="unequal")
    pop = len(run.state.balances)
    apply_winning_policy(run)

    series = []
    inv_bad = worst = streak = 0
    t0 = time.perf_counter()
    for t in range(run.state.tick + 1, TICKS + 1):
        drive(run, SEED, t, t)
        if money_delta(run) != 0:
            inv_bad += 1
        if unmet_essentials(run.state) > 0:
            streak += 1
            worst = max(worst, streak)
        else:
            streak = 0
        if t % 10 == 0:
            series.append([t, int(top1_share_bp(holders(run.state)))])
        if t % 300 == 0:
            print(f"t={t} top1_bp={series[-1][1]:5d} unmet_now={unmet_essentials(run.state):3d} inv_bad={inv_bad}", flush=True)
    wall = time.perf_counter() - t0

    out = {
        "label": "reduced_181",
        "citizens": pop,
        "seed": SEED,
        "ticks": TICKS,
        "policy": "tax0400_div3000",
        "top1_series": series,
        "final_top1_bp": series[-1][1] if series else None,
        "worst_streak": worst,
        "inv_bad": inv_bad,
        "wall_s": round(wall, 1),
    }
    dest = ROOT / "sweeps" / "fidelity_181_tax0400_div3000_s42.json"
    dest.write_text(json.dumps(out, indent=1))
    print(f"SAVED {dest}")
    print(f"RESULT {json.dumps({k: v for k, v in out.items() if k != 'top1_series'})}")


if __name__ == "__main__":
    main()