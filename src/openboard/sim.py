"""Simulation harness — bot-driven economies (Phase 7, spec §10).

run_simulation() builds a deterministic world from a cast + coop plan,
then lets bots act each tick. Same seed -> identical state hash.
"""

from __future__ import annotations

import random
from typing import Any

from .bots import DecisionFn, _my_coop, _tx, personal_needs
from .engine import apply_tick
from .ledger import Ledger, Transaction
from .metrics import SimMetrics
from .state import WorldState


def make_specialist(
    recipe_id: str,
    output_good: str,
    buys: dict[str, int],
    stock_target: int = 40,
) -> DecisionFn:
    """A producer bot specialized in one recipe: work, buy missing inputs,
    produce only up to a stock target (demand-driven, no infinite piles),
    list the surplus, and personally buy daily needs (circular flow)."""

    def bot(who: str, state: WorldState, params: dict[str, Any], tick: int, rng: random.Random) -> list[Transaction]:
        v = state.ruleset_version
        coop_id = _my_coop(state, who)
        if coop_id is None:
            return []
        c = state.coops[coop_id]
        recipe = state.recipes[recipe_id]
        out = []
        # Right to work: citizens log hours freely; society mints the wage
        # (D4). Idle-pool wages act as the income floor that funds essential
        # consumption — recycled by wealth tax + dividends, NOT an exploit.
        # The engine-side labor_pool_cap bounds adversarial farming; honest
        # pools never approach it because production consumes them.
        _cap = params.get("labor_pool_cap")
        if _cap is None or c["labor_pool_hours"] + 8 <= _cap:
            out.append(_tx(tick, who, "WORK", {"coop_id": coop_id, "hours": 8}, v))

        listed = sum(
            e["qty"] for e in state.listings.get(output_good, [])
            if e["coop_id"] == coop_id
        )
        stock = c["inventory"].get(output_good, 0) + listed
        want_produce = stock < stock_target

        # buy missing inputs from the market (treasury must afford it),
        # sized to at most one production run beyond the target
        if want_produce:
            out_units = sum(recipe["outputs"].values())
            runs_wanted = max(1, (stock_target - stock + out_units - 1) // out_units)
            for good, want_per_run in sorted(buys.items()):
                have = c["inventory"].get(good, 0)
                need = max(0, runs_wanted * want_per_run - have)
                floor = state.good_cost_baseline.get(good, 1)
                price = floor + 1
                treasury = c.get("treasury", 0)
                # affordability-capped: buy what we can now, more next tick
                # (all-or-nothing froze coops forever when a full top-up
                # cost slightly more than the treasury held)
                qty = min(need, treasury // price) if price > 0 else need
                if qty > 0:
                    out.append(_tx(tick, who, "BID_FOR_COOP", {
                        "coop_id": coop_id, "good": good, "max_price": price, "qty": qty,
                    }, v))
            # also recipe-native inputs when our own stock is short
            for good, want_per_run in sorted(recipe["inputs"].items()):
                if good in buys:
                    continue
                have = c["inventory"].get(good, 0)
                need = max(0, runs_wanted * want_per_run - have)
                floor = state.good_cost_baseline.get(good, 1)
                price = floor + 1
                treasury = c.get("treasury", 0)
                qty = min(need, treasury // price) if price > 0 else need
                if qty > 0:
                    out.append(_tx(tick, who, "BID_FOR_COOP", {
                        "coop_id": coop_id, "good": good, "max_price": price, "qty": qty,
                    }, v))
            # energy is an input too: coops must buy electricity to run
            # recipes (bootstrap endowment is finite; utilities sell power)
            if recipe.get("energy", 0) > 0 and "electricity" not in buys:
                have = c["inventory"].get("electricity", 0)
                need = max(0, runs_wanted * recipe["energy"] - have)
                floor = state.good_cost_baseline.get("electricity", 1)
                price = floor + 1
                treasury = c.get("treasury", 0)
                qty = min(need, treasury // price) if price > 0 else need
                if qty > 0:
                    out.append(_tx(tick, who, "BID_FOR_COOP", {
                        "coop_id": coop_id, "good": "electricity", "max_price": price, "qty": qty,
                    }, v))

        # solvency guard: estimate the NEXT run's input cost at bid prices
        # (book baseline + 1). Producing while unable to restock inputs is
        # the insolvency death spiral observed at t~800 (millers at 0).
        next_run_cost = recipe.get("energy", 0) * (state.good_cost_baseline.get("electricity", 2) + 1)
        next_run_cost += sum(
            q * (state.good_cost_baseline.get(g, 1) + 1)
            for g, q in recipe["inputs"].items()
            if g != "electricity"
        )
        # produce when feasible, demand says so, and we can restock after
        if (
            want_produce
            and c["labor_pool_hours"] >= recipe["labor_hours"]
            and c["inventory"].get("electricity", 0) >= recipe["energy"]
            and all(c["inventory"].get(g, 0) >= q for g, q in recipe["inputs"].items())
            and (c.get("treasury", 0) >= next_run_cost or stock < stock_target // 2)
        ):
            out.append(_tx(tick, who, "PRODUCE", {
                "coop_id": coop_id, "recipe_id": recipe_id, "runs": 1,
            }, v))

        # list the surplus of our output (keep a buffer of 10)
        held = c["inventory"].get(output_good, 0)
        if held > 10:
            out.append(_tx(tick, who, "LIST_GOOD", {
                "coop_id": coop_id, "good": output_good, "qty": held - 10,
            }, v))

        out.extend(personal_needs(who, state, params, tick))
        return out

    return bot




def run_simulation(
    cast: list[tuple[str, DecisionFn]],
    coop_plan: list[dict[str, Any]],
    ticks: int,
    seed: int,
    ruleset_params: dict[str, Any] | None = None,
    seed_treasuries: dict[str, int] | None = None,
) -> tuple[WorldState, Ledger, SimMetrics]:
    """Deterministic bot economy.

    - tick 1: co-ops founded from coop_plan
    - treasuries seeded directly (documented pre-run injection, consistent
      across reruns so determinism and the money invariant account for them)
    - ticks 2..N: every bot decides against live public state; the engine
      applies the batch; metrics record per-tick events
    """
    citizens = {name: 500 for name, _ in cast}
    state = genesis_state_compat(citizens, ruleset_params)
    ledger = Ledger()
    metrics = SimMetrics()

    founding = [
        Transaction(
            tick=1,
            sender=plan["members"][0],
            action="FOUND_COOP",
            payload={"coop_id": plan["coop_id"], "name": plan["coop_id"], "members": plan["members"]},
            ruleset_version=1,
        )
        for plan in coop_plan
    ]
    apply_tick(state, ledger, founding, current_tick=1)

    for coop_id, amount in (seed_treasuries or {}).items():
        state.coops[coop_id]["treasury"] = amount

    for t in range(2, ticks + 1):
        params = state.active_ruleset_params()
        actions: list[Transaction] = []
        for name, fn in sorted(cast, key=lambda c: c[0]):
            bot_rng = random.Random(f"{seed}:{t}:{name}")  # stable across processes
            actions.extend(fn(name, state, params, t, bot_rng))
        pre = len(state.applied)
        apply_tick(state, ledger, actions, current_tick=t)
        metrics.record_tick(state, state.applied[pre:])

    metrics.record_rejections(ledger)
    for pr in state.proposals.values():
        if pr["status"] == "passed":
            metrics.proposals_passed += 1
        elif pr["status"] == "failed":
            metrics.proposals_failed += 1

    return state, ledger, metrics


def genesis_state_compat(citizens: dict[str, int], ruleset_params: dict[str, Any] | None) -> WorldState:
    from .state import genesis_state

    return genesis_state(citizens, ruleset_params=ruleset_params)


def total_money(state: WorldState) -> int:
    treasuries = sum(c.get("treasury", 0) for c in state.coops.values())
    return sum(state.balances.values()) + state.surplus_pool + treasuries
