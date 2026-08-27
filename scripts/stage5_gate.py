#!/usr/bin/env python
"""Stage 5 gate: shocks, growth, research (spec 2026-08-26, plan lines 39-43).

Four criteria:
  1. Capital ratchet closed <= 50 ticks, all seeds (forced-zero machines).
  2. Escalating battery x >=2 seeds: honest breaking-tier report; below
     break, essentials recover <= 100 ticks; money invariant exact.
  3. Demographics: peaceful growth absorbed; children mature; deaths (if
     any) absorbed; money invariant exact.
  4. Research: budgets track injected signals; delegation changes
     outcomes; the votable tap follows algorithm edits.

Usage: stage5_gate.py [ticks] [seed ...]
"""
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "dashboard"))

from server import Run  # noqa: E402
from openboard import crisis as C  # noqa: E402
from openboard.research import (  # noqa: E402
    effective_allocation,
    fund_pool_phase,
    propose_allocation,
)

ESSENTIALS = ("bread", "water", "electricity", "meals")
FIELDS = ("food", "health", "energy", "infrastructure", "computing")


def drive(run, seed, t0, t1):
    """Drive the world tick by tick with the live bot set."""
    for t in range(t0, t1 + 1):
        actions = []
        for name, meta in sorted(run.bots.items()):
            rng = random.Random(f"{seed}:{t}:{name}")
            actions.extend(
                meta["fn"](name, run.state, run.state.active_ruleset_params(), t, rng)
            )
        run._apply_batch(t, actions)


def money_delta(run):
    """0 when money is conserved exactly. Captures the genesis total on
    first call (world size must not be hardcoded - the founding world
    has ~162 citizens) and checks total == genesis_total + minted - retired."""
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
    expected = run._money0 + s.money_minted - s.money_retired
    return total - expected


def unmet_essentials(state):
    """Living citizens with any essential unmet right now."""
    return sum(
        1
        for un in state.unmet_needs.values()
        if any(un.get(g) for g in ESSENTIALS)
    )


# ------------------------------------------------------------- criterion 1


def criterion_1_ratchet(seeds):
    """Ratchet closed <= 50 ticks, all seeds (forced-zero machines)."""
    all_ok = True
    for seed in seeds:
        run = Run(seed=seed)
        drive(run, seed, 2, 302)
        s = run.state
        coop = s.coops["miners"]
        primary = coop.get("recipe_intent") or coop.get("trade")
        coop["inventory"]["machines"] = 0
        delivered = produced = 0
        for t in range(303, 303 + 51):
            pre = len(s.applied)
            drive(run, seed, t, t)
            for e in s.applied[pre:]:
                if (
                    e.get("action") == "PRODUCER_INPUT_CLEAR"
                    and e.get("good") == "machines"
                    and any(x.get("coop_id") == "miners" for x in e.get("served", []))
                ):
                    delivered += sum(x["qty"] for x in e["served"] if x.get("coop_id") == "miners")
                if (
                    e.get("action") == "PRODUCE"
                    and e.get("coop_id") == "miners"
                    and e.get("recipe_id") == primary
                ):
                    produced += 1
        ok = delivered > 0 and produced > 0
        all_ok = all_ok and ok
        print(
            f"  seed {seed}: delivered={delivered} primary_runs={produced}"
            f" -> {'OK' if ok else 'FAIL'}"
        )
    return all_ok


# ------------------------------------------------------------- criterion 2


