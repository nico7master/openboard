#!/usr/bin/env python
"""RC1 week-4 soak: 3 seeds x 2,000 ticks x ~1,000 citizens, ALL founder
defaults ON (Run(governance=True): vote token + persuasion + reachable
quorum + whistleblower + audits + need_allocation + scarcity pricing),
capital_refresh ON (scale requirement from the 2026-09-10 gate ladder).

Criteria (freeze gate): money invariant exact EVERY tick; essentials
streak <= 50 post-genesis; deaths recorded; governance evidence (audits,
votes, proposals) counted. Resumable: per-seed JSON written once complete.

Usage: rc1_soak.py SEED [ticks]
"""
import json
import random
import resource
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "dashboard"))
sys.path.insert(0, str(ROOT / "scripts"))

from server import Run  # noqa: E402
from stage6_scale_gate import (  # noqa: E402
    ESSENTIALS, drive, money_delta, scale_world, trim_retention,
)

OUT_DIR = ROOT / "sweeps" / "rc1_soak"
OUT_DIR.mkdir(parents=True, exist_ok=True)
TICKS = int(sys.argv[2]) if len(sys.argv) > 2 else 2000


def main():
    seed = int(sys.argv[1])
    out = OUT_DIR / f"soak_gov_s{seed}.json"
    if out.exists():
        print(f"RESUMABLE: {out} exists, skipping")
        return
    t0 = time.perf_counter()
    run = Run(seed=seed, governance=True)
    pop = scale_world(run, 1000)
    print(f"seed {seed}: scaled population {pop}", flush=True)

    inv_bad = 0
    streak = 0
    worst_streak = 0
    worst_detail = None
    deaths = 0
    act: Counter = Counter()
    t_drive0 = time.perf_counter()

    for t in range(run.state.tick + 1, TICKS + 1):
        drive(run, seed, t, t)
        if money_delta(run) != 0:
            inv_bad += 1
        s = run.state
        for e in s.applied:
            a = e.get("action", "")
            act[a] += 1
            if a == "CITIZEN_DEATH":
                deaths += 1
        unmet = sum(1 for un in s.unmet_needs.values()
                    if any(un.get(g) for g in ESSENTIALS))
        if unmet > 0:
            streak += 1
            if streak > worst_streak:
                worst_streak = streak
                good_hits = {}
                for un in s.unmet_needs.values():
                    for g in ESSENTIALS:
                        if un.get(g):
                            good_hits[g] = good_hits.get(g, 0) + 1
                worst_detail = {"tick": t, "citizens": unmet, "goods": good_hits}
        else:
            streak = 0
        if t % 50 == 0:
            trim_retention(run)
        if t % 250 == 0:
            el = time.perf_counter() - t_drive0
            rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024
            print(f"  t={t} elapsed={el:.0f}s rss={rss}MB inv_bad={inv_bad} "
                  f"streak={streak} deaths={deaths}", flush=True)

    s = run.state
    fin_pop = len(s.balances)
    props = s.proposals
    doc = {
        "seed": seed, "ticks": TICKS, "pop_start": pop, "pop_end": fin_pop,
        "deaths": deaths,
        "inv_bad": inv_bad,
        "worst_ess_streak": worst_streak,
        "worst_detail": worst_detail,
        "governance": {
            "proposals_total": len(props),
            "proposals_passed": sum(1 for p in props.values() if p.get("status") == "passed"),
            "proposals_rejected": sum(1 for p in props.values() if p.get("status") == "rejected"),
            "proposals_failed": sum(1 for p in props.values() if p.get("status") == "failed"),
            "votes_cast": act.get("VOTE", 0),
            "audits": act.get("AUDIT_REPORT", 0),
            "whistle_flags": act.get("OVERSIGHT_FLAG", 0),
            "reports": act.get("REPORT", 0),
        },
        "economy": {
            "produced_total": act.get("PRODUCE", 0),
            "gini": __import__("openboard.metrics", fromlist=["gini"]).gini(list(s.balances.values())),
            "pool_units": s.surplus_pool,
            "money_ok": inv_bad == 0,
        },
        "final_ess_streak": streak,
        "wall_s": round(time.perf_counter() - t0, 1),
        "rss_mb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024,
    }
    out.write_text(json.dumps(doc, indent=1))
    verdict = ("PASS" if inv_bad == 0 and worst_streak <= 50 else "FAIL")
    print(f"RC1 SOAK seed {seed}: {verdict} inv_bad={inv_bad} "
          f"worst_streak={worst_streak} deaths={deaths} "
          f"props={len(props)} votes={act.get('VOTE', 0)} audits={act.get('AUDIT_REPORT', 0)} "
          f"wall={doc['wall_s']}s -> {out}", flush=True)


if __name__ == "__main__":
    main()
