#!/usr/bin/env python3
"""P3 analysis: paired hidden-system comparisons.

Inputs:  sweeps/p3/{disaster,disaster_spoil,disaster_memory,disaster_wear}_s{7,42,123}.json
Control: sweeps/p2/skills_off_s{seed}.json      (healthy world, no shocks)
Cross-check: sweeps/p2/crisis_off_s{seed}.json  (same harsh shocks, default rng)

Prints a verdict-oriented report; numbers only — narrative lives in FINDINGS.md.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
P3 = ROOT / "sweeps" / "p3"
P2 = ROOT / "sweeps" / "p2"

ARMS = ("disaster", "disaster_spoil", "disaster_memory", "disaster_wear",
        "disaster_nowear")
SEEDS = (7, 42, 123)


def load(p: Path):
    try:
        return json.loads(p.read_text())
    except FileNotFoundError:
        return None


def machines_of(r: dict):
    f = r.get("final", {})
    if "machines" in f:
        return f["machines"]
    inv = f.get("inventory") or {}
    if "machines" in inv:
        return inv["machines"]
    s = r.get("series") or []
    return s[-1][7] if s and len(s[-1]) > 7 else None


def late_foundings(r: dict):
    return [fc for fc in r.get("found_coops", []) if fc.get("tick", 0) > 2]


def row(r: dict):
    f = r["final"]
    return {
        "unmet": f["unmet"],
        "gini": f["gini"],
        "machines": machines_of(r),
        "produced": f["produced_total"],
        "spoil": f.get("spoil_total", 0),
        "found_late": len(late_foundings(r)),
        "pop": f["pop"],
        "money_ok": r.get("money_ok"),
    }


def mean(vals):
    vals = [v for v in vals if v is not None]
    return sum(vals) / len(vals) if vals else None


def main():
    data = {(a, s): load(P3 / f"{a}_s{s}.json") for a in ARMS for s in SEEDS}
    ctrl = {s: load(P2 / f"skills_off_s{s}.json") for s in SEEDS}
    p2shock = {s: load(P2 / f"crisis_off_s{s}.json") for s in SEEDS}

    missing = [k for k, v in data.items() if v is None]
    print(f"dataset: {len(data) - len(missing)}/12 P3 runs"
          + (f"  MISSING: {missing}" if missing else ""))

    # -- determinism cross-check: P3 disaster vs P2 crisis_off -------------
    print("\n== determinism: P3 disaster vs P2 crisis_off (same seeds, default shock rng) ==")
    for s in SEEDS:
        a, b = data.get(("disaster", s)), p2shock.get(s)
        if not (a and b):
            print(f"  seed {s}: n/a")
            continue
        keys = ("pop", "unmet", "pool_units", "gini", "produced_total", "deaths_total")
        same = all(a["final"].get(k) == b["final"].get(k) for k in keys)
        print(f"  seed {s}: {'IDENTICAL' if same else 'DIFFERS'}"
              f" (p3 unmet={a['final']['unmet']} gini={a['final']['gini']}"
              f" | p2 unmet={b['final']['unmet']} gini={b['final']['gini']})")

    # -- paired-design check: identical shock streams across arms ----------
    print("\n== paired design: shock streams aligned across arms per seed ==")
    for s in SEEDS:
        refs = [data.get((a, s)) for a in ARMS]
        refs = [r for r in refs if r]
        if len(refs) < 2:
            continue
        base = json.dumps(refs[0]["shocks"], sort_keys=True)
        ok = all(json.dumps(r["shocks"], sort_keys=True) == base for r in refs)
        kinds = refs[0]["shocks"]["counts"]
        first = refs[0]["shocks"]["first_tick"]
        print(f"  seed {s}: {'ALIGNED' if ok else 'MISALIGNED'}  counts={kinds}  first={first}")

    # -- main table ---------------------------------------------------------
    print("\n== results per run ==")
    hdr = (f"{'arm':16s} {'seed':>4s} {'unmet':>6s} {'gini':>6s} "
           f"{'machines':>9s} {'produced':>9s} {'spoil':>9s} "
           f"{'found_late':>10s} {'pop':>5s} {'money_ok':>8s}")
    print(hdr)
    for arm in ("control(p2)",) + ARMS:
        for s in SEEDS:
            r = ctrl.get(s) if arm == "control(p2)" else data.get((arm, s))
            if not r:
                continue
            w = row(r)
            found_s = str(w["found_late"]) if arm != "control(p2)" else "n/a"
            print(f"{arm:16s} {s:4d} {w['unmet']:6d} {w['gini']:6d} "
                  f"{str(w['machines']):>9s} {w['produced']:9d} {w['spoil']:9d} "
                  f"{found_s:>10s} {w['pop']:5d} {str(w['money_ok']):>8s}")

    # -- arm means and paired deltas vs disaster ----------------------------
    print("\n== arm means (across seeds) and paired deltas vs disaster ==")

    def arm_stats(arm, source):
        rows = [row(r) for r in (source.get((arm, s)) if source is data else source.get(s)
                                 for s in SEEDS) if r]
        return {k: mean([r[k] for r in rows]) for k in
                ("unmet", "gini", "machines", "produced", "spoil", "found_late")}

    stats = {a: arm_stats(a, data) for a in ARMS}
    for arm in ("control(p2)",) + ARMS:
        st = arm_stats(arm, ctrl if arm == "control(p2)" else data)
        pretty = {k: (round(v, 1) if v is not None else "n/a") for k, v in st.items()}
        print(f"  {arm:16s} {pretty}")

    for arm in ARMS[1:]:
        for s in SEEDS:
            a, b = data.get((arm, s)), data.get(("disaster", s))
            if not (a and b):
                continue
            wa, wb = row(a), row(b)
            dm = (wa["machines"] - wb["machines"]
                  if wa["machines"] is not None and wb["machines"] is not None else "n/a")
            print(f"  {arm:16s} s{s}: d_unmet={wa['unmet'] - wb['unmet']:+d} "
                  f"d_machines={dm} d_produced={wa['produced'] - wb['produced']:+d} "
                  f"d_spoil={wa['spoil'] - wb['spoil']:+d}")

    # -- unmet trajectory (cascade vs recovery) -----------------------------
    print("\n== unmet trajectory (every 10th sample; col idx 3) ==")
    for arm in ("control(p2)",) + ARMS:
        for s in SEEDS:
            r = ctrl.get(s) if arm == "control(p2)" else data.get((arm, s))
            if not r:
                continue
            ser = r["series"]
            pts = [f"t{e[0]}:{e[3]}" for e in ser[::10]]
            print(f"  {arm:16s} s{s}: " + " ".join(pts))

    # -- emergent foundings (tick > 2, excluding genesis co-ops) ------------
    print("\n== emergent foundings (tick>2) ==")
    any_late = False
    for arm in ARMS:
        for s in SEEDS:
            r = data.get((arm, s))
            if not r:
                continue
            lf = late_foundings(r)
            if not lf:
                continue
            any_late = True
            recipes = {}
            for fc in lf:
                rid = fc.get("recipe_id") or fc.get("recipe") or "?"
                recipes[rid] = recipes.get(rid, 0) + 1
            ticks = sorted({fc["tick"] for fc in lf})
            print(f"  {arm} s{s}: {len(lf)} foundings  recipes={recipes}  "
                  f"ticks={ticks[:10]}{'...' if len(ticks) > 10 else ''}")
    if not any_late:
        print("  (none — entrepreneur bots never triggered outside genesis)")


if __name__ == "__main__":
    main()
