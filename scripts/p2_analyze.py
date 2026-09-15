#!/usr/bin/env python
"""Analyze Priority 2 results (sweeps/p2/*.json).

All comparisons are WITHIN-SEED (chaos rule, FINDINGS.md): single-run
cross-seed deltas are noise at 1000 citizens.

  Q1 Skills:   skills_on vs skills_off  -> production, unmet, machines
  Q2 Voting:   vote_bad  vs vote_plain  -> unmet, production, inequality
               (also: did the referendum pass, and did the tax collect?)
  Q3 Crisis:   crisis_on vs crisis_off  -> deaths, unmet (override vs
               laissez-faire under identical harsh shocks)
"""
import json
import sys
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parents[1] / "sweeps" / "p2"
SEEDS = (7, 42, 123)
ARMS = {
    "skills": ("skills_off", "skills_on"),
    "voting": ("vote_plain", "vote_bad"),
    "crisis": ("crisis_off", "crisis_on"),
}


def load(arm, seed):
    f = OUT_DIR / f"{arm}_s{seed}.json"
    if not f.exists():
        return None
    return json.loads(f.read_text())


def _fmt(v):
    return "-" if v is None else f"{v}"


def main():
    rows = []
    for seed in SEEDS:
        base = {}
        for pair, (ctl, trt) in ARMS.items():
            c, t = load(ctl, seed), load(trt, seed)
            if c is None or t is None:
                continue
            cf, tf = c["final"], t["final"]
            rows.append({
                "pair": pair, "seed": seed,
                "ctl": cf, "trt": tf,
                "d_unmet": tf["unmet"] - cf["unmet"],
                "d_prod": tf["produced_total"] - cf["produced_total"],
                "d_gini": tf["gini"] - cf["gini"],
                "d_deaths": tf["deaths_total"] - cf["deaths_total"],
                "d_mach": (tf["inventory"].get("machines", 0)
                           + tf["inventory"].get("hand_tools", 0)
                           - cf["inventory"].get("machines", 0)
                           - cf["inventory"].get("hand_tools", 0)),
            })

    if not rows:
        print("no paired results yet")
        return

    print(f"{'Q':<7} {'seed':<5} {'ctl unmet':>9} {'trt unmet':>9} {'d':>6} "
          f"{'ctl prod':>9} {'trt prod':>9} {'d':>7} {'ctl gini':>8} {'d_gini':>7} "
          f"{'deaths c/t':>10} {'machines d':>10}")
    print("-" * 105)
    for r in rows:
        cf, tf = r["ctl"], r["trt"]
        print(f"{r['pair']:<7} {r['seed']:<5} {cf['unmet']:>9} {tf['unmet']:>9} "
              f"{r['d_unmet']:>+6} {cf['produced_total']:>9} {tf['produced_total']:>9} "
              f"{r['d_prod']:>+7} {cf['gini']:>8} {r['d_gini']:>+7} "
              f"{cf['deaths_total']}/{tf['deaths_total']:>6} {r['d_mach']:>+10}")

    print("\nVOTING detail (did the bad referendum pass & collect?):")
    for seed in SEEDS:
        v = load("vote_bad", seed)
        if v:
            f = v["final"]
            print(f"  s{seed}: proposals={v['proposals']} "
                  f"tax_events={f['tax_events']} tax_units={f['tax_units_total']} "
                  f"money_ok={f['money_ok']}")

    print("\nCRISIS detail (override exposure):")
    for seed in SEEDS:
        v = load("crisis_on", seed)
        if v:
            print(f"  s{seed}: crisis_ticks={v['final']['crisis_ticks']} "
                  f"state_active={v['crisis_state'].get('active')} "
                  f"ratified={v['crisis_state'].get('ratified')}")

    print("\nSKILLS detail (machine stock trajectory, seed 42):")
    for arm in ("skills_off", "skills_on"):
        v = load(arm, 42)
        if v:
            mach = [(row[0], row[7]) for row in v["series"] if row[0] in (50, 200, 400, 650)]
            print(f"  {arm:<11} machines@t: " + ", ".join(f"t{t}={m}" for t, m in mach))

    print("\nVERDICTS (within-seed, majority of seeds):")
    for pair in ARMS:
        rs = [r for r in rows if r["pair"] == pair]
        if not rs:
            continue
        worse_unmet = sum(1 for r in rs if r["d_unmet"] > 0)
        less_prod = sum(1 for r in rs if r["d_prod"] < 0)
        fewer_deaths = sum(1 for r in rs if r["d_deaths"] < 0)
        print(f"  {pair}: unmet worse in {worse_unmet}/{len(rs)} seeds, "
              f"production lower in {less_prod}/{len(rs)}, "
              f"deaths reduced in {fewer_deaths}/{len(rs)}")


if __name__ == "__main__":
    sys.exit(main())
