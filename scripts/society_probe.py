#!/usr/bin/env python3
"""Society in Motion study (spec 2026-09-13): lever interactions + sequencing
+ society trajectories.

17 arms x 3 seeds (7/42/123), 650 ticks, 1000 citizens. One cell per process,
resumable JSON under sweeps/society/<arm>_s<seed>.json. ALWAYS launch via
scripts/memrun.sh (project safety rule), one world at a time.

Arm registry (arm -> config deltas on the shared healthy base world):

  Part A pair1 (Spoilage-long x Disasters)
    base            plain healthy world (equal scenario defaults)
    spoil_long      + perishability, LONG shelf lives 14-30 ticks (below)
    disaster        + shocks profile 'harsh' (P3 disaster arm config)
    spoil_disaster  both
  Part A pair2 (Skills x Research fixed+floor)
    base2           plain healthy world
    skills_on       + skills (P2 mechanics: +5%/lvl out, +3%/lvl wage, cap 5)
    research_fixed  + research share 250bp, reserve_floor 1_000_000_000
                    (sweeps/p4fix config)
    skills_research both
  Part A pair3 (Wealth tax 800bp x Land dump)
    base3           plain healthy world (equal default wealth tax 400bp)
    tax800          wealth_tax rate_bp 800 (threshold untouched; unequal_rerun
                    rate-override mechanics on the healthy base world)
    land_dump       land market ON + pool-funded monopolist buys ALL parcels
                    at t=2 and dumps the portfolio at t=60 (land_study dump)
    tax_dump        both
  Part B research timing (EXACT p4_probe all_on config + reserve_floor 1B)
    research_early  research.start_tick = 50
    research_late   research.start_tick = 400
    research_never  research disabled (all_on minus the research rule)
  Part B crisis timing (P2 crisis arm config, identical shock streams)
    crisis_onset    pre-ratified crises declared at ticks 100/300/500
    crisis_late100  declared at ticks 200/400/600 (100 ticks after onset)
    (crisis-never baseline = existing sweeps/p2/crisis_off_*.json, NOT rerun)

Shock streams: the engine re-seeds the shock RNG per tick from the world seed
(random.Random(f"{seed}:{tick}"), P3 FINDINGS), so all cells of one seed see
byte-identical exogenous streams. Within-seed pairing is the chaos rule.

SOCIETY TIMELINE (the core new feature): snapshot at t=2 (baseline), every 50
ticks, and final. Per snapshot, deterministic ints (null only when the engine
has no source yet):
  t, unmet, unmet_streak_max      citizens with any unmet essential; longest
                                  unmet streak so far (run-cumulative)
  top1_bp / mid60_bp / bot20_bp   wealth shares of citizen balances
  bread_px                        real market clearing price of bread
                                  (state.last_clearing['bread']; fallback
                                  good_cost_baseline only before the first
                                  bread clearing ever)
  bread_idx                       bread_px * 100 // base_px (t=2 = 100)
  wage                            median wage per WORK tx this tick, units
                                  (credits * upc; median = sorted[n//2];
                                  carried forward when a tick has no WORK tx)
  real_wage                       wage // bread_px
  div_pp                          last citizen dividend per head (units;
                                  SURPLUS_SPEND kind=dividend per_citizen,
                                  carried forward; 0 before the first payout)
  top_coop_bp                     largest coop treasury share of private
                                  money (balances + treasuries), bp
  ev_*                            events since last snapshot: foreclosures
                                  (LAND_FORECLOSE), foundings (FOUND_COOP),
                                  insolvencies (WAGE_DEBT_ASSUMED), crisis
                                  declarations (CRISIS_START/CRISIS_AUTO),
                                  shock starts, citizen deaths

Conservation: extended money identity money_delta + d_foreign + d_research
== 0 exact (foreign bucket only exists on p4-based arms; research buckets
only on research arms — all zero elsewhere). money_delta covers balances +
pool + capital_fund + innovation_pool + coop treasuries.

Usage: society_probe.py ARM SEED [ticks]   (ticks default 650, 12 in SMOKE)
Env:   SMOKE=1 -> 12 ticks, 80 citizens (wiring check)
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

import p4_probe  # noqa: E402
from server import Run  # noqa: E402
from stage6_scale_gate import (  # noqa: E402
    ESSENTIALS, drive, money_delta, scale_world, trim_retention,
)
from openboard.crisis import declare_crisis  # noqa: E402
from openboard.ledger import Transaction  # noqa: E402
from openboard.metrics import gini  # noqa: E402

OUT_DIR = ROOT / "sweeps" / "society"
TARGET_CITIZENS = 1000
SMOKE = os.environ.get("SMOKE") == "1"
if SMOKE:
    TARGET_CITIZENS = 80

# ---------------- lever params (verbatim from proven probes) ----------------
# Part A pair1: LONG shelf lives 14-30 ticks (P3 proved 2-10 = instant famine;
# P4 used week-scale 7-28). Deterministic per-good values:
SHELF_LIFE_LONG = {"bread": 21, "milk": 14, "meat": 21, "eggs": 28,
                   "cheese": 30, "fruit": 21, "vegetables": 21,
                   "meals": 14, "fish": 14}
SHOCKS_PARAMS = {"enabled": True, "profile": "harsh"}   # P2/P3 harsh profile
SKILLS_PARAMS = {"enabled": True, "hours_per_level": 100, "max_level": 5,
                 "output_bonus_bp": 500, "wage_bonus_bp": 300}  # P2
RESEARCH_FIXED = {"enabled": True, "research_share_bp": 250,
                  "reserve_floor": 1_000_000_000}       # sweeps/p4fix
LAND_PARAMS = {"enabled": True, "base_land_price": 500,
               "land_tax_bp": 1, "grace_ticks": 5}      # land_study
CRISIS_PARAMS = {"enabled": True, "max_ticks": 100}     # P2
TAX800_BP = 800                                         # pair3
DUMP_TICK = 60                                          # land_study
MONO_BALANCE = 1_200_000                                # land_study

# Part B research timing on the EXACT p4 all_on config + floor 1B:
RESERVE_FLOOR = 1_000_000_000
START_EARLY = 50
START_LATE = 400

# P2 crisis_on declared at 100/300/500; late arm 100 ticks after each onset.
# SMOKE compresses to ticks 5/7 so the declaration path is exercised.
CRISIS_ONSET_TICKS = (5,) if SMOKE else (100, 300, 500)
CRISIS_LATE_TICKS = (7,) if SMOKE else (200, 400, 600)

ARMS = {
    # ---- Part A pair1: spoilage-long x disasters
    "base":            {},
    "spoil_long":      {"perish": True},
    "disaster":        {"shocks": True},
    "spoil_disaster":  {"perish": True, "shocks": True},
    # ---- Part A pair2: skills x research(fixed+floor)
    "base2":           {},
    "skills_on":       {"skills": True},
    "research_fixed":  {"research": True},
    "skills_research": {"skills": True, "research": True},
    # ---- Part A pair3: tax800 x land dump
    "base3":           {},
    "tax800":          {"tax800": True},
    "land_dump":       {"land": True},
    "tax_dump":        {"tax800": True, "land": True},
    # ---- Part B: research timing (p4 all_on config + floor 1B)
    "research_early":  {"p4": True, "start_tick": START_EARLY},
    "research_late":   {"p4": True, "start_tick": START_LATE},
    "research_never":  {"p4": True, "never": True},
    # ---- Part B: crisis timing (P2 crisis config, harness-declared)
    "crisis_onset":    {"shocks": True, "crisis": True,
                        "crisis_ticks": CRISIS_ONSET_TICKS},
    "crisis_late100":  {"shocks": True, "crisis": True,
                        "crisis_ticks": CRISIS_LATE_TICKS},
}


class SocietyRun(Run):
    """Part A + crisis-timing arms. Arm params via _params (genesis
    injection); land-monopolist and crisis declarations via _apply_batch
    (the one hook that always fires under drive())."""

    def __init__(self, arm: str, dump_tick: int | None = None, **kw):
        self.arm = arm
        self.dump_tick = dump_tick if dump_tick is not None \
            else (8 if SMOKE else DUMP_TICK)
        self.mono_injected = False
        self.declared = {}
        super().__init__(scenario="equal", **kw)

    def _params(self):
        p = super()._params()
        cfg = ARMS[self.arm]
        if cfg.get("perish"):
            p["perishability"] = {"enabled": True,
                                  "shelf_life": dict(SHELF_LIFE_LONG)}
        if cfg.get("shocks"):
            p["shocks"] = dict(SHOCKS_PARAMS)
        if cfg.get("skills"):
            p["skills"] = dict(SKILLS_PARAMS)
        if cfg.get("research"):
            p["research"] = dict(RESEARCH_FIXED)
        if cfg.get("land"):
            p["land_market"] = dict(LAND_PARAMS)
        if cfg.get("tax800"):
            # unequal_rerun mechanics: override ONLY the rate (a share,
            # unit-free). The threshold was already upc-scaled in super()._params()
            # — overwriting it would re-break the fixed-supply unit-scale fix.
            p["wealth_tax"]["rate_bp"] = TAX800_BP
        if cfg.get("crisis"):
            p["shocks"] = dict(SHOCKS_PARAMS)
            p["crisis"] = dict(CRISIS_PARAMS)
        return p

    def _apply_batch(self, tick, batch):
        cfg = ARMS[self.arm]
        s = self.state
        if cfg.get("land") and tick == 2 and not self.mono_injected:
            self.mono_injected = True
            # no-mint funding: recorded add_citizen injection takes the
            # stake out of the Society Pool (conservation intact)
            self._inject({"after_tick": 2, "op": "add_citizen",
                          "name": "monopolist", "balance": MONO_BALANCE})
            for pid in sorted(s.land_parcels.keys()):
                batch.append(Transaction(
                    tick=tick, sender="monopolist", action="BUY_LAND",
                    payload={"pid": pid}, ruleset_version=1))
        if (cfg.get("land") and tick == DUMP_TICK and self.mono_injected):
            for pid in sorted(s.land_parcels.keys()):
                if (s.land_parcels[pid] or {}).get("owner") == "monopolist":
                    batch.append(Transaction(
                        tick=tick, sender="monopolist", action="SELL_LAND",
                        payload={"pid": pid}, ruleset_version=1))
        if (cfg.get("crisis") and tick in cfg["crisis_ticks"]
                and not self.declared.get(tick)):
            self.declared[tick] = True
            declare_crisis(s, tick, "pandemic", "vote")  # pre-ratified (P2)
        super()._apply_batch(tick, batch)


class ResearchTimingRun(p4_probe.P4Run):
    """Part B research-timing arms: the EXACT p4 all_on config + reserve
    floor 1B + optional start_tick; never = research disabled."""

    def _params(self):
        p = super()._params()          # all_on extras incl. research 250bp
        if ARMS[self.arm].get("never"):
            p["research"] = {"enabled": False}
        else:
            p["research"] = dict(p4_probe.RESEARCH_PARAMS)
            p["research"]["reserve_floor"] = RESERVE_FLOOR
            p["research"]["start_tick"] = ARMS[self.arm]["start_tick"]
        return p


# ------------------------------------------------------------ society metrics


def _wealth_shares(balances) -> tuple[int, int, int]:
    """(top1_bp, mid60_bp, bot20_bp) of citizen balances, deterministic int
    bp. Buckets: top k1 = max(1, n//100); bottom k20 = max(1, n*20//100);
    middle = the rest. All-zero world => 0s."""
    bals = sorted(balances, reverse=True)
    n = len(bals)
    if n == 0:
        return 0, 0, 0
    k1 = max(1, n // 100)
    k20 = max(1, n * 20 // 100)
    tot = sum(bals)
    if tot <= 0:
        return 0, 0, 0
    top = sum(bals[:k1]) * 10_000 // tot
    bot = sum(bals[n - k20:]) * 10_000 // tot
    return top, max(0, 10_000 - top - bot), bot


def run(arm: str, seed: int, ticks: int | None = None) -> dict:
    ticks = ticks if ticks is not None else (12 if SMOKE else 650)
    name = f"smoke_{arm}_s{seed}.json" if SMOKE else f"{arm}_s{seed}.json"
    out = OUT_DIR / name
    if out.exists():
        return json.loads(out.read_text())  # resumable
    cfg = ARMS[arm]
    t0 = time.perf_counter()
    if cfg.get("p4"):
        r = ResearchTimingRun(arm=arm, seed=seed,
                              dump_tick=8 if SMOKE else p4_probe.DUMP_TICK)
    else:
        r = SocietyRun(arm=arm, seed=seed)

    society: list[dict] = []
    series = []          # [t, pop, gini, unmet, pool, produced, deaths, bread_px]
    win = Counter()      # event counters since last snapshot
    produced = deaths = found_total = 0
    unmet_streak = unmet_streak_max = 0
    wage_last = None     # median wage carried forward across quiet ticks
    div_last = 0         # last dividend per head, carried forward
    base_px = None       # bread price index denominator (locked at t=2)
    wage_events: list[int] = []
    px = 0
    fb0 = None

    for t in range(2, ticks + 1):
        drive(r, seed, t, t)
        if t == 2:
            scale_world(r, TARGET_CITIZENS)
        s = r.state
        if fb0 is None:
            fb0 = s.foreign_balance
            money_delta(r)                # locks _money0 baseline
            r._rf0 = sum(s.research_funding.values())
            r._upc = int((s.active_ruleset_params().get("money_cap") or {})
                         .get("units_per_credit", 1)) or 1
        wage_events = []
        px = int(s.last_clearing.get("bread")
                 or s.good_cost_baseline.get("bread") or 0)
        for e in s.applied:
            if not isinstance(e, dict):
                continue
            a = e.get("action", "")
            if a == "WORK":
                wage_events.append(int(e.get("wage_credits", 0)))
            elif a == "SURPLUS_SPEND" and e.get("kind") == "dividend":
                div_last = int(e.get("per_citizen", 0))
            elif a == "LAND_FORECLOSE":
                win["foreclosures"] += 1
            elif a == "FOUND_COOP":
                win["found_coop"] += 1
                found_total += 1
            elif a == "WAGE_DEBT_ASSUMED":
                win["insolvencies"] += 1
            elif a in ("CRISIS_START", "CRISIS_AUTO"):
                win["crisis_declarations"] += 1
            elif a == "SHOCK_START":
                win["shock_starts"] += 1
            elif a == "CITIZEN_DEATH":
                win["deaths"] += 1
                deaths += 1
            elif a.startswith("PRODUCE") and a != "PRODUCE_FAIL":
                produced += 1

        unmet = sum(1 for u in s.unmet_needs.values()
                    if any(u.get(g) for g in ESSENTIALS))
        unmet_streak = unmet_streak + 1 if unmet > 0 else 0
        unmet_streak_max = max(unmet_streak_max, unmet_streak)

        # ---- society snapshot: baseline t=2, every 50 ticks, final
        if t == 2 or t % 50 == 0 or t == ticks:
            top1, mid60, bot20 = _wealth_shares(s.balances.values())
            if base_px is None:
                base_px = px or None      # t=0 reference for the price index
            bread_idx = (px * 100 // base_px) if (base_px and px) else None
            if wage_events:
                med = sorted(wage_events)[len(wage_events) // 2]
                wage_last = med * r._upc  # credits -> state units
            real_wage = (wage_last // px) \
                if (wage_last is not None and px > 0) else None
            treasury = sum(int(c.get("treasury", 0)) for c in s.coops.values())
            priv = sum(s.balances.values()) + treasury
            top_coop_bp = (max((int(c.get("treasury", 0))
                                for c in s.coops.values()), default=0)
                           * 10_000 // priv) if priv > 0 else 0
            society.append({
                "t": t, "pop": len(s.balances),
                "unmet": unmet, "unmet_streak_max": unmet_streak_max,
                "top1_bp": top1, "mid60_bp": mid60, "bot20_bp": bot20,
                "bread_px": px or None, "bread_idx": bread_idx,
                "wage": wage_last, "real_wage": real_wage,
                "div_pp": div_last, "top_coop_bp": top_coop_bp,
                "ev_foreclosures": win["foreclosures"],
                "ev_found_coop": win["found_coop"],
                "ev_insolvencies": win["insolvencies"],
                "ev_crisis_declarations": win["crisis_declarations"],
                "ev_shock_starts": win["shock_starts"],
                "ev_deaths": win["deaths"],
                "pool": int(s.surplus_pool),
            })
            win = Counter()
        if t % 5 == 0 or t == ticks:
            series.append([t, len(s.balances),
                           gini(list(s.balances.values())), unmet,
                           int(s.surplus_pool), produced, deaths, px])

        # memory hygiene (project safety rule)
        s.applied.clear()
        r.batches.clear()
        if t % 50 == 0:
            trim_retention(r)

    s = r.state
    md = money_delta(r)
    dfb = s.foreign_balance - (fb0 or 0)
    drf = sum(s.research_funding.values()) - r._rf0
    identity_ok = (md + dfb + drf) == 0   # extended conservation identity
    unmet_final = sum(1 for u in s.unmet_needs.values()
                      if any(u.get(g) for g in ESSENTIALS))
    res = {
        "arm": arm, "seed": seed, "ticks": ticks, "smoke": SMOKE,
        "wall_s": round(time.perf_counter() - t0, 1),
        "config": dict(cfg),
        "society": society,
        "series": series,
        "final": {
            "pop": len(s.balances), "unmet": unmet_final,
            "unmet_streak_max": unmet_streak_max,
            "pool_units": int(s.surplus_pool),
            "gini": gini(list(s.balances.values())),
            "foreign_balance": int(s.foreign_balance),
            "produced": produced, "deaths": deaths,
            "found_total": found_total,
            "crisis_state": dict(getattr(s, "crisis", None) or {}),
        },
        "money_delta": md, "d_foreign": dfb, "d_research": drf,
        "identity_ok": identity_ok,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, indent=2, sort_keys=True))
    return res


if __name__ == "__main__":
    arm = sys.argv[1] if len(sys.argv) > 1 else "base"
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 42
    ticks = int(sys.argv[3]) if len(sys.argv) > 3 else (12 if SMOKE else 650)
    if arm not in ARMS:
        print(f"unknown arm {arm!r}; valid: {', '.join(ARMS)}")
        sys.exit(2)
    res = run(arm, seed, ticks)
    print(json.dumps(res, sort_keys=True), flush=True)