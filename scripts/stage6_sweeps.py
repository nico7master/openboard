#!/usr/bin/env python
"""Stage 6 WP3/WP4: parameter sweep harness on the scaled world.

Sweeps votable rule knobs over grids x seeds at the ~1k-citizen scale,
sequentially, resumable (one JSON per combo under sweeps/). Verdict per
combo: invariant exact, essentials streak <= bound, unmet-needs trend.

Usage:
  stage6_sweeps.py run COARSE        # 5 knobs x 3 values x 3 seeds x 500 ticks
  stage6_sweeps.py CLIFF <knob>      # fine sweep (7 values x 5 seeds x 1500)
  stage6_sweeps.py status            # progress overview
"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "dashboard"))
sys.path.insert(0, str(ROOT / "scripts"))

from server import Run  # noqa: E402
from stage6_scale_gate import (  # noqa: E402
    ESSENTIALS, TARGET_CITIZENS, drive, scale_world, trim_retention,
)

SWEEPS_DIR = ROOT / "sweeps"

KNOBS = {
    "wealth_tax.rate_bp": [200, 400, 800],
    "surplus_spending.dividend_share_bp": [3000, 5000, 7000],
    "surplus_spending.services_share_bp": [3000, 5000, 7000],
    "labor_pool_cap": [2000, 4000, 8000],
    "capital_backstop.interval_ticks": [5, 10, 20],
}

CLIFF_GRID = {
    "wealth_tax.rate_bp": [100, 150, 200, 300, 400, 600, 800],
    "surplus_spending.dividend_share_bp": [1000, 2000, 3000, 4000, 5000, 7000, 9000],
}


def override_run(seed, overrides):
    """Run with ruleset-param overrides applied from genesis."""
    class ORun(Run):
        def _params(self):
            p = super()._params()
            for path, val in overrides.items():
                if "." in path:
                    head, key = path.split(".", 1)
                    p.setdefault(head, {})[key] = val
                else:
                    p[path] = val
            return p

    return ORun(seed=seed)


def money_delta(run):
    s = run.state
    total = (sum(s.balances.values()) + s.surplus_pool + s.capital_fund
             + getattr(s, "innovation_pool", 0)
             + sum(c.get("treasury", 0) for c in s.coops.values()))
    if not hasattr(run, "_money0"):
        run._money0 = total - s.money_minted + s.money_retired
    return total - (run._money0 + s.money_minted - s.money_retired)


def run_combo(knob, value, seed, ticks, streak_bound=30):
    out = SWEEPS_DIR / f"{knob.replace('.', '__')}_{value}_s{seed}.json"
    if out.exists():
        return json.loads(out.read_text())  # resumable
    t0 = time.perf_counter()
    run = override_run(seed, {knob: value})
    scale_world(run, TARGET_CITIZENS)
    inv_bad = 0
    streak = worst = 0
    unmet_series = []
    for t in range(run.state.tick + 1, ticks + 1):
        drive(run, seed, t, t)
        s = run.state
        if money_delta(run) != 0:
            inv_bad += 1
        unmet = sum(1 for un in s.unmet_needs.values()
                    if any(un.get(g) for g in ESSENTIALS))
        unmet_series.append(unmet)
        if unmet > 0:
            streak += 1
            worst = max(worst, streak)
        else:
            streak = 0
        if t % 50 == 0:
            trim_retention(run)
    wall = time.perf_counter() - t0
    tail = unmet_series[-max(1, ticks // 5):]
    n = len(tail)
    xs = list(range(n))
    mx, my = sum(xs) / n, sum(tail) / n
    denom = sum((x - mx) ** 2 for x in xs) or 1
    trend = sum((x - mx) * (y - my) for x, y in zip(xs, tail)) / denom
    res = {
        "knob": knob, "value": value, "seed": seed, "ticks": ticks,
        "wall_s": round(wall, 1), "inv_bad": inv_bad,
        "worst_streak": worst, "mean_unmet_tail": round(my, 2),
        "trend": round(trend, 3), "pop": len(run.state.balances),
    }
    res["verdict"] = ("stable" if (inv_bad == 0 and worst <= streak_bound
                                   and trend <= 0.05) else "unstable")
    SWEEPS_DIR.mkdir(exist_ok=True)
    out.write_text(json.dumps(res, indent=2, sort_keys=True))
    return res


def cmd_coarse():
    results = []
    for knob, grid in KNOBS.items():
        for value in grid:
            for seed in (7, 42, 123):
                r = run_combo(knob, value, seed, 500)
                print(json.dumps(r), flush=True)
                results.append(r)
    stable = sum(1 for r in results if r["verdict"] == "stable")
    print(f"COARSE: {stable}/{len(results)} stable")


def cmd_cliff(knob):
    for value in CLIFF_GRID[knob]:
        for seed in (7, 42, 123, 5, 99):
            r = run_combo(knob, value, seed, 1500)
            print(json.dumps(r), flush=True)


def cmd_status():
    files = sorted(SWEEPS_DIR.glob("*.json")) if SWEEPS_DIR.exists() else []
    done = [json.loads(f.read_text()) for f in files]
    stable = sum(1 for r in done if r["verdict"] == "stable")
    print(f"{len(done)} combos done, {stable} stable")


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] == "status":
        cmd_status()
    elif len(sys.argv) >= 3 and sys.argv[1] == "run" and sys.argv[2] == "COARSE":
        cmd_coarse()
    elif len(sys.argv) >= 3 and sys.argv[1] == "CLIFF":
        cmd_cliff(sys.argv[2])
    else:
        print(__doc__)
