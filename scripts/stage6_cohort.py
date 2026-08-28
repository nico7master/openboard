#!/usr/bin/env python
"""Stage 6 WP7: cohort scaling - 1k agents x K=100 = 100,000 people.

Each simulated citizen/coop represents K real people. Needs, labor and
production are per-agent, so a verified 986-agent world represents
K x 986 people with identical dynamics PROVIDED every absolute-
denominator rule param is scaled by K (per-capita params need no
change). Runs the standard stability window and reports verdict.

Usage: stage6_cohort.py [K] [seed] [ticks]   (default: 100 42 500)
"""
import json
import resource
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "dashboard"))
sys.path.insert(0, str(ROOT / "scripts"))

from stage6_scale_gate import (  # noqa: E402
    ESSENTIALS, TARGET_CITIZENS, drive, money_delta, scale_world, trim_retention,
)


def unmet_essentials(state):
    return sum(
        1 for un in state.unmet_needs.values()
        if any(un.get(g) for g in ESSENTIALS)
    )


def cohort_run(seed, K):
    from server import Run

    run = Run(seed=seed)
    scale_world(run, TARGET_CITIZENS)
    params = run.state.rulesets[0]["params"]
    # absolute-denominator params scale with the represented population
    if "labor_pool_cap" in params:
        params["labor_pool_cap"] = int(params["labor_pool_cap"] * K)
    params["cohort_k"] = K
    return run


def run_cohort(K, seed, ticks):
    t0 = time.perf_counter()
    run = cohort_run(seed, K)
    inv_bad = streak = worst = 0
    for t in range(run.state.tick + 1, ticks + 1):
        drive(run, seed, t, t)
        if money_delta(run) != 0:
            inv_bad += 1
        if unmet_essentials(run.state) > 0:
            streak += 1
            worst = max(worst, streak)
        else:
            streak = 0
        if t % 50 == 0:
            trim_retention(run)
    wall = time.perf_counter() - t0
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024
    agents = len(run.state.balances)
    res = {
        "cohort_k": K, "seed": seed, "ticks": ticks,
        "agents": agents,
        "represented_people": agents * K,
        "worst_streak": worst, "inv_bad": inv_bad,
        "wall_s": round(wall, 1), "rss_mb": rss,
        "verdict": "stable" if (inv_bad == 0 and worst <= 50) else "unstable",
    }
    out = ROOT / "sweeps" / f"cohort_k{K}_s{seed}.json"
    out.write_text(json.dumps(res, indent=2, sort_keys=True))
    print(json.dumps(res), flush=True)
    return res


def main():
    K = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 42
    ticks = int(sys.argv[3]) if len(sys.argv) > 3 else 500
    res = run_cohort(K, seed, ticks)
    ok = res["verdict"] == "stable" and res["inv_bad"] == 0
    print(f"COHORT GATE: {'PASS' if ok else 'FAIL'} "
          f"({res['agents']} agents x K={K} = {res['represented_people']} people)")


if __name__ == "__main__":
    main()
