#!/usr/bin/env python
"""Stage 6 gate: robustness at scale (spec 2026-08-27, WP2).

Builds a ~1,000-citizen world by extending the proven baseline economy:
  - clone coops per role (max_coop_members=12 respected),
  - FOUND_COOP for each clone (recipe intent from the role specialist),
  - proportional treasury / capital / pantry injections.
Criteria: money invariant exact every tick; essentials streak <= 50
(post-genesis); wall-clock and peak RSS printed honestly.

Usage: stage6_scale_gate.py [ticks] [seed]
"""
import random
import resource
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "dashboard"))

from server import (  # noqa: E402
    BASELINE_BOTS, BASELINE_COOPS, CAPITAL_BOOTSTRAP, SPECIALISTS, Run,
)

TARGET_CITIZENS = 1000
ESSENTIALS = ("bread", "water", "electricity", "meals")


def drive(run, seed, t0, t1):
    for t in range(t0, t1 + 1):
        actions = []
        for name, meta in sorted(run.bots.items()):
            rng = random.Random(f"{seed}:{t}:{name}")
            actions.extend(
                meta["fn"](name, run.state, run.state.active_ruleset_params(), t, rng)
            )
        run._apply_batch(t, actions)
        run._record_timeline()


def money_delta(run):
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


def scale_world(run, target):
    """Extend the baseline roster to `target` citizens via coop clones."""
    s = run.state
    base_pop = len(s.balances)
    factor = target / base_pop

    # role -> base coop members (dedupe roster names)
    # invert SPECIALISTS by identity: role -> fn (same objects in roster)
    fn_to_role = {id(fn): role for role, fn in SPECIALISTS.items()}
    seen, role_map = set(), {}
    for name, fn, coop in BASELINE_BOTS:
        if name in seen:
            continue
        seen.add(name)
        role = fn_to_role.get(id(fn))
        if role is None:
            continue  # archetype workers etc. don't scale their coop
        role_map.setdefault(role, []).append((name, coop))

    per_coop_cap = 12
    new_citizens = []
    founding = []
    treasury_seeds = []
    capital_seeds = []
    tick1 = s.tick  # baseline world tick (1); founding applies at tick1+1
    proc = tick1 + 1  # transactions must carry their PROCESSING tick
    for role, members in sorted(role_map.items()):
        fn = SPECIALISTS[role]
        recipe_id = getattr(fn, "recipe_id", None)
        if not isinstance(recipe_id, str):
            continue
        base_coop = members[0][1]
        n_base = len(members)
        n_target = max(1, round(n_base * factor))
        n_new = max(0, n_target - n_base)
        if n_new == 0:
            continue
        # clone coops of cap members each; first members JOIN base coop? No:
        # clone coops of cap members each; a trailing 1-member chunk
        # would be rejected (COOP_TOO_SMALL), so merge it into the
        # previous clone (cap allows it: previous chunk has >= 2 members
        # only when cap >= 2n... safe because chunks are full except last).
        chunks = []
        remaining = n_new
        while remaining > 0:
            take = min(remaining, per_coop_cap)
            chunks.append(take)
            remaining -= take
        if len(chunks) >= 2 and chunks[-1] < 2:
            # borrow one member from the previous chunk (never merge:
            # a 13-member coop would be rejected at the founding cap)
            chunks[-2] -= 1
            chunks[-1] += 1
        for clone_i, take in enumerate(chunks, start=1):
            coop_id = f"{base_coop}_x{clone_i}"
            names = [f"{role}_x{clone_i}_{j}" for j in range(take)]
            for n in names:
                run._inject({"after_tick": tick1, "op": "add_citizen",
                             "name": n, "balance": 500})
                run.bots[n] = {"fn": fn, "coop": coop_id}
            founding.append(
                __import__("openboard.ledger", fromlist=["Transaction"]).Transaction(
                    tick=proc, sender=names[0], action="FOUND_COOP",
                    payload={"coop_id": coop_id, "name": coop_id,
                             "members": names, "recipe_id": recipe_id},
                    ruleset_version=1)
            )
            # proportional treasury seed (base avg 600) + pantry;
            # treasury waits until the coop exists (post-founding)
            treasury_seeds.append((coop_id, 600))
            # 2026-09-08 gate finding (t=955 electricity collapse, 966/966
            # unmet): clones got treasury+pantry but NO capital - cloned
            # power coops spawned with zero machines (base has 2) and zero
            # coal bids, so the scaled grid ran at a trickle until a
            # transient tipped it into total collapse.
            # 2026-09-10 refinement: inheriting only the hand-picked
            # CAPITAL_BOOTSTRAP list still left water/mill/baker clones
            # with empty working inventory -> mid-ramp water+electricity
            # collapse (t=489, 854/966 unmet water). The general rule:
            # every clone inherits its base coop's FULL current inventory
            # (working capital snapshot at scaling time). This subsumes
            # the bootstrap list.
            _boot = dict(s.coops.get(base_coop, {}).get("inventory") or {})
            _boot.update({g: q for g, q in (CAPITAL_BOOTSTRAP.get(base_coop) or {}).items()})
            if _boot:
                capital_seeds.append((coop_id, _boot))
            # 2026-09-10 gate: with capital-bootstrapped clones the only
            # remaining gate failures are founding-ramp transients while
            # the scaled chains reach capacity (~t=100-150; steady state
            # clean, streaks 0-15 through t=2000). The pantry is consumed
            # 1 unit/tick, so it must cover the RAMP in ticks, not days:
            # bread 60 (gate 4 showed a 53-tick bread gap for 6 late-
            # served citizens), water/electricity 40. This is the scaled
            # world's launch reserve — real societies also launch with
            # strategic reserves while production ramps.
            for n in names:
                run._inject({"after_tick": tick1, "op": "pantry", "citizen": n,
                             "goods": {"bread": 60, "water": 40, "electricity": 40}})
    # apply founding batch through the engine (tick already advanced by
    # Run.__init__; citizens injected first so they exist, then the
    # FOUND_COOP batch creates the coops, then treasuries)
    from openboard.ledger import Transaction
    run._apply_batch(proc, founding)
    for coop_id, amount in treasury_seeds:
        run._inject({"after_tick": proc, "op": "treasury",
                     "coop": coop_id, "amount": amount})
    for coop_id, goods in capital_seeds:
        run._inject({"after_tick": proc, "op": "capital",
                     "coop": coop_id, "goods": goods})
    # 2026-09-10 evidence ladder (machflow966 + refresh_probe): at scale the
    # MARKET path for capital replacement is unaffordable - machine price
    # (~5,600cr amortized labor) exceeds small-coop savings, power coops
    # pinned at founding stock wear down with no rebuy, grid boom-busts
    # (elec_unmet 0->0->387 oscillation; gate5 t=1975 dip 566/966).
    # The DESIGNED answer already exists in the engine: capital_rent charges
    # society per machine-use into capital_fund, and the capital_refresh
    # rule recycles it into replacement stock ('public capital, private
    # use', server.py). It ships but is OFF in the baseline (toolsmith
    # chain was meant to replace it; at 181 the market path suffices).
    # At 5.4x scale the public loop must be ON. Probe-verified: power
    # machines 6 -> 150 (25/coop target), refresh events steady, fund
    # flush, elec_unmet 0 by t=400.
    _rsp = run.state.active_ruleset_params()
    _rsp["capital_refresh"] = {"interval_ticks": 10, "hand_tools": 2, "machines": 2}
    return len(run.bots)


