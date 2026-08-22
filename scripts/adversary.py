#!/usr/bin/env python
"""Stage 2: adversary lab — systematic attack matrix + seeded fuzzer.

Each attack runs against a fresh governance-live world with an attacker
citizen that has budget. After every tick the harness asserts the core
invariants (money conservation, no negative balances/stocks) and flags
anything accepted that should not have been.

Usage: adversary.py            # attack matrix
       adversary.py fuzz [n]   # n seeded fuzz ticks
"""
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "dashboard"))

from server import Run  # noqa: E402
from openboard.engine import apply_tick  # noqa: E402
from openboard.ledger import Transaction  # noqa: E402

FINDINGS: list[str] = []


def invariants_ok(s) -> str | None:
    for name, bal in s.balances.items():
        if bal < 0:
            return f"negative balance {name}={bal}"
    for cid, c in s.coops.items():
        if c.get("treasury", 0) < 0:
            return f"negative treasury {cid}"
        for good, qty in c.get("inventory", {}).items():
            if qty < 0:
                return f"negative coop stock {cid}.{good}={qty}"
    for cid, inv in s.citizen_inventory.items():
        for good, qty in inv.items():
            if qty < 0:
                return f"negative citizen stock {cid}.{good}={qty}"
    if s.surplus_pool < 0:
        return "negative surplus pool"
    total = (sum(s.balances.values()) + s.surplus_pool + s.capital_fund
             + sum(c.get("treasury", 0) for c in s.coops.values()))
    expected = 14 * 500 + 4 * 600 + s.money_minted - s.money_retired
    if total != expected:
        return f"money invariant broken: {total} != {expected}"
    return None


def run_attack(name: str, build_txs, ticks: int = 6, governance: bool = False):
    """Fresh world; attacker acts each tick via build_txs(tick, run)."""
    run = Run(seed=99, governance=governance)
    s, led = run.state, run.ledger
    for t in range(2, ticks + 1):
        txs = build_txs(t, run)
        apply_tick(s, led, txs, current_tick=t)
        bad = invariants_ok(s)
        if bad:
            FINDINGS.append(f"{name}: {bad} (tick {t})")
            return
    print(f"  ok  {name}")


def tx(t, who, action, payload, version):
    return Transaction(tick=t, sender=who, action=action, payload=payload,
                       ruleset_version=version)


