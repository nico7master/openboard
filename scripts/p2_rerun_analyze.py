#!/usr/bin/env python
"""P2 re-run analysis: 2026-09-12 verdicts vs today's engine (RC1 wk-3).

Within-seed old-vs-new deltas per arm + verdict re-check. Read-only.
"""
import json
from pathlib import Path

ROOT = Path("/a0/usr/projects/openboard-economy")
OLD = ROOT / "sweeps" / "p2"
NEW = ROOT / "sweeps" / "p2_rerun"
ARMS = ("skills_off", "skills_on", "vote_plain", "vote_bad",
        "crisis_off", "crisis_on")
SEEDS = (42, 7, 123)


def load(d, arm, seed):
    f = d / f"{arm}_s{seed}.json"
    return json.loads(f.read_text()) if f.exists() else None


def metrics(doc):
    fin = doc.get("final", {})
    return {
        "pop": fin.get("pop"),
        "deaths": fin.get("deaths_total"),
        "gini": fin.get("gini"),
        "unmet": fin.get("unmet"),
        "tax_events": fin.get("tax_events"),
        "tax_units": fin.get("tax_units_total"),
        "crisis_ticks": fin.get("crisis_ticks"),
        "produced": fin.get("produced_total"),
        "money_ok": fin.get("money_ok"),
        "machines": (fin.get("inventory") or {}).get("machines"),
    }


def main():
    missing = []
    rows = []
    for arm in ARMS:
        for seed in SEEDS:
            o, n = load(OLD, arm, seed), load(NEW, arm, seed)
            if not (o and n):
                missing.append(f"{arm}_s{seed}")
                continue
            om, nm = metrics(o), metrics(n)
            rows.append({"arm": arm, "seed": seed,
                         "old": om, "new": nm,
                         "d_gini": (nm["gini"] or 0) - (om["gini"] or 0),
                         "d_produced": (nm["produced"] or 0) - (om["produced"] or 0),
                         "d_machines": (nm["machines"] or 0) - (om["machines"] or 0)})
    print(json.dumps({"missing": missing, "combos": len(rows), "rows": rows},
                     indent=1))


if __name__ == "__main__":
    main()
