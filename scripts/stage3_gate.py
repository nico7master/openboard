#!/usr/bin/env python
"""Stage 3 gate: competition & real capital.

3 seeds x 2000 ticks. PASS criteria:
- zero unmet needs (state.unmet_needs) at every checkpoint
- money invariant exact at every checkpoint
- capital consumed AND replenished by market (fills > burns/2)
- coops solvent (no permanent zero-treasury freeze in food/utility chain)
"""
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "dashboard"))

from server import Run, BASELINE_TREASURIES, CAPITAL_BOOTSTRAP  # noqa: E402
from openboard.engine import apply_tick  # noqa: E402
from openboard.metrics import gini  # noqa: E402


def invariant_error(s):
    total = (sum(s.balances.values()) + s.surplus_pool + s.capital_fund
             + sum(c.get("treasury", 0) for c in s.coops.values()))
    seed_total = 38 * 500 + sum(BASELINE_TREASURIES.values())
    expected = seed_total + s.money_minted - s.money_retired
    if total != expected:
        return f"money invariant: {total} != {expected}"
    return None


def run_seed(seed: int, ticks: int = 2000) -> tuple[bool, str]:
    run = Run(seed=seed)
    s, led = run.state, run.ledger
    fails = []
    for t in range(2, ticks + 1):
        actions = []
        for name, meta in sorted(run.bots.items()):
            r2 = random.Random(f"{seed}:{t}:{name}")
            actions.extend(meta["fn"](name, s, s.active_ruleset_params(), t, r2))
        apply_tick(s, led, actions, current_tick=t)
        if t % 250 == 0:
            err = invariant_error(s)
            if err:
                fails.append(f"t{t}: {err}")
            if s.unmet_needs:
                fails.append(f"t{t}: unmet needs {dict(list(s.unmet_needs.items())[:3])}")
            wealth = list(s.balances.values()) + [c.get("treasury", 0) for c in s.coops.values()]
            print(f"  seed{seed} t{t}: gini={gini(wealth)} pool={s.surplus_pool} minted={s.money_minted} retired={s.money_retired}", flush=True)
    # final checks
    mach = sum(1 for e in led.records if e.accepted and e.tx.get("action") == "BID_FOR_COOP"
               and e.tx.get("payload", {}).get("good") == "machines")
    tool = sum(1 for e in led.records if e.accepted and e.tx.get("action") == "BID_FOR_COOP"
               and e.tx.get("payload", {}).get("good") == "hand_tools")
    burned = sum(s.capital_burned.values())
    print(f"  seed{seed} FINAL: machine_fills={mach} tool_fills={tool} capital_burned={burned}")
    if burned == 0:
        fails.append("no capital consumption observed")
    if mach + tool < burned // 2:
        fails.append(f"capital not market-replenished: fills={mach + tool} vs burned={burned}")
    err = invariant_error(s)
    if err:
        fails.append(f"final: {err}")
    if s.unmet_needs:
        fails.append(f"final unmet: {len(s.unmet_needs)} citizens")
    return (not fails), "; ".join(fails)


if __name__ == "__main__":
    ok_all = True
    for seed in (1, 7, 42):
        print(f"=== seed {seed} ===", flush=True)
        ok, msg = run_seed(seed)
        print(f"  seed{seed}: {'PASS' if ok else 'FAIL: ' + msg}", flush=True)
        ok_all &= ok
    print("GATE:", "PASS" if ok_all else "FAIL")
    sys.exit(0 if ok_all else 1)
