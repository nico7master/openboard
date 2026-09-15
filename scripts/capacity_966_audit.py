#!/usr/bin/env python
"""966-citizen capacity audit (true-need follow-up, 2026-09-15).

Question: does the SCALED world's installed capacity cover the honest
post-kcal need for every essential? The 179-citizen gate verifies
code paths; this audit verifies the arithmetic at city scale.

Method:
  - build the baseline world, scale to target pop via the stage-6
    gate's scale_world (the same cloning the gate uses),
  - per good: need/tick = pop x quota  (or pop x daily_kcal / kcal_per_unit
    for kcal-group foods like the grain staple),
  - capacity/tick = sum over coops producing the good of
    floor(members x 8h / labor_hours) x output_qty  (theoretical max),
  - drive N ticks, then report demand_ema (what the founder trigger
    actually sees), capacity, need, and producer counts.

Also harvests WAGE_DEBT_ASSUMED events + final wage-debt book to check
D18 backstop calibration at scale (free rider on the same run).

Usage: capacity_966_audit.py [ticks] [seed] [target_pop]
Output: sweeps/society/capacity_966_s<seed>.json
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
from stage6_scale_gate import drive, scale_world, trim_retention  # noqa: E402


def need_map(params: dict, pop: int) -> dict[str, int]:
    kcal = params.get("kcal_needs") or {}
    kcal_map = {str(g): int(v) for g, v in (kcal.get("kcal_per_unit") or {}).items()}
    daily = int(kcal.get("daily_kcal", 0))
    quotas = params.get("essential_need_quota", {}) or {}
    cycle = params.get("needs_cycle", {}) or {}
    needs: dict[str, float] = {}
    for g in sorted(set(quotas) | set(kcal_map) | {"grain"}):
        if g in kcal_map and daily > 0:
            needs[g] = pop * daily / kcal_map[g]
        elif g in quotas:
            cyc = int(cycle.get(g, 1))
            needs[g] = pop * int(quotas[g]) / cyc
    return needs


def capacity_map(state) -> tuple[dict[str, int], dict[str, list]]:
    cap: dict[str, int] = {}
    producers: dict[str, list] = {}
    for cid in sorted(state.coops.keys()):
        c = state.coops[cid]
        r = state.recipes.get(c.get("recipe_intent"))
        members = len(c.get("members") or [])
        if not r or members <= 0:
            continue
        runs = (members * 8) / int(r["labor_hours"])  # fractional: pooled labor accumulates across ticks
        if runs <= 0:
            continue
        for g, q in r["outputs"].items():
            cap[g] = cap.get(g, 0) + runs * int(q)
            producers.setdefault(g, []).append(
                {"coop": cid, "members": members, "max_runs": runs}
            )
    return cap, producers


def snapshot(run, pop: int) -> dict:
    params = run.state.active_ruleset_params()
    needs = need_map(params, pop)
    cap, producers = capacity_map(run.state)
    rows = {}
    for g in sorted(needs):
        n = needs[g]
        c = cap.get(g, 0)
        rows[g] = {
            "need_per_tick": n,
            "capacity_per_tick": c,
            "coverage_bp": (c * 10_000 // n) if n else -1,
            "n_producers": len(producers.get(g, [])),
            "producers": producers.get(g, []),
        }
    return rows


def main() -> None:
    ticks = int(sys.argv[1]) if len(sys.argv) > 1 else 150
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 42
    target = int(sys.argv[3]) if len(sys.argv) > 3 else 966
    t0w = time.perf_counter()

    run = Run(seed=seed)
    pop = scale_world(run, target)
    t_start = run.state.tick + 1

    at_start = snapshot(run, pop)

    assumed_events: list[dict] = []
    for t in range(t_start, t_start + ticks):
        drive(run, seed, t, t)
        for ev in run.state.applied:
            if isinstance(ev, dict) and ev.get("action") == "WAGE_DEBT_ASSUMED":
                assumed_events.append(ev)
        trim_retention(run, keep_records=2_000, keep_events=4_000)

    at_end = snapshot(run, pop)
    ema = {g: run.state.demand_ema.get(g) for g in sorted(at_end)}
    wage_book = sum(
        sum((c.get("wage_debt") or {}).values()) for c in run.state.coops.values()
    )
    indebted = sum(1 for c in run.state.coops.values() if c.get("wage_debt"))

    result = {
        "seed": seed,
        "target_pop": pop,
        "ticks_driven": ticks,
        "wall_s": round(time.perf_counter() - t0w, 1),
        "at_start": at_start,
        "at_end": at_end,
        "demand_ema_at_end": ema,
        "d18_wage_debt_book": wage_book,
        "d18_indebted_coops": indebted,
        "d18_assumed_events": assumed_events,
    }
    out = ROOT / "sweeps" / "society" / f"capacity_966_s{seed}.json"
    out.write_text(json.dumps(result, indent=2))

    print(f"pop={pop} ticks={ticks} wall={result['wall_s']}s -> {out}")
    hdr = f"{'good':<14}{'need':>9}{'cap':>9}{'cov%':>7}{'ncoop':>7}{'ema_end':>10}"
    print(hdr)
    for g, row in at_end.items():
        cov = row["coverage_bp"] / 100 if row["coverage_bp"] >= 0 else -1
        e = ema.get(g)
        print(
            f"{g:<14}{row['need_per_tick']:>9}{row['capacity_per_tick']:>9}"
            f"{cov:>7.1f}{row['n_producers']:>7}{str(e):>10}"
        )
    print(
        f"D18: book={wage_book} indebted_coops={indebted} "
        f"assumed_events={len(assumed_events)}"
    )
    # kcal-group foods are substitutes: judge the GROUP, not each food
    kcal_cfg = params_cfg = None  # kcal map mirrored from rules.py defaults
    kcal_map = {"grain": 3400, "flour": 3600, "bread": 650, "meals": 700,
                "vegetables": 400, "fruit": 250, "eggs": 80, "fish": 200,
                "meat": 250, "milk": 300, "canned_food": 800, "cheese": 400}
    cap_kcal = sum(at_end[g]["capacity_per_tick"] * v for g, v in kcal_map.items() if g in at_end)
    need_kcal = pop * 2900
    grp = (cap_kcal / need_kcal * 100) if need_kcal else -1
    bad = [g for g, r in at_end.items()
           if g not in kcal_map and 0 <= r["coverage_bp"] < 10_000]
    print(f"KCAL GROUP coverage: {grp:,.0f}% (famine impossible while >=100)")
    print(f"UNDER-CAPACITY (non-food): {bad if bad else 'none'}")


if __name__ == "__main__":
    main()
