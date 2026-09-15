#!/usr/bin/env python3
"""P4: Combinations study — Land+Trade, Disaster+Trade, Everything-ON.

4 arms x 3 seeds, 650 ticks, 1000 citizens. Pairs against EXISTING corners:

  trade_only      5 traders, no land, no shocks   vs p2 skills_off (control)
  land_trade      dump monopolist + traders       vs p1 dump (same stream)
  disaster_trade  harsh shocks + traders          vs p3 disaster (same stream)
  all_on          shocks+land+traders+skills+
                  realistic spoilage+research     vs disaster_trade

Trader bot-world reality (P1: bots have NO trade logic): 5 scripted,
fully-fed citizens (P1 lesson: unfed scripted citizens poison unmet metrics)
run a profit-seeking import/export book every tick:
  - BUY_ESSENTIAL bread/water/electricity (domestic, keeps them fed)
  - IMPORT_GOOD grain (world 200 < domestic 300): import channel that
    displaces domestic grain demand + pays tariff into the pool
  - every 10 ticks (staggered): BID bread at 2x baseline (outbids citizens —
    clearing sorts by max_price), then EXPORT pantry bread above reserve
    next tick (drain channel; world bread price spikes to 700 at the
    drought, aligned with the engine drought t=533)

Conservation: money_delta + Δforeign_balance == 0 (foreign bucket is not in
stage6 money_delta). Traders funded from the pool via recorded add_citizen
(no mint); funding tracked and reported.

One combo per process, resumable JSON, ALWAYS via scripts/memrun.sh.
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
from openboard.ledger import Transaction  # noqa: E402
from openboard.metrics import gini  # noqa: E402

OUT_DIR = ROOT / "sweeps" / "p4"
TARGET_CITIZENS = 1000

SMOKE = os.environ.get("SMOKE") == "1"
if SMOKE:
    TARGET_CITIZENS = 80

# ---------------- trader book ----------------
N_TRADERS = 5
TRADER_BALANCE = 3_000_000            # per trader, pool-funded (no mint)
BREAD_RESERVE = 10                    # pantry units kept for self
BREAD_BID_QTY = 20                    # per 10-tick cycle per trader
BREAD_BID_MULT = 2                    # max_price = baseline * 2
GRAIN_IMPORT_QTY = 10                 # per tick per trader
# world prices: grain/flour cheap (import), bread dear (export)
WORLD_PRICES = {"bread": 400, "grain": 200, "flour": 250, "meat": 900,
                "milk": 350, "eggs": 300, "vegetables": 450, "fruit": 450,
                "fish": 550}
TARIFF_BP = 500
# world famine premium aligned with the engine drought (P3: t=533)
WORLD_SHOCKS = ([{"tick": 6, "good": "bread", "price": 400}]
                if SMOKE else
                [{"tick": 533, "good": "bread", "price": 700},
                 {"tick": 533, "good": "grain", "price": 500}])

LAND_PARAMS = {
    "enabled": True, "base_land_price": 500,
    "land_tax_bp": 1, "grace_ticks": 5,
}
SHOCKS_PARAMS = {"enabled": True, "profile": "harsh"}
SKILLS_PARAMS = {"enabled": True, "hours_per_level": 100, "max_level": 5,
                 "output_bonus_bp": 500, "wage_bonus_bp": 300}
# P3 lesson: short shelf lives = instant famine. Realistic setting:
# week-scale shelf lives (7 ticks ~ a week if 1 tick ~ 1 day).
SHELF_LIFE = {"bread": 21, "milk": 14, "meat": 21, "eggs": 28,
              "cheese": 60, "fruit": 21, "vegetables": 21, "meals": 7,
              "fish": 14}
RESEARCH_PARAMS = {"enabled": True, "research_share_bp": 250}
DUMP_TICK = 60

ARMS = ("trade_only", "land_trade", "disaster_trade", "all_on")


class P4Run(Run):
    """Arm params + scripted trader/monopolist transactions."""

    def __init__(self, arm: str, dump_tick: int = DUMP_TICK, **kw):
        self.arm = arm
        self.dump_tick = dump_tick
        self.injected = False
        self.mono_injected = False    # land monopolist injected at tick 2
        self.cycle_flip = {}          # per-trader bid/export phase
        super().__init__(scenario="equal", **kw)

    def _params(self):
        p = super()._params()
        p["foreign_sector"] = {
            "enabled": True,
            "world_prices": dict(WORLD_PRICES),
            "tariff_bp": TARIFF_BP,
            "shocks": list(WORLD_SHOCKS),
        }
        if self.arm in ("land_trade", "all_on"):
            p["land_market"] = dict(LAND_PARAMS)
        if self.arm == "disaster_trade":
            p["shocks"] = dict(SHOCKS_PARAMS)
        if self.arm == "all_on":
            p["shocks"] = dict(SHOCKS_PARAMS)
            p["skills"] = dict(SKILLS_PARAMS)
            p["perishability"] = {"enabled": True,
                                  "shelf_life": dict(SHELF_LIFE)}
            p["research"] = dict(RESEARCH_PARAMS)
        return p

    def _apply_batch(self, tick, batch):
        s = self.state
        if not self.injected:
            self.injected = True
            # pool-funded, recorded (no mint) — P1 pattern
            for i in range(N_TRADERS):
                self._inject({"after_tick": 1, "op": "add_citizen",
                              "name": f"trader_{i}",
                              "balance": TRADER_BALANCE})
        # monopolist must ride the REAL tick-2 batch: Run.__init__ fires a
        # founding _apply_batch(1, ...) at construction, so tick-2 txs sent
        # in that call are rejected (land_study.py gates on tick == 2 too)
        if (self.arm in ("land_trade", "all_on")
                and tick == 2 and not self.mono_injected):
            self.mono_injected = True
            self._inject({"after_tick": 2, "op": "add_citizen",
                          "name": "monopolist", "balance": 1_200_000})
            for pid in sorted(s.land_parcels.keys()):
                batch.append(Transaction(
                    tick=tick, sender="monopolist", action="BUY_LAND",
                    payload={"pid": pid}, ruleset_version=1))

        # dump the land portfolio at dump_tick (P1 dump scenario)
        if self.arm in ("land_trade", "all_on") and tick == self.dump_tick:
            for pid in sorted(s.land_parcels.keys()):
                if (s.land_parcels[pid] or {}).get("owner") == "monopolist":
                    batch.append(Transaction(
                        tick=tick, sender="monopolist", action="SELL_LAND",
                        payload={"pid": pid}, ruleset_version=1))

        # trader book: essentials, grain imports, bread drain cycle
        for i in range(N_TRADERS):
            who = f"trader_{i}"
            bal = s.balances.get(who)
            if bal is None:
                continue
            for g in ("bread", "water", "electricity"):
                batch.append(Transaction(
                    tick=tick, sender=who, action="BUY_ESSENTIAL",
                    payload={"good": g, "qty": 1}, ruleset_version=1))
            batch.append(Transaction(
                tick=tick, sender=who, action="IMPORT_GOOD",
                payload={"good": "grain", "qty": GRAIN_IMPORT_QTY},
                ruleset_version=1))
            # staggered drain cycle: bid high for bread, export surplus
            # (smoke uses a compressed 4-tick cycle so the path is exercised)
            stag = 4 if SMOKE else 10
            if (tick + i) % stag == 0:
                base = s.good_cost_baseline.get("bread", 300)
                batch.append(Transaction(
                    tick=tick, sender=who, action="BID",
                    payload={"good": "bread",
                             "max_price": base * BREAD_BID_MULT,
                             "qty": BREAD_BID_QTY},
                    ruleset_version=1))
            held = (s.citizen_inventory.get(who) or {}).get("bread", 0)
            if (tick + i) % stag == stag // 2 and held > BREAD_RESERVE:
                batch.append(Transaction(
                    tick=tick, sender=who, action="EXPORT_GOOD",
                    payload={"good": "bread",
                             "qty": held - BREAD_RESERVE},
                    ruleset_version=1))
        super()._apply_batch(tick, batch)


def _inv_total(state, good, both=True) -> int:
    tot = sum((inv or {}).get(good, 0)
              for inv in state.citizen_inventory.values())
    if both:
        tot += sum((c.get("inventory") or {}).get(good, 0)
                   for c in state.coops.values())
    return tot


def run(arm: str, seed: int, ticks: int, *, run_cls=None,
        out_dir: Path = None, name: str = None) -> dict:
    """run_cls/out_dir/name: optional overrides for verification harnesses
    (default None = original behavior, byte-identical)."""
    run_cls = run_cls or P4Run
    out_dir = out_dir or OUT_DIR
    if name is None:
        name = f"smoke_{arm}_s{seed}.json" if SMOKE else f"{arm}_s{seed}.json"
    out = out_dir / name
    if out.exists():
        return json.loads(out.read_text())  # resumable
    t0 = time.perf_counter()
    r = run_cls(arm=arm, seed=seed, dump_tick=8 if SMOKE else DUMP_TICK)
    series = []
    agg = Counter()
    found_coops = []
    fb0 = None

    for t in range(2, ticks + 1):
        drive(r, seed, t, t)
        if t == 2:
            scale_world(r, TARGET_CITIZENS)
        s = r.state
        if fb0 is None:
            fb0 = s.foreign_balance
            money_delta(r)  # lock money baseline at the same point
            r._rf0 = dict(s.research_funding)  # research funding baseline
        for e in s.applied:
            if not isinstance(e, dict):
                continue
            a = e.get("action", "")
            if a.startswith("PRODUCE") and a != "PRODUCE_FAIL":
                agg["produced"] += 1
            elif a == "CITIZEN_DEATH":
                agg["deaths"] += 1
            elif a == "IMPORT_DONE":
                agg["imports"] += 1
                agg["import_units"] += e.get("qty", 0)
                agg["tariff_units"] += e.get("tariff", 0)
            elif a == "EXPORT_DONE":
                agg["exports"] += 1
                agg["export_units"] += e.get("qty", 0)
                agg["export_earnings"] += e.get("earnings", 0)
            elif a == "LAND_TAX":
                agg["lvt_units"] += e.get("amount", 0)
            elif a == "LAND_FORECLOSE":
                agg["foreclosures"] += 1
            elif a == "LAND_BOUGHT":
                agg["bought_n"] += 1
                agg["bought_units"] += e.get("price", 0)
            elif a == "LAND_SOLD":
                agg["sold_n"] += 1
                agg["sold_units"] += e.get("payout", 0)  # 90% buyback payout
            elif a == "SHOCK_START":
                agg["shock_" + e.get("kind", "?")] += 1
            elif a == "FOUND_COOP" and t > 2 and len(found_coops) < 200:
                found_coops.append({"tick": t, "sender": e.get("sender")})

        if t % 5 == 0 or t == ticks:
            unmet = sum(1 for u in s.unmet_needs.values()
                        if any(u.get(g) for g in ESSENTIALS))
            series.append([t, len(s.balances), gini(list(s.balances.values())),
                           unmet, int(s.surplus_pool), agg["produced"],
                           agg["deaths"], _inv_total(s, "bread"),
                           _inv_total(s, "grain"), int(s.foreign_balance)])

        s.applied.clear()
        r.batches.clear()
        if t % 50 == 0:
            trim_retention(r)

    s = r.state
    md = money_delta(r)
    dfb = s.foreign_balance - (fb0 or 0)
    drf = sum(s.research_funding.values()) - sum(r._rf0.values())
    trade_ok = (md + dfb + drf) == 0  # research bucket holds pooled money
    unmet_final = sum(1 for u in s.unmet_needs.values()
                      if any(u.get(g) for g in ESSENTIALS))
    res = {
        "arm": arm, "seed": seed, "ticks": ticks, "smoke": SMOKE,
        "wall_s": round(time.perf_counter() - t0, 1),
        "final": {
            "pop": len(s.balances), "unmet": unmet_final,
            "pool_units": int(s.surplus_pool),
            "gini": gini(list(s.balances.values())),
            "foreign_balance": int(s.foreign_balance),
            "bread_inv": _inv_total(s, "bread"),
            "grain_inv": _inv_total(s, "grain"),
            "produced": agg["produced"], "deaths": agg["deaths"],
            "found_late": len(found_coops),
        },
        "trade": {k: agg[k] for k in (
            "imports", "import_units", "tariff_units", "exports",
            "export_units", "export_earnings")},
        "land": {k: agg[k] for k in ("lvt_units", "foreclosures", "bought_n",
                                     "bought_units", "sold_n", "sold_units")},
        "shocks": {k: v for k, v in agg.items() if k.startswith("shock_")},
        "series": series,
        "money_delta": md, "d_foreign": dfb, "d_research": drf,
        "trade_ok": trade_ok,
        "trader_funding": N_TRADERS * TRADER_BALANCE,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, indent=2, sort_keys=True))
    return res


if __name__ == "__main__":
    arm = sys.argv[1] if len(sys.argv) > 1 else "trade_only"
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 42
    ticks = int(sys.argv[3]) if len(sys.argv) > 3 else (12 if SMOKE else 650)
    res = run(arm, seed, ticks)
    print(json.dumps(res, sort_keys=True), flush=True)
