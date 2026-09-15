#!/usr/bin/env python
"""Priority 1 study: Land & Rent (docs/STUDY_PLAN.md).

Question: if one person owns all the land, do others starve?

Engine reality: land is a fixed financial asset (no production channel).
The monopoly channels are:
  HOLD  - buy all parcels cheap at genesis-pop prices, hold while the
          population (and assessments) appreciate ~50x. Georgist LVT
          bleeds the monopolist -> foreclosure cascade back to society.
  DUMP  - same buy, then SELL_LAND the whole portfolio after
          appreciation: 90% payout drains the Society Pool that funds
          everyone's dividends.

Scenarios (land rule ON in all, identical params, same seeds):
  control - nobody buys (parcels sit society-owned, inert)
  hold    - pool-funded monopolist buys ALL parcels at tick 2
  dump    - same, then sells all at dump_tick (default 60)

One combo per process (per-seed isolation), resumable JSON per combo
under sweeps/land_study/. Always launch via scripts/memrun.sh.

Usage: land_study.py SCENARIO SEED [ticks]
Env:   SMOKE=1 -> 10 ticks, 60 citizens, dump_tick 8 (wiring check)
"""
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "dashboard"))
sys.path.insert(0, str(ROOT / "scripts"))

from server import Run  # noqa: E402
from stage6_scale_gate import (  # noqa: E402
    ESSENTIALS, drive, money_delta, scale_world, trim_retention,
)
from openboard.land import assess  # noqa: E402
from openboard.ledger import Transaction  # noqa: E402
from openboard.metrics import gini  # noqa: E402

OUT_DIR = ROOT / "sweeps" / "land_study"
MONO_BALANCE = 1_200_000     # units (= 12,000 cr), pool-funded, no mint
DUMP_TICK = 60               # post-appreciation sell window
TARGET_CITIZENS = 1000

LAND_PARAMS = {
    "enabled": True,
    "base_land_price": 500,
    "land_tax_bp": 1,        # 1bp/tick ~ 3.6%/yr (Georgist default)
    "grace_ticks": 5,
}


class LandRun(Run):
    """Run with scripted monopolist actions injected into _apply_batch
    (drive() pushes bot batches through _apply_batch directly, so that
    is the one hook that always fires)."""

    def __init__(self, scenario_kind: str, dump_tick: int = DUMP_TICK, **kw):
        self.scenario_kind = scenario_kind
        self.dump_tick = dump_tick
        self.mono_injected = False
        super().__init__(scenario="equal", **kw)

    def _params(self):
        p = super()._params()
        p["land_market"] = dict(LAND_PARAMS)
        return p

    def _apply_batch(self, tick, batch):
        s = self.state
        if (self.scenario_kind in ("hold", "dump")
                and tick == 2 and not self.mono_injected):
            self.mono_injected = True
            # no-mint funding: recorded add_citizen injection takes the
            # stake out of the Society Pool (conservation intact)
            self._inject({"after_tick": tick, "op": "add_citizen",
                          "name": "monopolist", "balance": MONO_BALANCE})
            for pid in sorted(s.land_parcels.keys()):
                batch.append(Transaction(
                    tick=tick, sender="monopolist", action="BUY_LAND",
                    payload={"pid": pid}, ruleset_version=1))
        if self.scenario_kind == "dump" and tick == self.dump_tick:
            for pid in sorted(s.land_parcels.keys()):
                if s.land_parcels[pid].get("owner") == "monopolist":
                    batch.append(Transaction(
                        tick=tick, sender="monopolist", action="SELL_LAND",
                        payload={"pid": pid}, ruleset_version=1))
        super()._apply_batch(tick, batch)


def run_combo(scenario: str, seed: int, ticks: int) -> dict:
    out = OUT_DIR / f"{scenario}_s{seed}.json"
    if out.exists():
        return json.loads(out.read_text())  # resumable
    smoke = os.environ.get("SMOKE") == "1"
    target = 60 if smoke else TARGET_CITIZENS
    dump_tick = 8 if smoke else DUMP_TICK

    t0 = time.perf_counter()
    run = LandRun(scenario, dump_tick=dump_tick, seed=seed)
    agg = {"buy_n": 0, "buy_units": 0, "sell_n": 0, "sell_units": 0,
           "lvt_units": 0, "foreclosures": 0, "tax_due": 0}
    inv_bad = 0
    series = []
    streak = worst = 0

    for t in range(2, ticks + 1):
        drive(run, seed, t, t)
        if t == 2:
            scale_world(run, target)
        s = run.state
        for e in s.applied:
            if not isinstance(e, dict):
                continue
            a = e.get("action")
            if a == "LAND_TAX":
                agg["lvt_units"] += e.get("amount", 0)
            elif a == "LAND_TAX_DUE":
                agg["tax_due"] += 1
            elif a == "LAND_FORECLOSE":
                agg["foreclosures"] += 1
            elif a == "LAND_BOUGHT":
                agg["buy_n"] += 1
                agg["buy_units"] += e.get("price", 0)
            elif a == "LAND_SOLD":
                agg["sell_n"] += 1
                agg["sell_units"] += e.get("payout", 0)
        if money_delta(run) != 0:
            inv_bad += 1
        unmet = sum(1 for u in s.unmet_needs.values()
                    if any(u.get(g) for g in ESSENTIALS))
        streak = streak + 1 if unmet > 0 else 0
        worst = max(worst, streak)
        if t % 5 == 0 or t == ticks:
            bal = list(s.balances.values())
            assess_sum = sum(assess(s, pid, s.active_ruleset_params())
                             for pid in s.land_parcels)
            priv = sum(1 for p in s.land_parcels.values()
                       if p.get("owner") != "society")
            series.append([t, gini(bal), unmet, int(s.surplus_pool),
                           int(s.balances.get("monopolist", 0)),
                           priv, int(assess_sum)])
        s.applied.clear()
        run.batches.clear()
        if t % 50 == 0:
            trim_retention(run)

    s = run.state
    bal = list(s.balances.values())
    res = {
        "scenario": scenario, "seed": seed, "ticks": ticks,
        "smoke": smoke, "target_citizens": target,
        "wall_s": round(time.perf_counter() - t0, 1),
        "inv_bad": inv_bad, "agg": agg,
        "worst_unmet_streak": worst,
        "final": {
            "pop": len(bal), "gini": gini(bal),
            "unmet": sum(1 for u in s.unmet_needs.values()
                         if any(u.get(g) for g in ESSENTIALS)),
            "pool_units": int(s.surplus_pool),
            "mono_units": int(s.balances.get("monopolist", 0)),
            "priv_parcels": sum(1 for p in s.land_parcels.values()
                                if p.get("owner") != "society"),
        },
        "series": series,  # [t, gini, unmet, pool, mono, priv_parcels, assess_sum]
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, indent=2, sort_keys=True))
    return res


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(2)
    scenario, seed = sys.argv[1], int(sys.argv[2])
    ticks = int(sys.argv[3]) if len(sys.argv) > 3 else (10 if os.environ.get("SMOKE") == "1" else 650)
    print(json.dumps(run_combo(scenario, seed, ticks), sort_keys=True), flush=True)