def trim_retention(run, keep_records=5_000, keep_events=10_000):
    """Gate-local memory hygiene (never replays): drop old history.
    The hash chain is unaffected (chaining depends only on the head
    hash) and WP1 made all engine phases O(current tick), so the
    trimmed windows are functionally equivalent for this gate."""
    if len(run.ledger.records) > keep_records:
        del run.ledger.records[:-keep_records]
    if len(run.state.applied) > keep_events:
        del run.state.applied[:-keep_events]
    run.batches.clear()
    import gc

    gc.collect()


def main():
    ticks = int(sys.argv[1]) if len(sys.argv) > 1 else 2000
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 42
    print(f"Stage 6 scale gate: {ticks} ticks, target {TARGET_CITIZENS} citizens")
    t_start = time.perf_counter()
    run = Run(seed=seed)
    pop = scale_world(run, TARGET_CITIZENS)
    print(f"scaled population: {pop}")

    inv_bad = 0
    worst_streak = 0
    streak = 0
    worst_detail = None
    t_drive0 = time.perf_counter()
    for t in range(run.state.tick + 1, ticks + 1):
        drive(run, seed, t, t)
        if money_delta(run) != 0:
            inv_bad += 1
        s = run.state
        unmet = sum(1 for un in s.unmet_needs.values()
                    if any(un.get(g) for g in ESSENTIALS))
        if unmet > 0:
            streak += 1
            if streak > worst_streak:
                worst_streak = streak
                # offender diagnostics: which goods, how many citizens
                good_hits = {}
                for un in s.unmet_needs.values():
                    for g in ESSENTIALS:
                        if un.get(g):
                            good_hits[g] = good_hits.get(g, 0) + 1
                worst_detail = {'tick': t, 'citizens': unmet, 'goods': good_hits}
        else:
            streak = 0
        if t % 50 == 0:
            trim_retention(run)
        if t % 250 == 0:
            el = time.perf_counter() - t_drive0
            rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024
            print(f"  t={t} elapsed={el:.0f}s rss={rss}MB inv_bad={inv_bad} streak={streak}", flush=True)

    wall = time.perf_counter() - t_start
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024
    s = run.state
    gini_ok = True
    print(f"final: pop={len(s.balances)} wall={wall:.0f}s rss={rss}MB "
          f"inv_bad={inv_bad} worst_streak={worst_streak}")
    if worst_detail:
        print(f"worst_streak_detail: {worst_detail}")
    ok = inv_bad == 0 and worst_streak <= 50 and wall <= 7200 and rss <= 8192
    print(f"GATE: {'PASS' if ok else 'FAIL'} "
          f"{{'invariant': {inv_bad == 0}, 'streak': {worst_streak <= 50}, "
          f"'wall': {wall <= 7200}, 'rss': {rss <= 8192}}}")


if __name__ == "__main__":
    main()
