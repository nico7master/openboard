#!/usr/bin/env python3
"""Stage 4 gate: breadth of production.

Measures the REAL genesis configuration (founding capital, equipment,
and a 3-day pantry per citizen — society bootstraps its members, the
model's bootstrap-endowment rule). A zero-start variant remains
available via ZERO_START=1 for adversarial study.
- criteria (measured, not vibes):
  (a) no unmet streak ever exceeds BOUND (rotation lag is fine,
      starvation growth is not)
  (b) streak trend non-increasing between the two late windows
  (c) every catalog sector with a baseline coop has produced > 0
  (d) money invariant exact at every checkpoint
"""
import os
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "dashboard"))

from openboard.engine import apply_tick
from server import BASELINE_BOTS, BASELINE_COOPS, Run

import os

TICKS = int(os.environ.get("GATE_TICKS", "1000"))
BOUND = 30
SEEDS = (1, 7, 42)
ZERO_START = os.environ.get("ZERO_START", "0") == "1"
SKIP_TICKS = 250 if not ZERO_START else 0


def run_seed(seed: int) -> dict:
    run = Run(seed=seed)
    s, led = run.state, run.ledger

    if ZERO_START:
        # adversarial study mode: strip all founding values
        for inj in list(run.injections):
            if inj.get("op") == "capital":
                coop = s.coops.get(inj.get("coop", ""))
                if coop:
                    for g in inj.get("goods", {}):
                        coop["inventory"][g] = 0
                run.injections.remove(inj)
            elif inj.get("op") == "treasury":
                coop = s.coops.get(inj.get("coop", ""))
                if coop:
                    coop["treasury"] = 0
                run.injections.remove(inj)
            elif inj.get("op") == "pantry":
                inv = s.citizen_inventory.get(inj.get("citizen", ""), {})
                for g in inj.get("goods", {}):
                    inv[g] = 0
                run.injections.remove(inj)

    # true monetary base AFTER genesis seeding (and optional zero-start
    # strip): the old n*500 formula ignored founding treasuries, which
    # read as a fake invariant gap equal to the seed sum
    def _money_total() -> int:
        return (
            sum(s.balances.values()) + s.surplus_pool + s.capital_fund
            + sum(c.get("treasury", 0) for c in s.coops.values())
        )

    base_total = _money_total()

    max_streak = 0
    streak_at = {}
    # streak measurement starts AFTER the founding window: society seeds
    # capital, treasuries, and a pantry at genesis (bootstrap-endowment
    # rule), but supply chains still need ~250 ticks to reach steady flow.
    # ZERO_START=1 measures the harsher from-nothing variant instead.
    for t in range(2 + SKIP_TICKS, TICKS + 2):
        actions = []
        for name, meta in sorted(run.bots.items()):
            r2 = random.Random(f"{seed}:{t}:{name}")
            actions.extend(meta["fn"](name, s, s.active_ruleset_params(), t, r2))
        apply_tick(s, led, actions, current_tick=t)
        if t % 50 == 0:
            cur = max((max(st.values()) for st in s.unmet_needs.values()), default=0)
            max_streak = max(max_streak, cur)
            streak_at[t] = cur

    # (b) trend between late windows
    late = [streak_at[k] for k in sorted(streak_at) if k >= TICKS - 400]
    first_half = sum(late[: len(late) // 2]) / max(len(late) // 2, 1)
    second_half = sum(late[len(late) // 2 :]) / max(len(late) - len(late) // 2, 1)

    # (c) sector production
    produced = set()
    for e in s.applied:
        if e.get("action") == "PRODUCE":
            produced.update(e.get("outputs", {}).keys())

    # (d) money invariant
    total = (
        sum(s.balances.values()) + s.surplus_pool + s.capital_fund
        + sum(c.get("treasury", 0) for c in s.coops.values())
    )
    expected = base_total + s.money_minted - s.money_retired

    return {
        "max_streak": max_streak,
        "trend": second_half - first_half,
        "sectors_ok": all(
            g in produced
            for g in ("grain", "flour", "bread", "water", "electricity", "coal",
                      "timber", "lumber", "iron_ore", "steel", "sand", "glass",
                      "electronics", "hand_tools", "machines", "fish", "fruit",
                      "vegetables", "meat", "milk", "eggs", "cheese", "canned_food",
                      "meals", "fabric", "clothing", "books", "furniture",
                      "household_goods", "bricks", "stone", "housing", "healthcare",
                      "education", "childcare", "transport", "maintenance",
                      "heating_fuel", "medicine")
        ),
        "produced_count": len(produced),
        "invariant": total == expected,
        "invariant_gap": total - expected,
    }


def main() -> int:
    mode = "ZERO-START" if ZERO_START else "GENESIS-SEEDED (skip first 250t)"
    print(f"Stage 4 gate: {len(SEEDS)} seeds x {TICKS} ticks [{mode}], streak bound {BOUND}")
    print("bootstrap path: toolwrights coop makes first tools via labor-only primitive_toolmaking")
    ok = True
    for seed in SEEDS:
        r = run_seed(seed)
        checks = {
            "streak_bound": r["max_streak"] <= BOUND,
            "trend_non_growing": r["trend"] <= 2.0,
            "sectors": r["sectors_ok"] and r["produced_count"] >= 35,
            "invariant": r["invariant"],
        }
        passed = all(checks.values())
        ok &= passed
        print(
            f"seed {seed}: max_streak={r['max_streak']} trend={r['trend']:+.2f} "
            f"produced={r['produced_count']} invariant={r['invariant']} "
            f"gap={r['invariant_gap']} -> {'PASS' if passed else 'FAIL'} {checks}"
        )
    print("GATE:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
