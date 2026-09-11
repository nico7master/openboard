#!/usr/bin/env python
"""Lever Atlas: systematic multi-lever sweeps -> the policy playbook.

Measures what each realism lever (L1 credit interest, L2 scarcity
pricing cap, L3 research share) DOES to the proven-good baseline
world (unequal scenario + wealth tax 400bp + dividend 3000bp), alone
and in combination -- so game design and future policy calls can read
the answer instead of re-running simulations.

Grid: rate_bp_annual x max_markup_bp x research_share_bp (3x3x3) x 3 seeds.
One combo per process invocation, resumable: one JSON per combo under
sweeps/atlas/. Run via memrun.sh ALWAYS (2-core pin, mem cap).

Usage:
  atlas_grid.py list                  # grid + what is missing
  atlas_grid.py diag I,S,R [seed]     # 300-tick fast diagnostic
  atlas_grid.py run I,S,R             # full 600-tick run (next missing seed)
  atlas_grid.py report                # aggregate -> ATLAS.md playbook
"""
import json
import random
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "dashboard"))

from server import Run  # noqa: E402
from openboard.metrics import top1_share_bp  # noqa: E402

OUT = ROOT / "sweeps" / "atlas"
OUT.mkdir(parents=True, exist_ok=True)

SEEDS = [42, 123, 7]
# Lever grids (contract-test shapes):
#  L1 credit interest: 0 = free credit (old world), 300 = mild, 600 = strong
RATES_BP = [0, 300, 600]
#  L2 scarcity pricing cap: 0 = cost-floor only (no signal), 1250 = half, 2500 = engine default
MARKUPS_BP = [0, 1250, 2500]
#  L3 research share of surplus: 0 = none, 250, 500 = contract-test default
RESEARCH_BP = [0, 250, 500]
TICKS_FULL = 600
TICKS_DIAG = 300
ESSENTIALS = {"bread", "water", "electricity", "meals"}
ESSENTIALS_STREAK_BOUND = 30

# Fixed baseline policy: the proven-winning wealth-tax combo from the
# harvest (tax0400_div3000 passed all seeds). The atlas varies ONLY the
# three realism levers on top of it.
BASE_TAX_BP = 400
BASE_DIV_BP = 3000


def make_run(seed: int, rate_bp: int, markup_bp: int, research_bp: int) -> Run:
    """Unequal world + baseline policy + the lever combo from genesis."""

    class AtlasRun(Run):
        def _params(self):
            p = super()._params()
            p["wealth_tax"]["rate_bp"] = BASE_TAX_BP
            p["surplus_spending"]["dividend_share_bp"] = BASE_DIV_BP
            # L1 credit interest (exact contract-test shape)
            p["credit"] = {"enabled": True, "max_per_citizen": 1_000,
                           "term_ticks": 50, "fee_bp": 0,
                           "rate_bp_annual": rate_bp}
            # L2 scarcity pricing (exact contract-test shape; cap 0 = off)
            p["scarcity_pricing"] = {
                "enabled": True, "max_markup_bp": markup_bp,
                "step_bp": 500, "decay_bp": 250,
            }
            # L3 research (exact contract-test shape)
            p["research"] = {"enabled": True,
                             "research_share_bp": research_bp,
                             "unlock_threshold": 5_000}
            return p

    return AtlasRun(seed=seed, scenario="unequal")


def holders(state) -> list[int]:
    vals = list(state.balances.values())
    vals += [c.get("treasury", 0) for c in state.coops.values()]
    return vals


def money_delta(run) -> int:
    s = run.state
    total = (
        sum(s.balances.values())
        + s.surplus_pool
        + s.capital_fund
        + getattr(s, "innovation_pool", 0)
        + sum(c.get("treasury", 0) for c in s.coops.values())
    )
    if not hasattr(run, "_money0"):
        run._money0 = total - s.money_minted + s.money_retired
    return total - (run._money0 + s.money_minted - s.money_retired)


def essentials_streaks(run) -> dict[str, int]:
    worst: dict[str, int] = {}
    for _cit, goods in run.state.unmet_needs.items():
        for g, v in goods.items():
            if g in ESSENTIALS and v >= 1:
                worst[g] = max(worst.get(g, 0), v)
    return worst


def drive(run, combo: dict, seed: int, ticks: int,
          log_every: int = 100) -> dict:
    """Core loop (harvest_rerun recipe: prune, clear, invariant every tick)."""
    t0 = time.perf_counter()
    top1_series: list[list[int]] = []
    worst_ess: dict[str, int] = {}
    inv_bad = 0
    for t in range(2, ticks + 2):
        actions = []
        for name, meta in sorted(run.bots.items()):
            rng = random.Random(f"{seed}:{t}:{name}")
            actions.extend(
                meta["fn"](name, run.state, run.state.active_ruleset_params(), t, rng)
            )
        run._apply_batch(t, actions)
        run._record_timeline()
        run.state.applied.clear()
        run.batches.clear()
        run._last_events = []
        recs = run.ledger.records
        if len(recs) > 4000:
            del recs[: len(recs) - 1000]
        if money_delta(run) != 0:
            inv_bad += 1
        ess = essentials_streaks(run)
        for g, v in ess.items():
            worst_ess[g] = max(worst_ess.get(g, 0), v)
        if t % 10 == 0:
            top1_series.append([t, top1_share_bp(holders(run.state))])
        if t % log_every == 0:
            peak = max(ess.values()) if ess else 0
            print(f"  t={t} top1={top1_share_bp(holders(run.state))}bp "
                  f"ess_peak={peak}", flush=True)
    wall = time.perf_counter() - t0
    return {
        **combo,
        "seed": seed,
        "ticks": ticks,
        "wall_s": round(wall, 1),
        "inv_bad": inv_bad,
        "worst_ess_streak": worst_ess,
        "top1_series": top1_series,
        "final_top1_bp": top1_series[-1][1] if top1_series else None,
    }


