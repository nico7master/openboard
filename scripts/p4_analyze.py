#!/usr/bin/env python3
"""P4 analyzer: pair combination arms against their reference corners.

Pairs (same seed):
  trade_only      vs sweeps/p2/skills_off_{seed}.json      (P2 control)
  land_trade      vs sweeps/land_study/dump_{seed}.json    (P1 dump)
  disaster_trade  vs sweeps/p3/disaster_{seed}.json        (P3 disaster)
  all_on          vs disaster_trade (same-run family)

Reports per-seed deltas (unmet, pool, produced, gini), trade volumes,
land activity, drought-window unmet (t>=533 from series), and the
extended conservation check money_delta + d_foreign + d_research == 0.

Usage: p4_analyze.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
P4 = ROOT / "sweeps" / "p4"
SEEDS = (7, 42, 123)
ARMS = ("trade_only", "land_trade", "disaster_trade", "all_on")

REF = {
    "trade_only": ROOT / "sweeps/p2/skills_off_s{seed}.json",
    "land_trade": ROOT / "sweeps/land_study/dump_s{seed}.json",
    "disaster_trade": ROOT / "sweeps/p3/disaster_s{seed}.json",
    # all_on pairs against its own family's disaster_trade run
    "all_on": P4 / "disaster_trade_s{seed}.json",
}
DROUGHT_TICK = 533


def load(p: Path):
    return json.loads(p.read_text()) if p.exists() else None


def final_g(d: dict) -> dict:
    """Normalize the three corner schemas into one view."""
    f = d.get("final", {})
    return {
        "pop": f.get("pop"),
        "unmet": f.get("unmet"),
        "pool": f.get("pool_units"),
        "gini": f.get("gini"),
        "produced": f.get("produced", f.get("produced_total", 0)),
    }


def drought_unmet(d: dict) -> int:
    """Max unmet in the series after the drought tick.

    Layouts differ: land_study series rows are 7-wide WITHOUT a pop
    column ([t, gini, unmet, pool, ...]); every other probe is 8-10
    wide with pop second ([t, pop, gini, unmet, ...]).
    """
    worst = 0
    for row in d.get("series", []):
        idx = 2 if len(row) <= 7 else 3
        if row[0] >= DROUGHT_TICK:
            worst = max(worst, row[idx])
    return worst


def main() -> int:
    rows = []
    missing = []
    for arm in ARMS:
        for seed in SEEDS:
            d = load(P4 / f"{arm}_s{seed}.json")
            if d is None:
                missing.append(f"{arm}_s{seed}")
                continue
            cons = (d["money_delta"] + d["d_foreign"]
                    + d.get("d_research", 0)) == 0
            row = {
                "arm": arm, "seed": seed,
                "wall_s": d.get("wall_s"),
                "cons_ok": cons,
                "money_delta": d["money_delta"],
                "d_foreign": d["d_foreign"],
                "d_research": d.get("d_research", 0),
                "trade": d.get("trade", {}),
                "land": d.get("land", {}),
                "final": final_g(d),
                "drought_unmet": drought_unmet(d),
            }
            ref_path = REF.get(arm)
            if ref_path:
                ref = load(Path(str(ref_path).format(seed=seed)))
                if ref:
                    rf = final_g(ref)
                    row["ref"] = {
                        "name": ref_path.name,
                        **rf,
                        "drought_unmet": drought_unmet(ref),
                    }
            rows.append(row)

    if missing:
        print(f"MISSING {len(missing)}: {', '.join(missing)}")

    out = P4 / "ANALYSIS.json"
    out.write_text(json.dumps(rows, indent=2, sort_keys=True))

    # readable verdict table
    print(f"{'arm':<15}{'s':<5}{'cons':<6}{'unmet':<7}{'dUnmet':<8}"
          f"{'droughtU':<9}{'pool':<13}{'dPool%':<8}{'gini':<6}{'dGini':<7}"
          f"{'imp_u':<8}{'exp_u':<8}{'tariff':<8}{'lvt':<8}{'sold_u':<10}")
    for r in rows:
        f, rf = r["final"], r.get("ref")
        d_unmet = (f["unmet"] - rf["unmet"]) if rf else ""
        d_pool = (100 * (f["pool"] - rf["pool"]) / max(1, rf["pool"])
                  if rf else "")
        d_pool_s = f"{d_pool:<8.2f}" if isinstance(d_pool, float) else f"{d_pool:<8}"
        d_gini = (f["gini"] - rf["gini"]) if rf else ""
        dr = rf["drought_unmet"] if rf else ""
        t, l = r["trade"], r["land"]
        print(f"{r['arm']:<15}{r['seed']:<5}"
              f"{'OK' if r['cons_ok'] else 'FAIL':<6}"
              f"{f['unmet']:<7}{d_unmet:<8}"
              f"{r['drought_unmet']}/{dr:<4}"
              f"{f['pool']:<13}{d_pool_s}"
              f"{f['gini']:<6}{d_gini:<7}"
              f"{t.get('import_units', 0):<8}{t.get('export_units', 0):<8}"
              f"{t.get('tariff_units', 0):<8}"
              f"{l.get('lvt_units', 0):<8}{l.get('sold_units', 0):<10}")
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
