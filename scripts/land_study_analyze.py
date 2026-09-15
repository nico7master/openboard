#!/usr/bin/env python
"""Analyze land study results (sweeps/land_study/*.json).

Answers the STUDY_PLAN Priority-1 questions:
- Does one person owning all land starve others? (unmet + gini vs control)
- Does the Georgist LVT self-defend? (foreclosure cascade, mono balance)
- How big is the dump drain on the Society Pool? (sell_units vs pool)
"""
import json
import sys
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parents[1] / "sweeps" / "land_study"
SCENARIOS = ("control", "hold", "dump")
SEEDS = (7, 42, 123)


def load(scenario, seed):
    f = OUT_DIR / f"{scenario}_s{seed}.json"
    if not f.exists():
        return None
    return json.loads(f.read_text())


def main():
    rows = []
    for seed in SEEDS:
        ctrl = load("control", seed)
        for sc in SCENARIOS:
            r = load(sc, seed)
            if r is None:
                continue
            final = r["final"]
            agg = r["agg"]
            base_gini = ctrl["final"]["gini"] if ctrl else 0
            base_unmet = ctrl["final"]["unmet"] if ctrl else 0
            base_pool = ctrl["final"]["pool_units"] if ctrl else 0
            rows.append({
                "seed": seed,
                "scenario": sc,
                "gini": final["gini"],
                "gini_vs_ctrl": final["gini"] - base_gini,
                "unmet": final["unmet"],
                "unmet_vs_ctrl": final["unmet"] - base_unmet,
                "worst_streak": r["worst_unmet_streak"],
                "pool": final["pool_units"],
                "pool_drain_vs_ctrl": base_pool - final["pool_units"],
                "mono_left": final["mono_units"],
                "priv_parcels": final["priv_parcels"],
                "lvt_paid": agg["lvt_units"],
                "foreclosures": agg["foreclosures"],
                "sells": agg["sell_n"],
                "sell_units": agg["sell_units"],
                "inv_bad": r["inv_bad"],
                "pop": final["pop"],
            })

    if not rows:
        print("no results yet")
        return

    hdr = ("seed", "scen", "gini(+d)", "unmet(+d)", "streak", "pool_drain",
           "mono_left", "priv", "LVT", "forecl", "sells", "inv_bad")
    print(" | ".join(hdr))
    print("-" * 100)
    for r in rows:
        print(" | ".join(str(x) for x in (
            r["seed"], r["scenario"][:7],
            f"{r['gini']}({r['gini_vs_ctrl']:+})",
            f"{r['unmet']}({r['unmet_vs_ctrl']:+})",
            r["worst_streak"], r["pool_drain_vs_ctrl"],
            r["mono_left"], r["priv_parcels"], r["lvt_paid"],
            r["foreclosures"], r["sells"], r["inv_bad"],
        )))

    # foreclosure timing from hold series (mono balance trajectory)
    print("\nHOLD monopolist trajectory (seed 42): t, mono_balance, priv_parcels")
    h = load("hold", 42)
    if h:
        for row in h["series"]:
            print(f"  t={row[0]:4d} mono={row[4]:>9d} priv={row[5]}")

    # verdict per study question
    print("\nVERDICTS:")
    holds = [r for r in rows if r["scenario"] == "hold"]
    dumps = [r for r in rows if r["scenario"] == "dump"]
    ctrls = [r for r in rows if r["scenario"] == "control"]
    if holds and ctrls:
        starve = max(r["unmet"] - c["unmet"] for r, c in zip(holds, ctrls))
        gini_d = max(r["gini"] - c["gini"] for r, c in zip(holds, ctrls))
        forecl = sum(r["foreclosures"] for r in holds)
        print(f"- Q1 hold starves anyone: {'YES' if starve > 0 else 'NO'} (max unmet delta {starve}, max gini delta {gini_d:+})")
        print(f"- Q2 Georgist LVT recaptures: {forecl} foreclosures across holds")
    if dumps and ctrls:
        drain = max(r["pool_drain_vs_ctrl"] for r in dumps)
        pools = [c["pool"] for c in ctrls]
        if pools and drain:
            print(f"- Q3 dump pool drain: {drain} units (max {drain / max(pools) * 100:.2f}% of control pool)")


if __name__ == "__main__":
    sys.exit(main())