def attack_matrix():
    print("=== attack matrix (each = fresh world, invariants asserted per tick) ===")

    def mk(t, who="worker_a"):
        return tx(t, who, "WORK", {"coop_id": "farmers", "hours": 8}, 1)

    # 1) WORK payload abuse
    for hours, label in ((0, "zero"), (-5, "negative"), (10**9, "huge"), ("8", "string"), (None, "null"), (8.5, "float")):
        run_attack(f"WORK hours={label}", lambda t, run, h=hours: [
            tx(t, "worker_a", "WORK", {"coop_id": "farmers", "hours": h}, 1)])
    run_attack("WORK unknown coop", lambda t, run: [
        tx(t, "worker_a", "WORK", {"coop_id": "ghost", "hours": 8}, 1)])
    run_attack("WORK 50x same tick", lambda t, run: [
        tx(t, "worker_a", "WORK", {"coop_id": "farmers", "hours": h % 8 + 1}, 1)
        for h in range(50)])

    # 2) TRANSFER abuse
    run_attack("TRANSFER negative", lambda t, run: [
        tx(t, "worker_a", "TRANSFER", {"to": "worker_b", "amount": -100}, 1)])
    run_attack("TRANSFER overspend 3x", lambda t, run: [
        tx(t, "worker_a", "TRANSFER", {"to": w, "amount": 400}, 1)
        for w in ("worker_b", "baker_a", "miner_a")])
    run_attack("TRANSFER unknown recipient", lambda t, run: [
        tx(t, "worker_a", "TRANSFER", {"to": "ghost", "amount": 10}, 1)])
    run_attack("TRANSFER self wash", lambda t, run: [
        tx(t, "worker_a", "TRANSFER", {"to": "worker_a", "amount": 10}, 1)])
    run_attack("TRANSFER to coop id", lambda t, run: [
        tx(t, "worker_a", "TRANSFER", {"to": "farmers", "amount": 10}, 1)])

    # 3) LIST/BID abuse
    def list_txs(t, run):
        v = run.state.ruleset_version
        s = run.state
        # seed some grain first via produce-free injection: use pantry grain
        out = []
        if t == 2:
            out.append(tx(t, "farmer_a", "LIST_GOOD", {"good": "grain", "qty": 1_000_000, "price": 1}, v))
        else:
            out.append(tx(t, "farmer_a", "LIST_GOOD", {"good": "grain", "qty": 0, "price": 1}, v))
            out.append(tx(t, "farmer_a", "LIST_GOOD", {"good": "grain", "qty": -5, "price": 1}, v))
            out.append(tx(t, "farmer_a", "LIST_GOOD", {"good": "ghostgood", "qty": 1, "price": 1}, v))
            out.append(tx(t, "farmer_a", "LIST_GOOD", {"good": "grain", "qty": 1, "price": 0}, v))
            out.append(tx(t, "farmer_a", "LIST_GOOD", {"good": "grain", "qty": 1, "price": -3}, v))
            out.append(tx(t, "farmer_a", "LIST_GOOD", {"good": "grain", "qty": 10**9, "price": 1}, v))
        return out

    run_attack("LIST_GOOD payload abuse", list_txs)
    run_attack("BID overspend triple", lambda t, run: [
        tx(t, "worker_a", "BID", {"good": "bread", "qty": 1, "max_price": 400}, 1)
        for _ in range(3)])
    run_attack("BID zero price/qty", lambda t, run: [
        tx(t, "worker_a", "BID", {"good": "bread", "qty": 0, "max_price": 1}, 1),
        tx(t, "worker_a", "BID", {"good": "bread", "qty": 1, "max_price": 0}, 1),
        tx(t, "worker_a", "BID", {"good": "bread", "qty": -1, "max_price": -5}, 1),
        tx(t, "worker_a", "BID", {"good": "ghost", "qty": 1, "max_price": 1}, 1)])

    # 4) PRODUCE abuse
    run_attack("PRODUCE zero runs", lambda t, run: [
        tx(t, "farmer_a", "PRODUCE", {"recipe_id": "grain_farming", "runs": 0}, 1)])
    run_attack("PRODUCE huge runs", lambda t, run: [
        tx(t, "farmer_a", "PRODUCE", {"recipe_id": "grain_farming", "runs": 10**9}, 1)])
    run_attack("PRODUCE bad recipe", lambda t, run: [
        tx(t, "farmer_a", "PRODUCE", {"recipe_id": "make_gold", "runs": 1}, 1)])

    # 5) FOUND/JOIN abuse
    run_attack("FOUND duplicate coop", lambda t, run: [
        tx(t, "baker_a", "FOUND_COOP", {"coop_id": "bakers", "name": "x", "members": ["baker_a", "baker_b"]}, 1)])
    run_attack("FOUND with unknown member", lambda t, run: [
        tx(t, "baker_a", "FOUND_COOP", {"coop_id": "cult", "name": "x", "members": ["baker_a", "ghost"]}, 1)])
    run_attack("JOIN already member", lambda t, run: [
        tx(t, "baker_a", "JOIN_COOP", {"coop_id": "millers"}, 1)])

    # 6) governance paths (bootstrap RULE_CHANGE)
    def rule_tx(t, run, params):
        return [tx(t, "worker_a", "RULE_CHANGE", {"params": params, "activation_tick": t + 2}, 1)]

    run_attack("RULE_CHANGE disable governance", lambda t, run: rule_tx(t, run, {
        **run.state.active_ruleset_params(), "governance": {
            "enabled": False, "vote_window_ticks": 3, "quorum_bp": 5_000, "trial_period_ticks": 10}}))
    run_attack("RULE_CHANGE negative quotas", lambda t, run: rule_tx(t, run, {
        **run.state.active_ruleset_params(), "essential_need_quota": {"bread": -100}}))

    # 7) governance paths (LIVE)
    def prop_tx(t, run, params):
        v = run.state.ruleset_version
        return [tx(t, "worker_a", "PROPOSE", {"params": params, "activation_tick": t + 8}, v)]

    run_attack("PROPOSE garbage needs", lambda t, run: prop_tx(t, run, {
        **run.state.active_ruleset_params(), "needs": {"bread": "lots"}}), governance=True)
    run_attack("VOTE on ghost proposal", lambda t, run: [
        tx(t, "worker_a", "VOTE", {"proposal_id": "p999", "choice": "for"}, 1)], governance=True)
    run_attack("ROLLBACK to v0", lambda t, run: [
        tx(t, "worker_a", "ROLLBACK", {"to_version": 0}, 1)], governance=True)
    run_attack("INTERVENE as non-council", lambda t, run: [
        tx(t, "farmer_a", "INTERVENE", {"kind": "dissolve_hoard", "target": "worker_a"}, 1)], governance=True)

    # 8) wrong version pinning
    run_attack("wrong ruleset_version", lambda t, run: [
        tx(t, "worker_a", "WORK", {"coop_id": "farmers", "hours": 8}, 999)])

    print()
    if FINDINGS:
        print(f"!!! {len(FINDINGS)} FINDINGS:")
        for f in FINDINGS:
            print("   -", f)
        return 1
    print("matrix clean: no invariant breaks")
    return 0