def classify(res: dict, full: bool) -> dict:
    streaks = res["worst_ess_streak"]
    ess_ok = all(v <= ESSENTIALS_STREAK_BOUND for v in streaks.values())
    inv_ok = res["inv_bad"] == 0
    eq_ok = res["final_top1_bp"] is not None and res["final_top1_bp"] < 1500
    if full:
        verdict = "WIN" if (ess_ok and inv_ok and eq_ok) else (
            "fed_but_unequal" if (ess_ok and inv_ok) else "broken")
    else:
        verdict = "diag_ok" if (ess_ok and inv_ok) else "alarm"
    return {**res, "ess_ok": ess_ok, "inv_ok": inv_ok,
            "equity_gate": eq_ok, "verdict": verdict}


def fname(rate_bp: int, markup_bp: int, research_bp: int, seed: int) -> Path:
    return OUT / f"i{rate_bp:04d}_m{markup_bp:04d}_r{research_bp:04d}_s{seed}.json"


def main() -> int:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "list"
    if cmd == "list":
        for r in RATES_BP:
            for m in MARKUPS_BP:
                for q in RESEARCH_BP:
                    have = [s for s in SEEDS if fname(r, m, q, s).exists()]
                    print(f"rate={r:4d} markup={m:4d} research={q:4d}: "
                          f"{len(have)}/{len(SEEDS)} seeds done")
        return 0

    if cmd == "diag":
        r, m, q = [int(x) for x in sys.argv[2].split(",")]
        seed = int(sys.argv[3]) if len(sys.argv) > 3 else SEEDS[0]
        print(f"DIAG rate={r} markup={m} research={q} seed={seed}", flush=True)
        run = make_run(seed, r, m, q)
        res = classify(drive(run, {"rate_bp_annual": r, "max_markup_bp": m,
                                   "research_share_bp": q}, seed, TICKS_DIAG),
                       full=False)
        out = OUT / f"diag_i{r:04d}_m{m:04d}_r{q:04d}_s{seed}.json"
        out.write_text(json.dumps(res, indent=1))
        print(f"verdict={res['verdict']} top1={res['final_top1_bp']}bp "
              f"inv_bad={res['inv_bad']} wall={res['wall_s']}s -> {out.name}")
        return 0

    if cmd == "run":
        r, m, q = [int(x) for x in sys.argv[2].split(",")]
        pending = [s for s in SEEDS if not fname(r, m, q, s).exists()]
        if not pending:
            print("combo complete")
            return 0
        seed = pending[0]
        print(f"RUN rate={r} markup={m} research={q} seed={seed}", flush=True)
        run = make_run(seed, r, m, q)
        res = classify(drive(run, {"rate_bp_annual": r, "max_markup_bp": m,
                                   "research_share_bp": q}, seed, TICKS_FULL),
                       full=True)
        out = fname(r, m, q, seed)
        out.write_text(json.dumps(res, indent=1))
        print(f"verdict={res['verdict']} top1={res['final_top1_bp']}bp "
              f"ess_ok={res['ess_ok']} inv_ok={res['inv_ok']} "
              f"wall={res['wall_s']}s -> {out.name}")
        return 0

    if cmd == "report":
        rows = []
        for f in sorted(OUT.glob("i*_m*_r*_s*.json")):
            rows.append(json.loads(f.read_text()))
        if not rows:
            print("no results yet")
            return 0
        lines = ["# Lever Atlas Playbook", "",
                 f"runs={len(rows)} baseline=tax{BASE_TAX_BP}/div{BASE_DIV_BP}", ""]
        # verdict counts
        from collections import Counter
        vc = Counter(r["verdict"] for r in rows)
        lines.append(f"verdicts: {dict(vc)}")
        lines.append("")
        # marginal lever effects: mean top1 + worst streak by lever level
        for key, label in (("rate_bp_annual", "L1 interest"),
                           ("max_markup_bp", "L2 scarcity cap"),
                           ("research_share_bp", "L3 research share")):
            lines.append(f"## {label}")
            levels = sorted({r[key] for r in rows})
            for lv in levels:
                sub = [r for r in rows if r[key] == lv]
                tops = [r["final_top1_bp"] for r in sub if r["final_top1_bp"] is not None]
                worst = max((max(s.values()) for s in
                             (r["worst_ess_streak"] for r in sub) if s), default=0)
                wins = sum(1 for r in sub if r["verdict"] == "WIN")
                mt = round(statistics.mean(tops)) if tops else None
                lines.append(f"- {lv:5d}: n={len(sub):2d} WIN={wins:2d} "
                             f"mean_top1={mt}bp worst_ess={worst}")
            lines.append("")
        # interaction check: does the best single setting stay best combined?
        best = min(rows, key=lambda r: r["final_top1_bp"] or 10**9)
        lines.append(f"best single run: rate={best['rate_bp_annual']} "
                     f"markup={best['max_markup_bp']} "
                     f"research={best['research_share_bp']} "
                     f"seed={best['seed']} top1={best['final_top1_bp']}bp "
                     f"verdict={best['verdict']}")
        (OUT / "ATLAS.md").write_text("\n".join(lines) + "\n")
        print("\n".join(lines))
        return 0

    print(__doc__)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
