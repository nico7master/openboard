#!/usr/bin/env python3
"""P3: Hidden-systems study — disasters, spoilage, panic buying, machine wear,
new businesses. 4 arms x 3 seeds, 650 ticks, 1000 citizens.

Design: every arm enables the SAME harsh shock profile with the DEFAULT
rng_seed (0). The engine re-seeds the shock RNG per tick
(random.Random(f"{seed}:{tick}")), so all arms with the same world seed see
byte-identical exogenous shock sequences — paired comparisons isolate exactly
one hidden system per arm:

  disaster        shocks only                (reference; re-run of P2 crisis_off with tracking)
  disaster_spoil  shocks + perishability     (does rot waste or discipline hoarding?)
  disaster_memory shocks + demand_memory     (does remembered shortage deepen panic?)
  disaster_wear   shocks + durable_capital   (does wear crash the capital chain?)

Founders (entrepreneur bots) are wired into every cast by server.py; their
FOUND_COOP events are tracked to answer the new-businesses question.
Healthy (no-shock) control = P2 skills_off runs.
"""
import json
import os
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
from openboard.metrics import gini  # noqa: E402

OUT_DIR = ROOT / "sweeps" / "p3"
TARGET_CITIZENS = 1000

SMOKE = os.environ.get("SMOKE") == "1"
if SMOKE:
    TARGET_CITIZENS = 80

# harsh profile, rng_seed left at default 0 -> identical stream across arms
SHOCKS_PARAMS = {"enabled": True, "profile": "harsh"}
SHELF_LIFE = {"bread": 4, "milk": 3, "meat": 5, "eggs": 6, "cheese": 10,
              "fruit": 5, "vegetables": 5, "meals": 2, "fish": 3}
FOOD_KEYS = tuple(SHELF_LIFE) + ("grain", "flour", "canned_food")

ARMS = (
    "disaster",
    "disaster_spoil",
    "disaster_memory",
    "disaster_wear",
    "disaster_nowear",
)


class P3Run(Run):
    """Arm-specific params via _params (genesis injection, P2-proven)."""

    def __init__(self, arm: str, **kw):
        self.arm = arm
        super().__init__(scenario="equal", governance=False, **kw)

    def _params(self):
        p = super()._params()
        p["shocks"] = dict(SHOCKS_PARAMS)
        if self.arm == "disaster_spoil":
            p["perishability"] = {"enabled": True, "shelf_life": dict(SHELF_LIFE)}
        elif self.arm == "disaster_memory":
            p["demand_memory"] = {"enabled": True}
        elif self.arm == "disaster_wear":
            p["durable_capital"] = {"enabled": True, "durability": 20}
        elif self.arm == "disaster_nowear":
            # base Run enables wear for EVERY scenario (server.py), so the
            # proper wear A/B is disaster(wear ON) vs this arm (wear OFF)
            p["durable_capital"] = {"enabled": False}
        return p


def _inv_by_good(state) -> dict:
    totals = {}
    for c in state.coops.values():
        for g, q in (c.get("inventory") or {}).items():
            totals[g] = totals.get(g, 0) + int(q)
    return totals


def run(arm: str, seed: int, ticks: int) -> dict:
    name = f"smoke_{arm}_s{seed}.json" if SMOKE else f"{arm}_s{seed}.json"
    out = OUT_DIR / name
    if out.exists():
        return json.loads(out.read_text())  # resumable
    t0 = time.perf_counter()
    r = P3Run(arm=arm, seed=seed)
    series = []
    produced_total = deaths_total = 0
    spoil_by_good = Counter()
    shock_counts = Counter()
    shock_first = {}
    found_coops = []

    for t in range(2, ticks + 1):
        drive(r, seed, t, t)
        if t == 2:
            scale_world(r, TARGET_CITIZENS)
        s = r.state
        for e in s.applied:
            a = e.get("action", "")
            if a.startswith("PRODUCE") and a != "PRODUCE_FAIL":
                produced_total += 1
            elif a == "CITIZEN_DEATH":
                deaths_total += 1
            elif a == "SHOCK_START":
                k = e.get("kind", "?")
                shock_counts[k] += 1
                shock_first.setdefault(k, t)
            elif a == "SPOIL":
                spoil_by_good[e.get("good", "?")] += int(e.get("qty", 0))
            elif a == "FOUND_COOP":
                if len(found_coops) < 500:
                    found_coops.append({
                        "tick": t,
                        **{k: e.get(k) for k in
                           ("sender", "actor", "citizen", "coop_id", "recipe_id", "recipe")
                           if k in e},
                    })

        if t % 5 == 0 or t == ticks:
            inv = _inv_by_good(s)
            machine_total = sum(q for g, q in inv.items()
                                if "machine" in g or "tool" in g)
            unmet = sum(1 for u in s.unmet_needs.values()
                        if any(u.get(g) for g in ESSENTIALS))
            series.append([t, len(s.balances), gini(list(s.balances.values())),
                           unmet, int(s.surplus_pool), produced_total,
                           deaths_total, machine_total,
                           sum(spoil_by_good.values()), len(found_coops)])

        s.applied.clear()
        r.batches.clear()
        if t % 50 == 0:
            trim_retention(r)

    s = r.state
    money = money_delta(r)
    final_inv = _inv_by_good(s)
    unmet_final = sum(1 for u in s.unmet_needs.values()
                      if any(u.get(g) for g in ESSENTIALS))
    res = {
        "arm": arm, "seed": seed, "ticks": ticks,
        "smoke": SMOKE,
        "wall_s": round(time.perf_counter() - t0, 1),
        "final": {
            "pop": len(s.balances),
            "unmet": unmet_final,
            "pool_units": int(s.surplus_pool),
            "gini": gini(list(s.balances.values())),
            "produced_total": produced_total,
            "deaths_total": deaths_total,
            "machines": final_inv.get("machines", 0),
            "hand_tools": final_inv.get("hand_tools", 0),
            "food_inv": {g: final_inv.get(g, 0) for g in FOOD_KEYS},
            "spoil_total": sum(spoil_by_good.values()),
            "found_count": len(found_coops),
        },
        "shocks": {"counts": dict(shock_counts), "first_tick": shock_first},
        "spoil_by_good": dict(spoil_by_good),
        "found_coops": found_coops,
        "series": series,
        "money_delta": money,
        "money_ok": money == 0,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, indent=2, sort_keys=True))
    return res


if __name__ == "__main__":
    arm = sys.argv[1] if len(sys.argv) > 1 else "disaster"
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 42
    ticks = int(sys.argv[3]) if len(sys.argv) > 3 else (12 if SMOKE else 650)
    res = run(arm, seed, ticks)
    print(json.dumps(res, sort_keys=True), flush=True)
