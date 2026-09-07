#!/usr/bin/env python
"""WP2.2 harvest re-run: prove winnable policy paths from the 50/50 start.

Re-runs policy COMBINATIONS (wealth tax rate x dividend share) on the
current engine -- unequal scenario, fixed 21M cap, D21g offer smoothing --
which the pre-cap banked sweeps never tested (banked data is single-knob
and pre-D21g; triage shows none of it meets the essentials bound alone).

Gate (plan WP2.2): >=3 distinct policy paths reach top-1 share < 1500 bp
while essentials unmet stays within the bound (30).

One combo per process invocation (10 GB cgroup; one seed per process).
Resumable: one JSON per combo under sweeps/unequal_rerun/.

Usage:
  harvest_rerun.py list                  # grid + what is missing
  harvest_rerun.py diag TAX,DIV [seed]   # 300-tick fast diagnostic
  harvest_rerun.py run TAX,DIV           # full 1500-tick run (next missing seed)
  harvest_rerun.py report                # aggregate combo JSONs -> heat-card
"""
import json
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "dashboard"))

from server import Run  # noqa: E402
from openboard.metrics import top1_share_bp  # noqa: E402

OUT = ROOT / "sweeps" / "unequal_rerun"
OUT.mkdir(parents=True, exist_ok=True)

SEEDS = [42, 123, 7]
# Combination grid: tax rate (bp/tick above threshold) x dividend share.
# Rates around the equal-world default 400bp; 100bp tests whether slow drain
# suffices once dividends recycle the pool.
TAX_RATES_BP = [100, 200, 400, 600, 800, 1200]
DIVIDEND_SHARES_BP = [2000, 3000, 5000]
TICKS_FULL = 1500
TICKS_DIAG = 300
ESSENTIALS = {"bread", "water", "electricity", "meals"}
ESSENTIALS_STREAK_BOUND = 30
TOP1_GATE_BP = 1500


def make_run(seed: int, tax_bp: int, div_bp: int) -> Run:
    """Unequal world with the policy combo enacted from genesis.

    The player path 'watch -> enact -> observe' is modeled as a ruleset
    change at t0: wealth tax ON above the engine-default threshold (5,000
    credits), surplus spending dividend share overridden. All other unequal
    world defaults (empty pool, D21g offer smoothing, producer input
    priority) stay exactly as the dashboard assembles them.
    """

    class PolicyRun(Run):
        def _params(self):
            p = super()._params()
            # threshold is already upc-scaled (x100) at the end of super()
            # ._params(); override ONLY the rate (a share, unit-free).
            # Overwriting the threshold here would silently re-break the
            # fixed-supply unit-scale fix (memory: 2026-09-04, 359eaa7).
            p["wealth_tax"]["rate_bp"] = tax_bp
            p["surplus_spending"]["dividend_share_bp"] = div_bp
            return p

    return PolicyRun(seed=seed, scenario="unequal")


def holders(state) -> list[int]:
    """PRIVATE wealth holders: citizen balances + coop treasuries.

    The Society Pool is EXCLUDED: it is public money (the tax's
    destination), not a private holder. The unequal scenario defines the
    start as 'top 1% owns 50% of private money, pool empty' — counting
    the pool would mask exactly the redistribution the gate measures.
    """
    vals = list(state.balances.values())
    vals += [c.get("treasury", 0) for c in state.coops.values()]
    return vals


def money_delta(run) -> int:
    """Exact money-supply invariant across ALL money locations.

    Matches stage6_sweeps.money_delta: balances, pool, capital fund,
    innovation pool, coop treasuries — vs minted/retired drift.
    """
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
    """Worst unmet streak per essential good (streak >= 1 = unmet now)."""
    worst: dict[str, int] = {}
    for _cit, goods in run.state.unmet_needs.items():
        for g, v in goods.items():
            if g in ESSENTIALS and v >= 1:
                worst[g] = max(worst.get(g, 0), v)
    return worst