def fuzz(ticks: int = 400, seed: int = 7):
    """Seeded random action fuzzing against a live economy."""
    print(f"=== fuzz: {ticks} ticks, seed {seed} ===")
    run = Run(seed=seed, governance=True)
    s, led = run.state, run.ledger
    rng = random.Random(seed)
    citizens = sorted(s.balances)
    actions_pool = ["WORK", "TRANSFER", "LIST_GOOD", "BID", "BUY_ESSENTIAL",
                    "PRODUCE", "JOIN_COOP", "VOTE", "PROPOSE", "ROLLBACK"]
    goods = sorted(s.goods)
    coops = sorted(s.coops)
    accepted = {}
    for t in range(2, ticks + 1):
        # normal economy actions continue
        normal = []
        for name, meta in sorted(run.bots.items()):
            r2 = random.Random(f"{seed}:{t}:{name}")
            normal.extend(meta["fn"](name, s, s.active_ruleset_params(), t, r2))
        # attacker noise
        noise = []
        for _ in range(6):
            who = rng.choice(citizens)
            act = rng.choice(actions_pool)
            v = s.ruleset_version
            if act == "WORK":
                payload = {"coop_id": rng.choice(coops + ["ghost"]),
                           "hours": rng.choice([8, 0, -3, 10**7, 999])}
            elif act == "TRANSFER":
                payload = {"to": rng.choice(citizens), "amount": rng.choice([10, 0, -5, 10**6])}
            elif act == "LIST_GOOD":
                payload = {"good": rng.choice(goods), "qty": rng.choice([1, 0, -2, 10**6]),
                           "price": rng.choice([2, 0, -1, 10**6])}
            elif act == "BID":
                payload = {"good": rng.choice(goods), "qty": rng.choice([1, 0, -1]),
                           "price": rng.choice([2, 0, 10**6])}
            elif act == "BUY_ESSENTIAL":
                payload = {"good": rng.choice(goods), "qty": rng.choice([1, 0, 10**6])}
            elif act == "PRODUCE":
                payload = {"recipe_id": rng.choice(["grain_farming", "x"]),
                           "runs": rng.choice([1, 0, -1, 10**6])}
            elif act == "JOIN_COOP":
                payload = {"coop_id": rng.choice(coops)}
            elif act == "VOTE":
                payload = {"proposal_id": rng.choice(["p1", "p99", ""]),
                           "choice": rng.choice(["for", "against", "maybe"])}
            elif act == "PROPOSE":
                payload = {"params": rng.choice([{}, {"bread": 1}, None]),
                           "activation_tick": rng.choice([t + 9, 0, -1])}
            else:  # ROLLBACK
                payload = {"to_version": rng.choice([1, 2, 99, 0])}
            noise.append(tx(t, who, act, payload, v))
        apply_tick(s, led, normal + noise, current_tick=t)
        run._record_timeline()
        bad = invariants_ok(s)
        if bad:
            FINDINGS.append(f"fuzz tick {t}: {bad}")
            print(f"!!! fuzz finding at tick {t}: {bad}")
            return 1
    print("fuzz clean: invariants held")
    return 0




