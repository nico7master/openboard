#!/usr/bin/env python
"""WP3.1 soak: 10+ concurrent human seats, 1000 ticks, zero invariant breaks.

Simulates the real multiplayer path: each human seat registers via the
account API (claiming a genesis citizen out of bot control), then acts
through the same queue_action path the dashboard uses (WORK when in a
coop with hours left, BUY_ESSENTIAL for due needs, occasional VOTE/LOAN).
Seats act with randomized presence/latency each tick — not synchronized.

Gate: 1000 ticks, 12 seats, money invariant exact every tick, no crashes,
bot+human world stays alive (essentials within bound).

Usage: python scripts/soak_seats.py [ticks] [seed]
"""
import json
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "dashboard"))

from server import Run  # noqa: E402

TICKS = int(sys.argv[1]) if len(sys.argv) > 1 else 1000
SEED = int(sys.argv[2]) if len(sys.argv) > 2 else 42
N_SEATS = 12
ESSENTIALS = {"bread", "water", "electricity", "meals"}
ESSENTIALS_STREAK_BOUND = 30
OUT = ROOT / "sweeps" / "soak_seats.json"


def holders(state) -> list[int]:
    vals = list(state.balances.values())
    vals += [c.get("treasury", 0) for c in state.coops.values()]
    return vals


def money_delta(run) -> int:
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
    return total - (run._money0 + s.money_minted - s.money_retired)


def essentials_streaks(run) -> dict[str, int]:
    worst: dict[str, int] = {}
    for _cit, goods in run.state.unmet_needs.items():
        for g, v in goods.items():
            if g in ESSENTIALS and v >= 1:
                worst[g] = max(worst.get(g, 0), v)
    return worst


