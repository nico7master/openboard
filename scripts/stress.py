#!/usr/bin/env python
"""Deep stress harness: runs the baseline world N seeds x T ticks and
prints a diagnostic report (Gini path, savings, velocity, prices,
stockouts, flags). Usage: stress.py [ticks] [seed...]"""
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "dashboard"))

from server import Run  # noqa: E402
from openboard.metrics import gini  # noqa: E402


def run_world(seed: int, ticks: int):
    run = Run(seed=seed)
    gini_path, unmet_path = [], []
    price_spread = {g: [] for g in ("grain", "flour", "bread", "coal", "electricity", "water")}
    stockouts = {g: 0 for g in price_spread}
    for t in range(2, ticks + 1):
        actions = []
        for name, meta in sorted(run.bots.items()):
            rng = random.Random(f"{seed}:{t}:{name}")
            actions.extend(meta["fn"](name, run.state, run.state.active_ruleset_params(), t, rng))
        run._apply_batch(t, actions)
        run._record_timeline()
        s = run.state
        wealth = (list(s.balances.values()) + [s.surplus_pool, s.capital_fund]
                  + [c.get("treasury", 0) for c in s.coops.values()])
        gini_path.append(gini(wealth))
        unmet_path.append(sum(len(v) for v in s.unmet_needs.values()))
        for g in price_spread:
            cl = s.last_clearing.get(g)
            bl = s.good_cost_baseline.get(g)
            if cl is not None and bl:
                price_spread[g].append(cl - bl)
            world_stock = sum(c["inventory"].get(g, 0) for c in s.coops.values()) + sum(l["qty"] for l in s.listings.get(g, []))
            if world_stock <= 5:
                stockouts[g] += 1
    return run, gini_path, unmet_path, price_spread, stockouts


def main():
    ticks = int(sys.argv[1]) if len(sys.argv) > 1 else 2000
    seeds = [int(x) for x in sys.argv[2:]] or [42, 7, 123]
    for seed in seeds:
        run, gp, up, ps, so = run_world(seed, ticks)
        s = run.state
        n = len(gp)
        q = lambda arr, p: arr[min(n - 1, int(n * p))]  # quantile helper
        print(f"=== seed {seed} ({ticks} ticks) ===")
        print(f"gini: start={gp[0]/10000:.3f} mid={gp[n//2]/10000:.3f} end={gp[-1]/10000:.3f} max={max(gp)/10000:.3f}")
        print(f"unmet: end={up[-1]} max={max(up)} (last500max={max(up[-500:])})")
        print(f"balances: min={min(s.balances.values())} max={max(s.balances.values())} avg={sum(s.balances.values())//len(s.balances)}")
        print(f"savings rank: {dict(sorted(s.balances.items(), key=lambda kv: -kv[1])[:3])}")
        print(f"pool={s.surplus_pool} capital_fund={s.capital_fund} retired={s.money_retired} minted={s.money_minted}")
        for g, spreads in ps.items():
            if spreads:
                avg = sum(spreads) / len(spreads)
                print(f"price-floor {g}: avg={avg:+.1f} min={min(spreads)} max={max(spreads)} stockout_ticks={so[g]}")
        kinds = {}
        for f in s.flags:
            kinds[f["kind"]] = kinds.get(f["kind"], 0) + 1
        print(f"flags: {kinds}")
        print()


if __name__ == "__main__":
    main()