def drive(run, tax_bp: int, div_bp: int, seed: int, ticks: int,
          log_every: int = 100) -> dict:
    """Core gate loop (hardcore_seed recipe, pruning included)."""
    t0 = time.perf_counter()
    top1_series: list[list[int]] = []  # [tick, top1_bp]
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
        # Memory hygiene (hardcore gate lesson: never let the ledger OOM us)
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
        if ess:
            print(f"  t={t} ESSENTIAL STREAKS {ess}", flush=True)
        if t % 10 == 0:
            top1_series.append([t, top1_share_bp(holders(run.state))])
        if t % 100 == 0:
            top1 = top1_share_bp(holders(run.state))
            peak = max(ess.values()) if ess else 0
            print(f"  t={t} top1={top1}bp ess_peak={peak}", flush=True)
    wall = time.perf_counter() - t0
    return {
        "tax_rate_bp": tax_bp,
        "dividend_share_bp": div_bp,
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
    eq_ok = res["final_top1_bp"] is not None and res["final_top1_bp"] < TOP1_GATE_BP
    if full:
        verdict = "WIN" if (ess_ok and inv_ok and eq_ok) else (
            "fed_but_unequal" if (ess_ok and inv_ok) else "broken"
        )
    else:
        verdict = "diag_ok" if (ess_ok and inv_ok) else "alarm"
    return {**res, "ess_ok": ess_ok, "inv_ok": inv_ok,
            "equity_gate": eq_ok, "verdict": verdict}


def fname(tax_bp: int, div_bp: int, seed: int) -> Path:
    return OUT / f"tax{tax_bp:04d}_div{div_bp:04d}_s{seed}.json"


def main() -> int:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "list"
    if cmd == "list":
        for t in TAX_RATES_BP:
            for d in DIVIDEND_SHARES_BP:
                have = [s for s in SEEDS if fname(t, d, s).exists()]
                print(f"tax={t:4d} div={d:4d}: {len(have)}/{len(SEEDS)} seeds done")
        return 0

    if cmd == "diag":
        tax_bp, div_bp = [int(x) for x in sys.argv[2].split(",")]
        seed = int(sys.argv[3]) if len(sys.argv) > 3 else SEEDS[0]
        print(f"DIAG tax={tax_bp} div={div_bp} seed={seed} ticks={TICKS_DIAG}", flush=True)
        run = make_run(seed, tax_bp, div_bp)
        res = classify(drive(run, tax_bp, div_bp, seed, TICKS_DIAG), full=False)
        out = OUT / f"diag_tax{tax_bp:04d}_div{div_bp:04d}_s{seed}.json"
        out.write_text(json.dumps(res, indent=1))
        print(f"verdict={res['verdict']} final_top1={res['final_top1_bp']}bp "
              f"inv_bad={res['inv_bad']} wall={res['wall_s']}s -> {out.name}")
        return 0

    if cmd == "run":
        tax_bp, div_bp = [int(x) for x in sys.argv[2].split(",")]
        pending = [s for s in SEEDS if not fname(tax_bp, div_bp, s).exists()]
        if not pending:
            print("combo complete")
            return 0
        seed = pending[0]
        print(f"RUN tax={tax_bp} div={div_bp} seed={seed} ticks={TICKS_FULL}", flush=True)
        run = make_run(seed, tax_bp, div_bp)
        res = classify(drive(run, tax_bp, div_bp, seed, TICKS_FULL), full=True)
        out = fname(tax_bp, div_bp, seed)
        out.write_text(json.dumps(res, indent=1))
        print(f"verdict={res['verdict']} final_top1={res['final_top1_bp']}bp "
              f"ess_ok={res['ess_ok']} inv_ok={res['inv_ok']} wall={res['wall_s']}s -> {out.name}")
        return 0

    if cmd == "report":
        rows = []
        for t in TAX_RATES_BP:
            for d in DIVIDEND_SHARES_BP:
                files = [fname(t, d, s) for s in SEEDS if fname(t, d, s).exists()]
                if not files:
                    continue
                results = [json.loads(f.read_text()) for f in files]
                verdicts = sorted({r["verdict"] for r in results})
                top1s = [r["final_top1_bp"] for r in results]
                ess_max = max(
                    max(r["worst_ess_streak"].values(), default=0) for r in results
                )
                rows.append(
                    f"| tax={t:4d} div={d:4d} | {len(files)} | {min(top1s)}-{max(top1s)} "
                    f"| {ess_max} | {','.join(verdicts)} |"
                )
        md = [
            "# Unequal-world policy-path harvest (current engine: fixed cap + D21g)",
            "",
            "Gate: verdict WIN on all seeds (top1 < 1500 bp, ess streaks <= 30, invariant exact).",
            "",
            "| combo | seeds | final top1 bp range | worst ess streak | verdicts |",
            "|---|---|---|---|---|",
            *rows,
        ]
        (OUT / "HEATCARD.md").write_text("\n".join(md) + "\n")
        print(f"wrote {OUT / 'HEATCARD.md'} ({len(rows)} combos)")
        return 0

    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main())