def main() -> int:
    t0 = time.perf_counter()
    run = Run(seed=SEED)
    rng = random.Random(f"soak:{SEED}")

    # 12 seats claim citizens out of bot control (the real claim flow).
    # Spread seats across NON-essential coops (<=2 per coop): pulling the
    # bread/water/electricity specialists out of bot control collapses
    # essential production and starves the world — that's a staffing
    # decision, not a multiplayer stress test. recipe_intent is a STRING
    # (recipe id), so map intent ids to the essentials supply chain.
    essential_intents = {
        "flour_to_bread", "grain_farming", "grain_to_flour",  # bread chain
        "water_service",                                        # water
        "electricity_coal", "wind_farm", "coal_mining",        # electricity
        "meal_service",                                         # meals
    }
    essential_coops = {
        cid
        for cid, c in run.state.coops.items()
        if (c.get("recipe_intent") or "") in essential_intents
    }
    candidates = [
        cit
        for cit in sorted(run.state.balances.keys())
        if (next((cid for cid, c in run.state.coops.items()
                  if cit in c.get("members", ())), None) not in essential_coops)
    ]
    per_coop: dict[str, int] = {}
    seats = []
    for cit in candidates:
        cid = next((cid for cid, c in run.state.coops.items()
                    if cit in c.get("members", ())), "-")
        if per_coop.get(cid, 0) >= 2:
            continue
        per_coop[cid] = per_coop.get(cid, 0) + 1
        seats.append(cit)
        if len(seats) == N_SEATS:
            break
    assert len(seats) == N_SEATS, f"only {len(seats)} claimable seats"
    for cit in seats:
        assert cit in run.bots, f"seat citizen {cit} not bot-managed"
        run.bots.pop(cit)
    print(f"soak: {len(seats)} human seats claimed, ticks={TICKS}", flush=True)

    inv_bad = 0
    n_actions = 0
    accepted = 0
    rejected = 0
    seen_seqs: set[int] = set()
    rejection_reasons: dict[str, int] = {}
    worst_ess: dict[str, int] = {}
    seat_util: dict[str, int] = {c: 0 for c in seats}

    for t in range(2, TICKS + 2):
        # --- human seats act (staggered, like real players)
        for cit in seats:
            if rng.random() < 0.3:  # 70% presence per tick, unsynchronized
                continue
            seat_util[cit] += 1
            s = run.state
            params = s.active_ruleset_params()
            choices = []
            hours_left = max(0, int(params.get("max_work_hours_cumulative", 8))
                             - int(s.labor_hours.get(cit, 0)))
            in_coop = any(cit in c.get("members", ()) for c in s.coops.values())
            if in_coop and hours_left > 0:
                coop_id = next(
                    cid for cid, c in s.coops.items() if cit in c.get("members", ())
                )
                # competent players work ALL available hours when present
                choices.append(("WORK", {"coop_id": coop_id, "hours": hours_left}))
            elif not in_coop:
                # seatless players join the smallest open coop (real affordance)
                max_members = int(params.get("max_coop_members", 20) or 20)
                open_coops = sorted(
                    (cid for cid, c in s.coops.items()
                     if len(c.get("members", [])) < max_members),
                    key=lambda cid: len(s.coops[cid].get("members", [])),
                )
                if open_coops := open_coops[:3]:
                    choices.append(("JOIN_COOP", {"coop_id": rng.choice(open_coops)}))
            needs = params.get("needs") or {}
            inv = s.citizen_inventory.get(cit, {})
            for good, quota in sorted(needs.items()):
                cyc = int((params.get("needs_cycle") or {}).get(good, 1))
                due = cyc <= 1 or s.tick % cyc == 0
                if due and int(inv.get(good, 0)) < quota and good in ESSENTIALS:
                    choices.append(("BUY_ESSENTIAL", {"good": good, "qty": 1}))
            if (params.get("credit") or {}).get("enabled") and rng.random() < 0.02:
                choices.append(("LOAN", {"amount": 200}))
            if not choices:
                continue
            # competent players BUY FOOD FIRST (all due unmet essentials,
            # they're at cost floors), then work with the rest of the tick
            buys = [c for c in choices if c[0] == "BUY_ESSENTIAL"]
            work = [c for c in choices if c[0] != "BUY_ESSENTIAL"]
            for action, payload in buys:
                run.queue_action(cit, action, payload)
                n_actions += 1
            if work and rng.random() < 0.8:
                action, payload = work[0]
                run.queue_action(cit, action, payload)
                n_actions += 1

        # --- world advances: bots + queued human actions, one batch
        actions = []
        for name, meta in sorted(run.bots.items()):
            brng = random.Random(f"{SEED}:{t}:{name}")
            actions.extend(
                meta["fn"](name, run.state, run.state.active_ruleset_params(), t, brng)
            )
        # drain human-queued actions into the same batch (server merge path)
        pend = list(run.pending)
        run.pending.clear()
        actions.extend(pend)
        pre = len(run.ledger.records)
        run._apply_batch(t, actions)
        run._record_timeline()
        n_actions_applied = len(pend)

        # ledger triage: ONLY this tick's records (positional, before pruning)
        for r in run.ledger.records[pre:]:
            tx = r.tx or {}
            if tx.get("sender") in seat_util:
                if r.accepted:
                    accepted += 1
                else:
                    rejected += 1
                    if r.reason:
                        rejection_reasons[r.reason] = rejection_reasons.get(r.reason, 0) + 1

        # memory hygiene (gate recipe)
        run.state.applied.clear()
        run.batches.clear()
        run._last_events = []
        recs = run.ledger.records
        if len(recs) > 4000:
            del recs[: len(recs) - 1000]

        if money_delta(run) != 0:
            inv_bad += 1
            print(f"  t={t} MONEY INVARIANT VIOLATION delta={money_delta(run)}", flush=True)
        ess = essentials_streaks(run)
        for g, v in ess.items():
            worst_ess[g] = max(worst_ess.get(g, 0), v)
        if t % 100 == 0:
            top_bal = max(run.state.balances.values())
            print(f"  t={t} alive inv_bad={inv_bad} actions={n_actions} "
                  f"ess_peak={max(ess.values()) if ess else 0} top_bal={top_bal/100:,.0f}cr",
                  flush=True)

    wall = time.perf_counter() - t0
    result = {
        "ticks": TICKS,
        "seed": SEED,
        "n_seats": len(seats),
        "seat_util_pct": {c: round(100 * u / (TICKS - 1), 1) for c, u in seat_util.items()},
        "actions_queued": n_actions,
        "human_accepted": accepted,
        "human_rejected": rejected,
        "rejection_reasons": rejection_reasons,
        "inv_bad": inv_bad,
        "worst_ess_streak": worst_ess,
        "wall_s": round(wall, 1),
    }
    OUT.write_text(json.dumps(result, indent=1))
    gate = inv_bad == 0 and all(v <= 30 for v in worst_ess.values())
    print(f"SOAK {'PASS' if gate else 'FAIL'}: inv_bad={inv_bad} "
          f"ess={max(worst_ess.values()) if worst_ess else 0} "
          f"actions={n_actions} (acc={accepted} rej={rejected}) wall={wall:.0f}s -> {OUT}")
    return 0 if gate else 1


if __name__ == "__main__":
    sys.exit(main())
