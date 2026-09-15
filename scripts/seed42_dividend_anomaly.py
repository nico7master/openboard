#!/usr/bin/env python
"""Seed-42 anomaly: mechanism or butterfly effect?

Existing land-study data: control_s42 ended unmet=616 while hold_s42 and
dump_s42 ended unmet=1. Two hypotheses:

  A (mechanism): the monopolist's 11.8k-cr land buy-in was paid INTO the
     surplus pool, recycled as dividends/services, lifting consumption.
  B (chaos): the single extra 'monopolist' citizen perturbs bot ordering
     and batch composition -> the whole trajectory diverges; the gap is
     noise, not mechanism.

Test: perturb run = inject ONE extra citizen (500 cr, pool-funded via
the D15 add_citizen path) at t=2, with the SAME land rule as control but
NO land purchases. If unmet flips toward ~1 anyway, chaos wins (B).

Also compares divergence onset against the existing land-study series.

Usage: seed42_dividend_anomaly.py [scenario] [seed] [ticks]
  scenario: perturb (default) | control
Launch via scripts/memrun.sh. Results: sweeps/seed42_anomaly/
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
from stage6_scale_gate import (  # noqa: E402
    ESSENTIALS, drive, scale_world, trim_retention,
)
from openboard.metrics import gini  # noqa: E402

OUT_DIR = ROOT / "sweeps" / "seed42_anomaly"

# identical land params to the land-study control (rule ON, nobody buys)
LAND_PARAMS = {
    "enabled": True,
    "base_land_price": 500,
    "land_tax_bp": 1,
    "grace_ticks": 5,
}


class PerturbRun(Run):
    """Control world + ONE extra citizen at t=2 (no land purchases).

    _params is overridden INSIDE the class so genesis sees land_market
    enabled (a post-init lambda patch would be too late for parcels).
    """

    def __init__(self, **kw):
        self.injected = False
        super().__init__(scenario="equal", **kw)

    def _params(self):
        p = super()._params()
        p["land_market"] = dict(LAND_PARAMS)
        return p

    def _apply_batch(self, tick, batch):
        if tick == 2 and not self.injected:
            self.injected = True
            # D15: add_citizen with money_cap ON funds the stake from the
            # surplus pool -> conservation intact, no mint.
            self._inject({"after_tick": tick, "op": "add_citizen",
                          "name": "extra_1", "balance": 500})
        super()._apply_batch(tick, batch)


def run(scenario: str, seed: int, ticks: int) -> dict:
    out = OUT_DIR / f"{scenario}_s{seed}.json"
    if out.exists():
        return json.loads(out.read_text())  # resumable
    t0 = time.perf_counter()
    r = PerturbRun(seed=seed)
    series = []
    for t in range(2, ticks + 1):
        drive(r, seed, t, t)
        if t == 2:
            scale_world(r, 1000)
        s = r.state
        if t % 5 == 0 or t == ticks:
            unmet = sum(1 for u in s.unmet_needs.values()
                        if any(u.get(g) for g in ESSENTIALS))
            series.append([t, unmet, int(s.surplus_pool),
                           gini(list(s.balances.values()))])
        s.applied.clear()
        r.batches.clear()
        if t % 50 == 0:
            trim_retention(r)
    s = r.state
    res = {
        "scenario": scenario, "seed": seed, "ticks": ticks,
        "wall_s": round(time.perf_counter() - t0, 1),
        "final": {
            "pop": len(s.balances),
            "unmet": sum(1 for u in s.unmet_needs.values()
                         if any(u.get(g) for g in ESSENTIALS)),
            "pool_units": int(s.surplus_pool),
            "gini": gini(list(s.balances.values())),
        },
        "series": series,  # [t, unmet, pool, gini]
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, indent=2, sort_keys=True))
    return res


if __name__ == "__main__":
    scenario = sys.argv[1] if len(sys.argv) > 1 else "perturb"
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 42
    ticks = int(sys.argv[3]) if len(sys.argv) > 3 else 650
    print(json.dumps(run(scenario, seed, ticks), sort_keys=True), flush=True)