def criterion_2_battery(seeds, ticks=1250):
    """Escalating battery x2 seeds: essentials recover <=100 ticks post-shock,
    money invariant exact every tick. Report the worst essential streak —
    the honest map of where the society breaks."""
    all_ok = True
    for seed in seeds:
        run = Run(seed=seed)
        run.state.rulesets[0]["params"]["shocks"] = {
            "enabled": True,
            "profile": "battery",
        }
        run.state.rulesets[0]["params"]["crisis"] = {"enabled": True}
        drive(run, seed, 2, 302)  # healthy baseline
        inv_bad = 0
        streak = worst_streak = 0
        for t in range(303, 303 + ticks):
            drive(run, seed, t, t)
            if unmet_essentials(run.state) > 0:
                streak += 1
                worst_streak = max(worst_streak, streak)
            else:
                streak = 0
            if money_delta(run) != 0:
                inv_bad += 1
        # recovery criterion: after any essential outage, recovery within
        # 100 ticks means no streak exceeds 100
        ok = inv_bad == 0 and worst_streak <= 100
        all_ok = all_ok and ok
        tier = min(4, ticks // 250)
        names = ["mild", "moderate", "severe", "extreme", "fatal"]
        print(
            f"  seed {seed}: worst_streak={worst_streak} inv_bad={inv_bad}"
            f" (battery through tier '{names[tier]}')"
            f" -> {'OK' if ok else 'BREAK-REPORT'}"
        )
    return all_ok


# ------------------------------------------------------------- criterion 3


def criterion_3_demographics(seed, ticks=1500):
    """Peaceful growth absorbed; children mature; invariant exact."""
    run = Run(seed=seed)
    s = run.state
    s.rulesets[0]["params"]["demographics"] = {
        "enabled": True,
        "birth_interval_ticks": 400,
        "adulthood_ticks": 600,
        "child_need_pct": 50,
    }
    drive(run, seed, 2, 302)
    pop0 = len(s.balances)
    inv_bad = 0
    for t in range(303, 303 + ticks):
        drive(run, seed, t, t)
        if money_delta(run) != 0:
            inv_bad += 1
    born = sum(1 for e in s.applied if e.get("action") == "CITIZEN_BORN")
    matured = sum(1 for e in s.applied if e.get("action") == "CITIZEN_ADULT")
    deaths = sum(1 for e in s.applied if e.get("action") == "CITIZEN_DEATH")
    expected_births = ticks // 400
    ok = born >= expected_births and matured >= 1 and inv_bad == 0
    print(
        f"  seed {seed}: pop {pop0} -> {len(s.balances)} (born {born}>= {expected_births},"
        f" matured {matured}, deaths {deaths}) inv_bad={inv_bad}"
        f" -> {'OK' if ok else 'FAIL'}"
    )
    return ok


# ------------------------------------------------------------- criterion 4


def criterion_4_research(seed):
    """Budgets track signals; delegation changes outcomes; edits change taps."""
    run = Run(seed=seed)
    s = run.state
    drive(run, seed, 2, 202)
    base = propose_allocation(s, s.active_ruleset_params())

    # (a) famine signal shifts food share up
    for c in s.balances:
        s.unmet_needs[c] = {"bread": True}
    famine = propose_allocation(s, s.active_ruleset_params())
    signal_ok = famine["food"] > base["food"]
    for c in s.balances:
        s.unmet_needs[c] = {}

    # (b) delegation raises health weight
    algo = {f: 2000 for f in FIELDS}
    solo = effective_allocation(
        {"expert": {"health": 100}}, {}, algo, ["expert", "a", "b"]
    )
    delegated = effective_allocation(
        {"expert": {"health": 100}},
        {"a": "expert", "b": "expert"},
        algo,
        ["expert", "a", "b"],
    )
    deleg_ok = delegated["health"] > solo["health"]

    # (c) the votable tap follows edits: 5% vs 10% of the same surplus
    params = {"research": {"enabled": True, "research_share_bp": 500}}
    s.surplus_pool = 10_000
    tap_5 = fund_pool_phase(s, 300, params)[0]["amount"]
    s.surplus_pool = 10_000
    params["research"]["research_share_bp"] = 1000
    tap_10 = fund_pool_phase(s, 301, params)[0]["amount"]
    edit_ok = tap_10 > tap_5

    ok = signal_ok and deleg_ok and edit_ok
    print(
        f"  signals food {base['food']}->{famine['food']} ({'OK' if signal_ok else 'FAIL'}),"
        f" delegation health {solo['health']}->{delegated['health']} ({'OK' if deleg_ok else 'FAIL'}),"
        f" tap {tap_5}->{tap_10} ({'OK' if edit_ok else 'FAIL'})"
    )
    return ok


# -------------------------------------------------------------------- main


def main():
    ticks = int(sys.argv[1]) if len(sys.argv) > 1 else 1250
    seeds = tuple(int(a) for a in sys.argv[2:]) or (42, 7, 123)
    print("Stage 5 gate: democracy under fire")
    print("[1] capital ratchet <= 50 ticks, all seeds")
    ok1 = criterion_1_ratchet(seeds)
    print("[4] research signals + delegation + edits")
    ok4 = criterion_4_research(42)
    print("[3] demographics absorbed")
    ok3 = criterion_3_demographics(42, ticks=1500)
    print("[2] escalating shock battery x2 seeds")
    ok2 = criterion_2_battery(seeds[:2], ticks=ticks)
    verdict = ok1 and ok2 and ok3 and ok4
    print(f"GATE: {'PASS' if verdict else 'FAIL'} (ratchet={ok1} battery={ok2} demo={ok3} research={ok4})")
    return 0 if verdict else 1


if __name__ == "__main__":
    sys.exit(main())
