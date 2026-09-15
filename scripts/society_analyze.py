#!/usr/bin/env python3
"""Society in Motion analyzer (spec 2026-09-13-society-in-motion-study.md).

For each 2x2 pair: within-seed interaction effect (AB - A - B + base) on
every final metric, plus society-timeline extraction for narratives.
For sequencing arms: same-lever, different-timing comparisons.

Usage: society_analyze.py
Output: sweeps/society/ANALYSIS.json (raw numbers only - stories are
written by hand from these numbers into FINDINGS.md).
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "sweeps" / "society"
SEEDS = (7, 42, 123)

PAIRS = {
    "pair1_spoilage_x_disasters": ("base", "spoil_long", "disaster", "spoil_disaster"),
    "pair2_skills_x_research": ("base2", "skills_on", "research_fixed", "skills_research"),
    "pair3_tax_x_landdump": ("base3", "tax800", "land_dump", "tax_dump"),
}

SEQ_GROUPS = {
    "seq_research": ("research_early", "research_late", "research_never"),
    "seq_crisis": ("crisis_onset", "crisis_late100"),
}

FINAL_METRICS = (
    "gini", "produced", "unmet", "unmet_streak_max", "pool_units",
    "found_total", "deaths",
)
TIMELINE_KEYS = (
    "unmet", "top1_bp", "mid60_bp", "bot20_bp", "bread_idx",
    "real_wage", "div_pp", "top_coop_bp",
)


def load(arm: str, seed: int) -> dict | None:
    p = OUT / f"{arm}_s{seed}.json"
    if not p.exists():
        return None
    return json.loads(p.read_text())


def interactions(cell: dict) -> dict:
    """cell: {base, A, B, AB} of {seed: final-dict}. Returns per-metric
    interaction = AB - A - B + base (per seed + median)."""
    out = {}
    for m in FINAL_METRICS:
        per_seed = {}
        for s in SEEDS:
            b, a, bb, ab = (cell[k][s] for k in ("base", "A", "B", "AB"))
            if None in (b, a, bb, ab):
                per_seed[s] = None
            else:
                per_seed[s] = ab[m] - a[m] - bb[m] + b[m]
        vals = [v for v in per_seed.values() if v is not None]
        med = sorted(vals)[len(vals) // 2] if len(vals) == len(SEEDS) else None
        out[m] = {"per_seed": per_seed, "median": med}
    return out


def society_story(d: dict) -> dict:
    """Condense one run's society timeline into story-relevant moments."""
    soc = d.get("society") or []
    if not soc:
        return {}
    famine = [p for p in soc if p["unmet"] > 50]
    peak = max(soc, key=lambda p: p["unmet"])
    return {
        "t_start": soc[0]["t"],
        "famine_windows": [
            {"from": famine[0]["t"], "to": famine[-1]["t"],
             "peak_unmet": max(p["unmet"] for p in famine)}
        ] if famine else [],
        "peak": {"t": peak["t"], **{k: peak[k] for k in TIMELINE_KEYS}},
        "arc": [
            {"t": p["t"], **{k: p[k] for k in TIMELINE_KEYS}}
            for p in soc
        ],
    }


def main() -> None:
    result = {"pairs": {}, "sequencing": {}, "stories": {}}

    for pname, (base, a, b, ab) in PAIRS.items():
        cell = {"base": {}, "A": {}, "B": {}, "AB": {}}
        keys = {"base": base, "A": a, "B": b, "AB": ab}
        for role, arm in keys.items():
            for s in SEEDS:
                d = load(arm, s)
                cell[role][s] = d["final"] if d else None
        result["pairs"][pname] = {
            "arms": keys,
            "finals": cell,
            "interaction": interactions(cell),
        }

    for gname, arms in SEQ_GROUPS.items():
        result["sequencing"][gname] = {}
        for arm in arms:
            finals = {}
            for s in SEEDS:
                d = load(arm, s)
                finals[s] = d["final"] if d else None
            result["sequencing"][gname][arm] = finals

    # Society stories for every completed run
    for arm_dir in sorted(OUT.glob("*_s*.json")):
        if arm_dir.name.startswith("smoke_"):
            continue
        d = json.loads(arm_dir.read_text())
        result["stories"][arm_dir.stem] = society_story(d)

    out = OUT / "ANALYSIS.json"
    out.write_text(json.dumps(result, indent=1, sort_keys=True))
    print(f"wrote {out} ({out.stat().st_size:,} bytes)")

    # quick console summary of what's complete
    for pname, (base, a, b, ab) in PAIRS.items():
        done = sum(
            1 for arm in (base, a, b, ab) for s in SEEDS if load(arm, s)
        )
        print(f"{pname}: {done}/12 cells")
    for gname, arms in SEQ_GROUPS.items():
        done = sum(1 for arm in arms for s in SEEDS if load(arm, s))
        print(f"{gname}: {done}/{len(arms) * len(SEEDS)} cells")


if __name__ == "__main__":
    main()