def greedy_adversary(ticks: int = 300, seed: int = 5):
    """Valid-action profit seekers, overlaid ON TOP of honest behavior
    (attacker keeps working/eating + adds malicious txs). Blind bids match
    at settlement against same-tick listings (listings never survive a
    tick — FCFS essential buyers clear them)."""
    print(f"=== greedy adversary: {ticks} ticks ===")
    from openboard.bots import _tx as btx
    from openboard.metrics import gini as gini_fn

    def overlay(extra):
        def make(inner):
            def bot(who, state, params, tick, rng):
                out = inner(who, state, params, tick, rng)
                out.extend(extra(who, state, tick))
                return out
            return bot
        return make

    def wash_extra(who, state, tick):
        # worker_a IS a farmers member: 3x-floor bid on own coop's grain.
        # Wash-bid detection must catch the attempt itself.
        v = state.ruleset_version
        floor = state.good_cost_baseline.get("grain") or state.goods.get("grain", {}).get("floor") or 1
        return [btx(tick, who, "BID", {"good": "grain", "qty": 5, "max_price": floor * 3}, v)]

    def corner_extra(who, state, tick):
        # buy all bread every tick slightly above last clear, corner the flow
        v = state.ruleset_version
        cl = state.last_clearing.get("bread") or 2
        return [btx(tick, who, "BID", {"good": "bread", "qty": 50, "max_price": cl + 1}, v)]

    def vampire(who, state, params, tick, rng):
        v = state.ruleset_version
        return [btx(tick, who, "WORK", {"coop_id": "farmers", "hours": 8}, v)]

    strategies = {
        "wash_trader": lambda fn: overlay(wash_extra)(fn),
        "cornerer": lambda fn: overlay(corner_extra)(fn),
        "vampire": lambda fn: vampire,
    }

    rc = 0
    for sname, wrap in strategies.items():
        run = Run(seed=seed)
        s, led = run.state, run.ledger
        for t in range(2, ticks + 1):
            actions = []
            for name, meta in sorted(run.bots.items()):
                fn = wrap(meta["fn"]) if name == "worker_a" else meta["fn"]
                r2 = random.Random(f"{seed}:{t}:{name}")
                actions.extend(fn(name, s, s.active_ruleset_params(), t, r2))
            apply_tick(s, led, actions, current_tick=t)
            run._record_timeline()
            bad = invariants_ok(s)
            if bad:
                FINDINGS.append(f"greedy/{sname}: {bad} tick {t}")
                print(f"  !! {sname}: INVARIANT BREAK {bad}")
                rc = 1
                break
        else:
            vals = sorted(s.balances.values())
            med = vals[len(vals) // 2]
            attacker = s.balances["worker_a"]
            ratio = attacker / max(med, 1)
            flag = ratio > 2.0
            mark = "FINDING" if flag else "ok"
            print(f"  {mark:8s} {sname}: attacker={attacker} median={med} ratio={ratio:.2f} gini={gini_fn(list(s.balances.values()))}")
            if flag:
                FINDINGS.append(f"greedy/{sname}: extracted {attacker} vs median {med} (ratio {ratio:.1f}x)")
                rc = 1
    return rc


if __name__ == "__main__":
    rc = attack_matrix()
    if len(sys.argv) > 1 and sys.argv[1] == "fuzz":
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 400
        rc += fuzz(n)
    if len(sys.argv) > 1 and sys.argv[1] == "greedy":
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 300
        rc += greedy_adversary(n)
    if len(sys.argv) > 1 and sys.argv[1] == "all":
        rc += fuzz(400) + greedy_adversary(300)
    sys.exit(rc)
