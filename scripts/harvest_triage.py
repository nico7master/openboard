#!/usr/bin/env python
"""WP2.1 Step 1: triage the banked sweeps into a provisional heat-card.

The banked JSONs (sweeps/*.json) are pre-21M-cap and pre-D21g aggregates;
this tool makes them legible: one markdown heat-card + one CSV, grouped by
knob family and value, worst-case across seeds. Output is PROVISIONAL —
winning regions are shortlisted for re-validation under the current engine
(harvest_rerun.py), never treated as proof.

Usage: python scripts/harvest_triage.py
"""
import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SWEEPS = ROOT / "sweeps"

VERDICT_RANK = {"stable": 0, "degraded": 1, "unstable": 2, "failed": 3}


def parse_name(path: Path) -> tuple[str, str] | None:
    """Family + value from '<family>__<knob>_<value>_s<seed>.json' or
    '<knob>_<value>_s<seed>.json'. Returns None for files without a seed."""
    m = re.match(r"(?:(.+?)__)?(.+?)_s(\d+)\.json$", path.name)
    if not m:
        return None
    family = m.group(1) or m.group(2).rsplit("_", 1)[0]
    family = family.split("__")[0]
    value = m.group(2)
    return family, value


def main() -> int:
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    skipped = []
    for p in sorted(SWEEPS.glob("*.json")):
        parsed = parse_name(p)
        if parsed is None:
            skipped.append(p.name)
            continue
        try:
            d = json.loads(p.read_text())
        except json.JSONDecodeError:
            skipped.append(p.name)
            continue
        groups[parsed].append(d)

    rows = []
    for (family, value), runs in sorted(groups.items()):
        verdicts = [r.get("verdict", "?") for r in runs]
        worst = max(verdicts, key=lambda v: VERDICT_RANK.get(v, 99))
        unmet = [r.get("mean_unmet_tail", 0) for r in runs]
        streaks = [r.get("worst_streak", 0) for r in runs]
        inv_bad = sum(r.get("inv_bad", 0) for r in runs)
        seeds = sorted(r.get("seed") for r in runs)
        rows.append(
            {
                "family": family,
                "value": value,
                "n_seeds": len(runs),
                "seeds": ",".join(map(str, seeds)),
                "verdict_worst": worst,
                "unmet_tail_mean": round(sum(unmet) / len(unmet), 1),
                "unmet_tail_max": round(max(unmet), 1),
                "worst_streak_max": max(streaks),
                "inv_bad_total": inv_bad,
            }
        )

    # CSV
    csv_path = SWEEPS / "harvest_triage.csv"
    with csv_path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    # Markdown heat-card
    md = [
        "# Harvest triage — banked sweeps (PROVISIONAL: pre-21M-cap, pre-D21g)",
        "",
        f"{len(rows)} combos, {sum(r['n_seeds'] for r in rows)} runs. "
        "Verdict = worst across seeds. Shortlist = verdict_worst == 'stable' "
        "AND unmet_tail_max < 30 (essentials bound).",
        "",
        "| family | value | seeds | worst verdict | unmet tail mean/max | worst streak | inv_bad | shortlist |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        shortlist = (
            "YES"
            if r["verdict_worst"] == "stable" and r["unmet_tail_max"] < 30
            else ""
        )
        md.append(
            f"| {r['family']} | {r['value']} | {r['n_seeds']} "
            f"| {r['verdict_worst']} | {r['unmet_tail_mean']}/{r['unmet_tail_max']} "
            f"| {r['worst_streak_max']} | {r['inv_bad_total']} | {shortlist} |"
        )
    md_path = SWEEPS / "harvest_triage.md"
    md_path.write_text("\n".join(md) + "\n")

    n_short = sum(1 for r in rows if r["verdict_worst"] == "stable" and r["unmet_tail_max"] < 30)
    print(f"wrote {csv_path.name} and {md_path.name}: {len(rows)} combos, {n_short} shortlisted")
    if skipped:
        print(f"skipped (no seed/unreadable): {skipped}")
    for r in rows:
        if r["verdict_worst"] == "stable" and r["unmet_tail_max"] < 30:
            print(f"  SHORTLIST {r['family']} = {r['value']} ({r['n_seeds']} seeds)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
