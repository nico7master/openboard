#!/usr/bin/env python
"""Stage 6 WP6: escalating shock battery at ~1k citizens.

Battery (mild->fatal) on the scaled world x seeds. Criteria: money
invariant exact every tick; essentials recover <= 100 ticks post-shock
(no streak > 100); honest breaking-tier report.

Usage: stage6_shock_scale.py [seed...]   (default: 42 7)
"""
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

TIER_NAMES = ["mild", "moderate", "severe", "extreme", "fatal"]


def unmet_essentials(state):
    return sum(
        1 for un in state.unmet_needs.values()
        if any(un.get(g) for g in ESSENTIALS)
    )


def scaled_shock_run(seed):
    from server import Run

    run = Run(seed=seed)
    scale_world(run, TARGET_CITIZENS)
    run.state.rulesets[0]["params"]["shocks"] = {"enabled": True, "profile": "battery"}
    run.state.rulesets[0]["params"]["crisis"] = {"enabled": True}
    return run


def battery_seed(seed, base_ticks=302, shock_ticks=1750):
    t0 = time.perf_counter()
    run = scaled_shock_run(seed)
    drive(run, seed, 2, base_ticks)  # healthy baseline at scale
    inv_bad = streak = worst = 0
    for t in range(base_ticks + 1, base_ticks + 1 + shock_ticks):
        drive(run, seed, t, t)
        if unmet_essentials(run.state) > 0:
            streak += 1
            worst = max(worst, streak)
        else:
            streak = 0
        if money_delta(run) != 0:
            inv_bad += 1
        if t % 50 == 0:
            trim_retention(run)
    wall = time.perf_counter() - t0
    tier = min(4, shock_ticks // 250)
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024
    ok = inv_bad == 0 and worst <= 100
    print(
        f"  seed {seed}: worst_streak={worst} inv_bad={inv_bad} "
        f"wall={wall:.0f}s rss={rss}MB (battery through tier '{TIER_NAMES[tier]}') "
        f"-> {'OK' if ok else 'BREAK-REPORT'}",
        flush=True,
    )
    return ok


def main():
    seeds = [int(x) for x in sys.argv[1:]] or [42, 7]
    print(f"Stage 6 shock battery at scale: {len(seeds)} seeds, target {TARGET_CITIZENS} citizens", flush=True)
    ok = all(battery_seed(s) for s in seeds)
    print(f"GATE: {'PASS' if ok else 'BREAK-REPORT'}")


if __name__ == "__main__":
    main()
