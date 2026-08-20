"""Deterministic tick engine (Phases 1–2).

One tick = one action batch, settled in fixed deterministic order —
sorted by (sender, action, content hash, ruleset version). No wall-clock,
no randomness. Rejections are ledger records, never crashes.

Phase 2: the engine is a rule-set interpreter — the active rule version is
resolved for the tick BEFORE processing; every transaction must be pinned
to that version (RULESET_MISMATCH otherwise). RULE_CHANGE transactions
activate new versions at strictly future ticks.
"""

from __future__ import annotations

from typing import Any

from .errors import Reason
from .ledger import Ledger, Transaction
from .rules import RuleSetDoc, validate_params
from .state import WorldState

SUPPORTED_ACTIONS = frozenset({"TRANSFER", "RULE_CHANGE", "FOUND_COOP", "JOIN_COOP", "WORK", "PRODUCE", "LIST_GOOD", "BID", "BID_FOR_COOP", "BUY_ESSENTIAL", "PROPOSE", "VOTE", "ROLLBACK"})


def _is_int(v: Any) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


# ---------------------------------------------------------------- TRANSFER


def _validate_transfer(state: WorldState, tx: Transaction, params: dict[str, Any]) -> Reason | None:
    payload: dict[str, Any] = tx.payload

    if tx.sender not in state.balances:
        return Reason.UNKNOWN_SENDER

    if not isinstance(payload, dict) or set(payload.keys()) != {"to", "amount"}:
        return Reason.INVALID_PAYLOAD

    amount = payload.get("amount")
    to = payload.get("to")

    if not _is_int(amount):
        return Reason.NON_INTEGER_AMOUNT
    if to not in state.balances:
        return Reason.UNKNOWN_CITIZEN
    if amount <= 0:
        return Reason.RULE_VIOLATION

    limit = params.get("transfer_limit", 0)
    if limit > 0 and amount > limit:
        return Reason.RULE_VIOLATION  # above transfer limit — votable rule (D5/D7)

    if state.balances[tx.sender] < amount:
        return Reason.INSUFFICIENT_CREDITS
    return None


def _apply_transfer(state: WorldState, tx: Transaction) -> dict[str, Any]:
    amount = tx.payload["amount"]
    to = tx.payload["to"]
    state.balances[tx.sender] -= amount
    state.balances[to] += amount
    return {
        "tick": tx.tick,
        "sender": tx.sender,
        "action": "TRANSFER",
        "to": to,
        "amount": amount,
    }


# ------------------------------------------------------------- RULE_CHANGE


def _validate_rule_change(state: WorldState, tx: Transaction, params: dict[str, Any]) -> Reason | None:
    payload = tx.payload

    if tx.sender not in state.balances:
        return Reason.UNKNOWN_SENDER

    # D10 bootstrap story: once governance is enabled, the instant path is
    # locked — all rule change flows through proposals and votes.
    if _gov_params(params)["enabled"]:
        return Reason.GOVERNANCE_LOCKED

    if not isinstance(payload, dict) or set(payload.keys()) != {"params", "activation_tick"}:
        return Reason.INVALID_PAYLOAD

    activation = payload.get("activation_tick")
    if not _is_int(activation):
        return Reason.INVALID_PAYLOAD
    if activation <= tx.tick:
        return Reason.ACTIVATION_IN_PAST  # strictly future only — no retroactivity

    reason = validate_params(payload.get("params"), known_goods=set(state.goods.keys()))
    if reason is not None:
        return reason

    return None


def _apply_rule_change(state: WorldState, tx: Transaction, ledger: Ledger) -> dict[str, Any]:
    params = tx.payload["params"]
    activation = tx.payload["activation_tick"]
    next_version = max(rs["version"] for rs in state.rulesets) + 1

    doc = RuleSetDoc(
        version=next_version,
        params=params,
        activated_at=activation,
        change_tx_hash=tx.content_hash(),
    )
    state.rulesets.append(doc.to_dict())

    return {
        "tick": tx.tick,
        "sender": tx.sender,
        "action": "RULE_CHANGE",
        "new_version": next_version,
        "activated_at": activation,
        "change_tx_hash": tx.content_hash(),
    }


# --------------------------------------------------------------- FOUND_COOP


def _member_of(state: WorldState, citizen: str) -> str | None:
    for coop_id, coop in state.coops.items():
        if citizen in coop["members"]:
            return coop_id
    return None


def _validate_found_coop(state: WorldState, tx: Transaction, params: dict[str, Any]) -> Reason | None:
    payload = tx.payload

    if tx.sender not in state.balances:
        return Reason.UNKNOWN_SENDER

    if not isinstance(payload, dict) or set(payload.keys()) != {"coop_id", "name", "members"}:
        return Reason.INVALID_PAYLOAD

    coop_id = payload.get("coop_id")
    members = payload.get("members")

    if not isinstance(coop_id, str) or not coop_id:
        return Reason.INVALID_PAYLOAD
    if not isinstance(members, list) or not all(isinstance(m, str) for m in members):
        return Reason.INVALID_PAYLOAD
    if tx.sender not in members:
        return Reason.NOT_A_MEMBER
    if len(set(members)) != len(members):
        return Reason.INVALID_PAYLOAD

    for m in members:
        if m not in state.balances:
            return Reason.UNKNOWN_CITIZEN
        if _member_of(state, m) is not None:
            return Reason.ALREADY_IN_COOP

    if coop_id in state.coops:
        return Reason.COOP_EXISTS

    if len(members) < params.get("min_coop_members", 2):
        return Reason.COOP_TOO_SMALL
    if len(members) > params.get("max_coop_members", 12):
        return Reason.COOP_FULL

    return None


def _apply_found_coop(state: WorldState, tx: Transaction, params: dict[str, Any]) -> dict[str, Any]:
    payload = tx.payload
    endowment = params.get("bootstrap_endowment", {})
    state.coops[payload["coop_id"]] = {
        "name": payload["name"],
        "members": list(payload["members"]),
        "founded_tick": tx.tick,
        "inventory": {g: q for g, q in endowment.items()},  # socially granted means of production
        "labor_pool_hours": 0,
        "wage_remainder_bp": 0,
    }
    return {
        "tick": tx.tick,
        "sender": tx.sender,
        "action": "FOUND_COOP",
        "coop_id": payload["coop_id"],
        "members": list(payload["members"]),
        "endowment": dict(endowment),
    }


# ---------------------------------------------------------------- JOIN_COOP


def _validate_join_coop(state: WorldState, tx: Transaction, params: dict[str, Any]) -> Reason | None:
    payload = tx.payload

    if tx.sender not in state.balances:
        return Reason.UNKNOWN_SENDER

    if not isinstance(payload, dict) or set(payload.keys()) != {"coop_id"}:
        return Reason.INVALID_PAYLOAD

    coop_id = payload.get("coop_id")
    if coop_id not in state.coops:
        return Reason.COOP_NOT_FOUND

    if _member_of(state, tx.sender) is not None:
        return Reason.ALREADY_IN_COOP

    coop = state.coops[coop_id]
    if len(coop["members"]) >= params.get("max_coop_members", 12):
        return Reason.COOP_FULL

    return None


def _apply_join_coop(state: WorldState, tx: Transaction) -> dict[str, Any]:
    coop = state.coops[tx.payload["coop_id"]]
    coop["members"].append(tx.sender)
    return {
        "tick": tx.tick,
        "sender": tx.sender,
        "action": "JOIN_COOP",
        "coop_id": tx.payload["coop_id"],
    }


# --------------------------------------------------------------------- WORK


def _validate_work(state: WorldState, tx: Transaction, params: dict[str, Any]) -> Reason | None:
    payload = tx.payload

    if tx.sender not in state.balances:
        return Reason.UNKNOWN_SENDER

    if not isinstance(payload, dict) or set(payload.keys()) != {"coop_id", "hours"}:
        return Reason.INVALID_PAYLOAD

    hours = payload.get("hours")
    coop_id = payload.get("coop_id")

    if not _is_int(hours):
        return Reason.INVALID_HOURS
    if coop_id not in state.coops:
        return Reason.COOP_NOT_FOUND
    coop = state.coops[coop_id]
    if tx.sender not in coop["members"]:
        return Reason.NOT_A_MEMBER
    if hours <= 0:
        return Reason.INVALID_HOURS
    if hours > params.get("max_work_hours_per_tick", 8):
        return Reason.INVALID_HOURS

    return None


def _apply_work(state: WorldState, tx: Transaction, params: dict[str, Any]) -> dict[str, Any]:
    coop = state.coops[tx.payload["coop_id"]]
    hours = tx.payload["hours"]
    mult_bp = params.get("wage_multiplier_bp", 10_000)

    # Integer-only wage math with remainder accumulation (no floats, ever)
    total_bp = hours * mult_bp + coop.get("wage_remainder_bp", 0)
    credits = total_bp // 10_000
    coop["wage_remainder_bp"] = total_bp % 10_000

    # Money creation by work (D4): wages are minted, not transferred
    state.balances[tx.sender] += credits
    state.money_minted += credits

    coop["labor_pool_hours"] += hours
    state.labor_hours[tx.sender] += hours

    return {
        "tick": tx.tick,
        "sender": tx.sender,
        "action": "WORK",
        "coop_id": tx.payload["coop_id"],
        "hours": hours,
        "wage_credits": credits,
    }


# ------------------------------------------------------------------ PRODUCE


def _validate_produce(state: WorldState, tx: Transaction, params: dict[str, Any]) -> Reason | None:
    payload = tx.payload

    if tx.sender not in state.balances:
        return Reason.UNKNOWN_SENDER

    if not isinstance(payload, dict) or set(payload.keys()) != {"coop_id", "recipe_id", "runs"}:
        return Reason.INVALID_PAYLOAD

    runs = payload.get("runs")
    recipe_id = payload.get("recipe_id")
    coop_id = payload.get("coop_id")

    if not _is_int(runs) or runs <= 0:
        return Reason.INVALID_RUNS
    if coop_id not in state.coops:
        return Reason.COOP_NOT_FOUND
    coop = state.coops[coop_id]
    if tx.sender not in coop["members"]:
        return Reason.NOT_A_MEMBER
    if recipe_id not in state.recipes:
        return Reason.RECIPE_NOT_FOUND

    recipe = state.recipes[recipe_id]
    inventory = coop["inventory"]

    # Material inputs × runs
    for good, qty in recipe["inputs"].items():
        if inventory.get(good, 0) < qty * runs:
            return Reason.NOT_ENOUGH_INPUTS

    # Energy × runs (electricity good)
    energy_needed = recipe["energy"] * runs
    if energy_needed > 0 and inventory.get("electricity", 0) < energy_needed:
        return Reason.NOT_ENOUGH_ENERGY

    # Labor pool × runs
    if coop.get("labor_pool_hours", 0) < recipe["labor_hours"] * runs:
        return Reason.NOT_ENOUGH_LABOR

    return None


def _apply_produce(state: WorldState, tx: Transaction, params: dict[str, Any]) -> dict[str, Any]:
    coop = state.coops[tx.payload["coop_id"]]
    recipe = state.recipes[tx.payload["recipe_id"]]
    runs = tx.payload["runs"]
    inventory = coop["inventory"]

    # Consume inputs
    for good, qty in recipe["inputs"].items():
        inventory[good] -= qty * runs

    # Consume energy
    energy_consumed = recipe["energy"] * runs
    if energy_consumed > 0:
        inventory["electricity"] -= energy_consumed

    # Consume labor from pool
    coop["labor_pool_hours"] -= recipe["labor_hours"] * runs

    # Produce outputs
    outputs_produced: dict[str, int] = {}
    for good, qty in recipe["outputs"].items():
        inventory[good] = inventory.get(good, 0) + qty * runs
        outputs_produced[good] = qty * runs

    # Cost baseline: ceil((labor + energy + material inputs) / total output units)
    # Round UP, never down: production at cost must not price below cost.
    # Floor division priced high-output staples (100 grain per run) at 0,
    # collapsing the whole market into pure surplus.
    labor_cost = recipe["labor_hours"] * runs  # 1 credit/hour base accounting
    energy_cost = energy_consumed * params.get("energy_price", 2)
    input_cost = sum(
        qty * runs * state.good_cost_baseline.get(good, 1) for good, qty in recipe["inputs"].items()
    )
    total_units = sum(outputs_produced.values())

    baselines_stamped: dict[str, int] = {}
    if total_units > 0:
        unit_baseline = -(-(labor_cost + energy_cost + input_cost) // total_units)
        for good in outputs_produced:
            state.good_cost_baseline[good] = unit_baseline
            baselines_stamped[good] = unit_baseline

    return {
        "tick": tx.tick,
        "sender": tx.sender,
        "action": "PRODUCE",
        "coop_id": tx.payload["coop_id"],
        "recipe_id": tx.payload["recipe_id"],
        "runs": runs,
        "outputs": outputs_produced,
        "cost_baselines": baselines_stamped,
    }


# ----------------------------------------------------------------- MARKETS


def _validate_list_good(state: WorldState, tx: Transaction, params: dict[str, Any]) -> Reason | None:
    payload = tx.payload

    if tx.sender not in state.balances:
        return Reason.UNKNOWN_SENDER

    if not isinstance(payload, dict) or set(payload.keys()) != {"coop_id", "good", "qty"}:
        return Reason.INVALID_PAYLOAD

    coop_id = payload.get("coop_id")
    good = payload.get("good")
    qty = payload.get("qty")

    if coop_id not in state.coops:
        return Reason.COOP_NOT_FOUND
    coop = state.coops[coop_id]
    if tx.sender not in coop["members"]:
        return Reason.NOT_A_MEMBER
    if good not in state.goods:
        return Reason.GOOD_UNKNOWN
    if not _is_int(qty) or qty <= 0:
        return Reason.INVALID_QTY
    if coop["inventory"].get(good, 0) < qty:
        return Reason.NOT_ENOUGH_INVENTORY
    return None


def _apply_list_good(state: WorldState, tx: Transaction) -> dict[str, Any]:
    payload = tx.payload
    coop = state.coops[payload["coop_id"]]
    good = payload["good"]
    qty = payload["qty"]

    # Escrow: goods leave inventory into the listing
    coop["inventory"][good] -= qty
    floor = state.good_cost_baseline.get(good, 1)

    state.listings.setdefault(good, []).append({
        "coop_id": payload["coop_id"],
        "qty": qty,
        "floor": floor,
        "listed_tick": tx.tick,
    })

    return {
        "tick": tx.tick,
        "sender": tx.sender,
        "action": "LIST_GOOD",
        "coop_id": payload["coop_id"],
        "good": good,
        "qty": qty,
        "floor": floor,
    }


def _validate_bid(state: WorldState, tx: Transaction, params: dict[str, Any]) -> Reason | None:
    payload = tx.payload

    if tx.sender not in state.balances:
        return Reason.UNKNOWN_SENDER

    keys = {"good", "max_price", "qty"}
    if not isinstance(payload, dict) or set(payload.keys()) != keys:
        return Reason.INVALID_PAYLOAD

    good = payload.get("good")
    price = payload.get("max_price")
    qty = payload.get("qty")

    if good not in state.goods:
        return Reason.GOOD_UNKNOWN
    if not _is_int(price) or price <= 0:
        return Reason.INVALID_PRICE
    if not _is_int(qty) or qty <= 0:
        return Reason.INVALID_QTY

    floor = state.good_cost_baseline.get(good, 1)
    if price < floor:
        return Reason.INVALID_PRICE  # below cost floor

    # Affordability at submission (max exposure = price × qty)
    if state.balances[tx.sender] < price * qty:
        return Reason.INSUFFICIENT_FUNDS
    return None


def _apply_bid(state: WorldState, tx: Transaction) -> dict[str, Any]:
    payload = tx.payload
    state.bids.append({
        "bidder": tx.sender,
        "coop_id": None,
        "good": payload["good"],
        "max_price": payload["max_price"],
        "qty": payload["qty"],
    })
    return {
        "tick": tx.tick,
        "sender": tx.sender,
        "action": "BID",
        "good": payload["good"],
        "max_price": payload["max_price"],
        "qty": payload["qty"],
    }


def _validate_bid_for_coop(state: WorldState, tx: Transaction, params: dict[str, Any]) -> Reason | None:
    payload = tx.payload

    if tx.sender not in state.balances:
        return Reason.UNKNOWN_SENDER

    keys = {"coop_id", "good", "max_price", "qty"}
    if not isinstance(payload, dict) or set(payload.keys()) != keys:
        return Reason.INVALID_PAYLOAD

    coop_id = payload.get("coop_id")
    good = payload.get("good")
    price = payload.get("max_price")
    qty = payload.get("qty")

    if coop_id not in state.coops:
        return Reason.COOP_NOT_FOUND
    coop = state.coops[coop_id]
    if tx.sender not in coop["members"]:
        return Reason.NOT_A_MEMBER
    if good not in state.goods:
        return Reason.GOOD_UNKNOWN
    if not _is_int(price) or price <= 0:
        return Reason.INVALID_PRICE
    if not _is_int(qty) or qty <= 0:
        return Reason.INVALID_QTY

    floor = state.good_cost_baseline.get(good, 1)
    if price < floor:
        return Reason.INVALID_PRICE

    if coop.get("treasury", 0) < price * qty:
        return Reason.INSUFFICIENT_FUNDS
    return None


def _apply_bid_for_coop(state: WorldState, tx: Transaction) -> dict[str, Any]:
    payload = tx.payload
    state.bids.append({
        "bidder": tx.sender,
        "coop_id": payload["coop_id"],
        "good": payload["good"],
        "max_price": payload["max_price"],
        "qty": payload["qty"],
    })
    return {
        "tick": tx.tick,
        "sender": tx.sender,
        "action": "BID_FOR_COOP",
        "coop_id": payload["coop_id"],
        "good": payload["good"],
        "max_price": payload["max_price"],
        "qty": payload["qty"],
    }


def _validate_buy_essential(state: WorldState, tx: Transaction, params: dict[str, Any]) -> Reason | None:
    payload = tx.payload

    if tx.sender not in state.balances:
        return Reason.UNKNOWN_SENDER

    if not isinstance(payload, dict) or set(payload.keys()) != {"good", "qty"}:
        return Reason.INVALID_PAYLOAD

    good = payload.get("good")
    qty = payload.get("qty")

    if good not in state.goods:
        return Reason.GOOD_UNKNOWN
    if not _is_int(qty) or qty <= 0:
        return Reason.INVALID_QTY

    triage = state.effective_triage(good)
    if triage not in ("essential", "emergency"):
        return Reason.NOT_ESSENTIAL

    quota = params.get("essential_need_quota", {}).get(good, 0)
    if qty > quota:
        return Reason.QUOTA_EXCEEDED

    price = state.good_cost_baseline.get(good, 1)
    if state.balances[tx.sender] < price * qty:
        return Reason.INSUFFICIENT_FUNDS

    # supply check happens at clearing (FCFS); nothing else to verify here
    return None


def _apply_buy_essential(state: WorldState, tx: Transaction) -> dict[str, Any]:
    payload = tx.payload
    state.bids.append({
        "bidder": tx.sender,
        "coop_id": None,
        "good": payload["good"],
        "max_price": state.good_cost_baseline.get(payload["good"], 1),  # baseline price, no bidding
        "qty": payload["qty"],
        "essential": True,
    })
    return {
        "tick": tx.tick,
        "sender": tx.sender,
        "action": "BUY_ESSENTIAL",
        "good": payload["good"],
        "qty": payload["qty"],
    }


def _clear_markets(state: WorldState, tick: int, params: dict[str, Any], ledger: Ledger) -> list[dict[str, Any]]:
    """End-of-tick market clearing. Deterministic (spec §9).

    1. Essential FCFS pass: essential/emergency goods sold at the seller's
       cost floor to essential buyers in deterministic order.
    2. Auction pass: remaining listed units sold to market bids at the
       uniform clearing price (lowest winning bid, never below floor).
    3. Unsold units return to their sellers.
    4. Surplus (price - floor) flows to the pool; pool beyond the reserve
       cap is retired from circulation.

    Money conservation is exact: every unit sold at price P moves exactly
    P credits from the buyer to seller floor + pool (P - floor). Integer
    only, no rounding — nothing is ever created or destroyed by clearing.
    """
    events: list[dict[str, Any]] = []

    if not state.listings and not state.bids:
        return events

    essential_buyers: dict[str, list[dict[str, Any]]] = {}
    auction_bids: dict[str, list[dict[str, Any]]] = {}

    for bid in sorted(
        state.bids,
        key=lambda b: (b["bidder"], str(b["coop_id"]), b["good"], b["qty"], b["max_price"]),
    ):
        if bid.get("essential"):
            essential_buyers.setdefault(bid["good"], []).append(bid)
        else:
            auction_bids.setdefault(bid["good"], []).append(bid)

    # --- Pass 1: essentials FCFS at the cost floor (D8: need first)
    for good in sorted(essential_buyers.keys() & state.listings.keys()):
        sold_records: list[dict[str, Any]] = []
        total_sold = 0
        listed = sum(e["qty"] for e in state.listings[good])

        for buyer in essential_buyers[good]:
            need = buyer["qty"]
            got = 0
            paid = 0
            for entry in state.listings[good]:
                if need <= 0:
                    break
                take = min(entry["qty"], need)
                if take <= 0:
                    continue
                price = entry["floor"]
                if state.balances[buyer["bidder"]] < take * price:
                    break  # cannot pay at settlement — deterministic drop
                state.balances[buyer["bidder"]] -= take * price
                entry["qty"] -= take
                seller = state.coops[entry["coop_id"]]
                seller["treasury"] = seller.get("treasury", 0) + take * price
                state.treasury_in += take * price
                need -= take
                got += take
                paid += take * price
            if got > 0:
                inv = state.citizen_inventory.setdefault(buyer["bidder"], {})
                inv[good] = inv.get(good, 0) + got
                total_sold += got
                sold_records.append({"bidder": buyer["bidder"], "qty": got, "paid": paid})

        events.append({
            "tick": tick,
            "action": "MARKET_CLEAR_ESSENTIAL",
            "good": good,
            "listed": listed,
            "sold": total_sold,
            "buyers": sold_records,
        })

    # --- Pass 2: uniform-price auction for the rest
    for good in sorted(state.listings.keys()):
        entries = [e for e in state.listings[good] if e["qty"] > 0]
        if not entries:
            continue

        supply = sum(e["qty"] for e in entries)
        bids = auction_bids.get(good, [])
        bids.sort(key=lambda b: (-b["max_price"], b["bidder"], str(b["coop_id"])))

        winners: list[dict[str, Any]] = []
        remaining_supply = supply
        committed: dict[str, int] = {}  # payer key -> credits already promised
        for bid in bids:
            if remaining_supply <= 0:
                break
            take = min(bid["qty"], remaining_supply)
            # live funds re-check at settlement, accounting for cumulative
            # exposure: multiple winning bids by one payer must jointly fit
            key = bid["coop_id"] if bid["coop_id"] is not None else bid["bidder"]
            if bid["coop_id"] is not None:
                funds = state.coops[bid["coop_id"]].get("treasury", 0)
            else:
                funds = state.balances[bid["bidder"]]
            if funds - committed.get(key, 0) < take * bid["max_price"]:
                continue  # dropped: cannot pay at settlement
            committed[key] = committed.get(key, 0) + take * bid["max_price"]
            winners.append({"bid": bid, "take": take})
            remaining_supply -= take

        if not winners:
            _return_unsold(state, good)
            events.append({
                "tick": tick,
                "action": "MARKET_CLEAR_AUCTION",
                "good": good,
                "listed": supply,
                "sold": 0,
                "clearing_price": None,
                "surplus_delta": 0,
                "winners": [],
            })
            continue

        clearing = min(w["bid"]["max_price"] for w in winners)
        total_sold = supply - remaining_supply

        # buyers pay take x clearing (exact)
        for w in winners:
            bid = w["bid"]
            payment = w["take"] * clearing
            if bid["coop_id"] is not None:
                coop = state.coops[bid["coop_id"]]
                coop["treasury"] = coop.get("treasury", 0) - payment
                inv = coop["inventory"]
            else:
                state.balances[bid["bidder"]] -= payment
                inv = state.citizen_inventory.setdefault(bid["bidder"], {})
            inv[good] = inv.get(good, 0) + w["take"]

        # sellers receive floor per unit; pool receives clearing - floor (exact)
        surplus_delta = 0
        to_sell = total_sold
        for entry in entries:
            if to_sell <= 0:
                break
            take = min(entry["qty"], to_sell)
            floor_used = min(entry["floor"], clearing)
            seller = state.coops[entry["coop_id"]]
            seller["treasury"] = seller.get("treasury", 0) + take * floor_used
            state.treasury_in += take * floor_used
            surplus_delta += take * (clearing - floor_used)
            state.surplus_pool += take * (clearing - floor_used)
            entry["qty"] -= take
            to_sell -= take

        _return_unsold(state, good)

        events.append({
            "tick": tick,
            "action": "MARKET_CLEAR_AUCTION",
            "good": good,
            "listed": supply,
            "sold": total_sold,
            "clearing_price": clearing,
            "surplus_delta": surplus_delta,
            "winners": [
                {"bidder": w["bid"]["bidder"], "coop_id": w["bid"]["coop_id"], "qty": w["take"], "price": clearing}
                for w in winners
            ],
        })

    # --- Pass 3: retire pool beyond the cap
    cap = params.get("surplus_reserve_cap", 0)
    if state.surplus_pool > cap:
        excess = state.surplus_pool - cap
        state.surplus_pool -= excess
        state.money_retired += excess
        events.append({
            "tick": tick,
            "action": "SURPLUS_RETIRE",
            "excess_retired": excess,
            "pool_after": state.surplus_pool,
        })

    state.listings = {g: ls for g, ls in state.listings.items() if any(e["qty"] > 0 for e in ls)}
    state.bids = []
    return events


def _return_unsold(state: WorldState, good: str) -> int:
    """Return all remaining listed units to their sellers (exact, no rounding)."""
    remaining = 0
    for entry in state.listings.get(good, []):
        qty = entry["qty"]
        if qty > 0:
            coop = state.coops[entry["coop_id"]]
            coop["inventory"][good] = coop["inventory"].get(good, 0) + qty
            entry["qty"] = 0
            remaining += qty
    return remaining


# ------------------------------------------------------------- GOVERNANCE


def _gov_params(params: dict[str, Any]) -> dict[str, Any]:
    gov = params.get("governance") or {}
    return {
        "enabled": gov.get("enabled", False),
        "vote_window_ticks": gov.get("vote_window_ticks", 3),
        "quorum_bp": gov.get("quorum_bp", 5_000),
        "trial_period_ticks": gov.get("trial_period_ticks", 10),
    }


def _validate_propose(state: WorldState, tx: Transaction, params: dict[str, Any]) -> Reason | None:
    payload = tx.payload

    if tx.sender not in state.balances:
        return Reason.UNKNOWN_SENDER

    if not isinstance(payload, dict) or set(payload.keys()) != {"params", "activation_tick"}:
        return Reason.INVALID_PAYLOAD

    gov = _gov_params(params)
    if not gov["enabled"]:
        return Reason.GOVERNANCE_DISABLED

    activation = payload.get("activation_tick")
    if not _is_int(activation):
        return Reason.INVALID_PAYLOAD
    window_close = tx.tick + gov["vote_window_ticks"]
    if activation <= window_close:
        return Reason.ACTIVATION_IN_PAST  # must activate after the window closes

    reason = validate_params(payload.get("params"), known_goods=set(state.goods.keys()))
    if reason is not None:
        return reason

    # Constitutional guard: proposals may not disable governance or its ratchet
    if payload["params"].get("governance", {}).get("enabled") is False:
        return Reason.CONSTITUTIONAL_GUARD

    return None


def _apply_propose(state: WorldState, tx: Transaction, params: dict[str, Any]) -> dict[str, Any]:
    gov = _gov_params(params)
    proposal_id = f"p{state.next_proposal_id}"
    state.next_proposal_id += 1

    state.proposals[proposal_id] = {
        "proposal_id": proposal_id,
        "proposer": tx.sender,
        "params": dict(tx.payload["params"]),
        "activation_tick": tx.payload["activation_tick"],
        "opened_tick": tx.tick,
        "closes_tick": tx.tick + gov["vote_window_ticks"],
        "ballots": {},
        "status": "open",
        "is_rollback": False,
        "target_version": None,
        "change_tx_hash": tx.content_hash(),
    }

    return {
        "tick": tx.tick,
        "sender": tx.sender,
        "action": "PROPOSE",
        "proposal_id": proposal_id,
        "closes_tick": tx.tick + gov["vote_window_ticks"],
    }


def _validate_vote(state: WorldState, tx: Transaction, params: dict[str, Any]) -> Reason | None:
    payload = tx.payload

    if tx.sender not in state.balances:
        return Reason.UNKNOWN_SENDER

    if not isinstance(payload, dict) or set(payload.keys()) != {"proposal_id", "choice"}:
        return Reason.INVALID_PAYLOAD

    gov = _gov_params(params)
    if not gov["enabled"]:
        return Reason.GOVERNANCE_DISABLED

    proposal_id = payload.get("proposal_id")
    proposal = state.proposals.get(proposal_id)
    if proposal is None:
        return Reason.PROPOSAL_NOT_FOUND
    if proposal["status"] != "open":
        return Reason.VOTE_WINDOW_CLOSED
    if tx.tick > proposal["closes_tick"]:
        return Reason.VOTE_WINDOW_CLOSED

    if payload.get("choice") not in ("for", "against"):
        return Reason.INVALID_CHOICE

    if tx.sender in proposal["ballots"]:
        return Reason.ALREADY_VOTED  # one person, one vote — constitutional core #4

    return None


def _apply_vote(state: WorldState, tx: Transaction) -> dict[str, Any]:
    proposal = state.proposals[tx.payload["proposal_id"]]
    proposal["ballots"][tx.sender] = tx.payload["choice"]

    return {
        "tick": tx.tick,
        "sender": tx.sender,
        "action": "VOTE",
        "proposal_id": tx.payload["proposal_id"],
        "choice": tx.payload["choice"],
    }


def _validate_rollback(state: WorldState, tx: Transaction, params: dict[str, Any]) -> Reason | None:
    payload = tx.payload

    if tx.sender not in state.balances:
        return Reason.UNKNOWN_SENDER

    if not isinstance(payload, dict) or set(payload.keys()) != {"target_version"}:
        return Reason.INVALID_PAYLOAD

    gov = _gov_params(params)
    if not gov["enabled"]:
        return Reason.GOVERNANCE_DISABLED

    target = payload.get("target_version")
    if not _is_int(target):
        return Reason.INVALID_PAYLOAD

    target_doc = next((rs for rs in state.rulesets if rs["version"] == target), None)
    if target_doc is None:
        return Reason.TARGET_VERSION_NOT_FOUND
    if target == max(rs["version"] for rs in state.rulesets):
        return Reason.TARGET_VERSION_NOT_FOUND  # rolling back to the active version is meaningless

    # Constitutional guard: rollback target must not predate governance-on
    if not _gov_params(target_doc["params"])["enabled"] and _gov_params(params)["enabled"]:
        return Reason.CONSTITUTIONAL_GUARD

    return None


def _apply_rollback(state: WorldState, tx: Transaction, params: dict[str, Any]) -> dict[str, Any]:
    gov = _gov_params(params)
    target = tx.payload["target_version"]
    target_doc = next(rs for rs in state.rulesets if rs["version"] == target)

    proposal_id = f"p{state.next_proposal_id}"
    state.next_proposal_id += 1

    state.proposals[proposal_id] = {
        "proposal_id": proposal_id,
        "proposer": tx.sender,
        "params": dict(target_doc["params"]),
        "activation_tick": tx.tick + gov["vote_window_ticks"] + 1,
        "opened_tick": tx.tick,
        "closes_tick": tx.tick + gov["vote_window_ticks"],
        "ballots": {},
        "status": "open",
        "is_rollback": True,
        "target_version": target,
        "change_tx_hash": tx.content_hash(),
    }

    return {
        "tick": tx.tick,
        "sender": tx.sender,
        "action": "ROLLBACK",
        "proposal_id": proposal_id,
        "target_version": target,
        "closes_tick": tx.tick + gov["vote_window_ticks"],
    }


def _settle_proposals(state: WorldState, tick: int, params: dict[str, Any], ledger: Ledger) -> list[dict[str, Any]]:
    """End-of-tick proposal tally. Deterministic (spec §6)."""
    events: list[dict[str, Any]] = []
    if not state.proposals:
        return events

    gov = _gov_params(params)
    citizens = len(state.balances)
    quorum_needed = -(-citizens * gov["quorum_bp"] // 10_000)  # ceil
    hardened = params.get("constitution_phase") == "hardened"
    active_version_doc = next(rs for rs in state.rulesets if rs["version"] == max(r["version"] for r in state.rulesets if r["activated_at"] <= tick))
    trial_end = active_version_doc["activated_at"] + gov["trial_period_ticks"]

    for proposal_id in sorted(state.proposals.keys()):
        proposal = state.proposals[proposal_id]
        if proposal["status"] != "open" or tick < proposal["closes_tick"]:
            continue

        ballots = proposal["ballots"]
        cast = len(ballots)
        votes_for = sum(1 for c in ballots.values() if c == "for")
        votes_against = cast - votes_for

        passed = False
        if cast >= quorum_needed and cast > 0:
            # Asymmetric recovery (§6.3): rollback inside the trial period
            # of the active version needs only a simple majority.
            in_trial_rollback = proposal["is_rollback"] and tick <= trial_end
            if in_trial_rollback:
                passed = votes_for > votes_against
            elif hardened:
                passed = votes_for * 3 >= cast * 2  # >= 2/3 of cast
            else:
                passed = votes_for > votes_against  # strict majority; tie fails

        if passed:
            proposal["status"] = "passed"
            next_version = max(rs["version"] for rs in state.rulesets) + 1
            doc = RuleSetDoc(
                version=next_version,
                params=proposal["params"],
                activated_at=max(proposal["activation_tick"], tick + 1),
                change_tx_hash=proposal["change_tx_hash"],
            )
            state.rulesets.append(doc.to_dict())
            events.append({
                "tick": tick,
                "action": "PROPOSAL_SETTLED",
                "proposal_id": proposal_id,
                "result": "passed",
                "new_version": next_version,
                "activated_at": doc.activated_at,
                "votes_for": votes_for,
                "votes_against": votes_against,
                "is_rollback": proposal["is_rollback"],
            })
        else:
            proposal["status"] = "failed"
            events.append({
                "tick": tick,
                "action": "PROPOSAL_SETTLED",
                "proposal_id": proposal_id,
                "result": "failed",
                "votes_for": votes_for,
                "votes_against": votes_against,
            })

    return events



def apply_tick(
    state: WorldState,
    ledger: Ledger,
    actions: list[Transaction],
    *,
    current_tick: int | None = None,
) -> WorldState:
    """Process one tick's action batch deterministically.

    1. Resolve the active rule-set version for this tick (D7 pinning).
    2. Sort actions deterministically.
    3. Validate each under the active rules; accept or reject (both logged).
    4. Apply accepted actions; stamp state with tick + active version.
    """
    tick = state.tick + 1 if current_tick is None else current_tick

    # Version pinning: the version active for THIS tick, resolved from history
    from .rules import active_version

    version_for_tick = active_version(
        [RuleSetDoc.from_dict(rs) for rs in state.rulesets], tick
    )
    params = None
    for rs in state.rulesets:
        if rs["version"] == version_for_tick:
            params = rs["params"]
            break
    if params is None:  # pragma: no cover — defensive
        raise RuntimeError(f"ruleset v{version_for_tick} missing from state")

    seen: set[str] = set()
    for tx in sorted(actions, key=Transaction.sort_key):
        if tx.tick != tick:
            ledger.reject(tx, Reason.MALFORMED_TRANSACTION)
            continue

        if tx.action not in SUPPORTED_ACTIONS:
            ledger.reject(tx, Reason.INVALID_PAYLOAD)
            continue

        # A transaction must be pinned to the version active for this tick.
        # RULE_CHANGE declares the CURRENT version it amends (it changes rules
        # from a strictly future tick, so it executes under today's rules).
        if tx.action == "RULE_CHANGE":
            if tx.ruleset_version != version_for_tick:
                ledger.reject(tx, Reason.RULESET_MISMATCH)
                continue
        elif tx.ruleset_version != version_for_tick:
            ledger.reject(tx, Reason.RULESET_MISMATCH)
            continue

        content_hash = tx.content_hash()
        if content_hash in seen:
            ledger.reject(tx, Reason.DUPLICATE_TRANSACTION)
            continue

        validator = {
            "TRANSFER": lambda t: _validate_transfer(state, t, params),
            "RULE_CHANGE": lambda t: _validate_rule_change(state, t, params),
            "FOUND_COOP": lambda t: _validate_found_coop(state, t, params),
            "JOIN_COOP": lambda t: _validate_join_coop(state, t, params),
            "WORK": lambda t: _validate_work(state, t, params),
            "PRODUCE": lambda t: _validate_produce(state, t, params),
            "LIST_GOOD": lambda t: _validate_list_good(state, t, params),
            "BID": lambda t: _validate_bid(state, t, params),
            "BID_FOR_COOP": lambda t: _validate_bid_for_coop(state, t, params),
            "BUY_ESSENTIAL": lambda t: _validate_buy_essential(state, t, params),
            "PROPOSE": lambda t: _validate_propose(state, t, params),
            "VOTE": lambda t: _validate_vote(state, t, params),
            "ROLLBACK": lambda t: _validate_rollback(state, t, params),
        }[tx.action]

        reason = validator(tx)
        if reason is not None:
            ledger.reject(tx, reason)
            continue

        seen.add(content_hash)
        ledger.accept(tx)
        if tx.action == "RULE_CHANGE":
            entry = _apply_rule_change(state, tx, ledger)
        elif tx.action == "FOUND_COOP":
            entry = _apply_found_coop(state, tx, params)
        elif tx.action == "WORK":
            entry = _apply_work(state, tx, params)
        elif tx.action == "PRODUCE":
            entry = _apply_produce(state, tx, params)
        elif tx.action == "PROPOSE":
            entry = _apply_propose(state, tx, params)
        elif tx.action == "ROLLBACK":
            entry = _apply_rollback(state, tx, params)
        else:
            entry = {
                "TRANSFER": _apply_transfer,
                "JOIN_COOP": _apply_join_coop,
                "LIST_GOOD": _apply_list_good,
                "BID": _apply_bid,
                "BID_FOR_COOP": _apply_bid_for_coop,
                "BUY_ESSENTIAL": _apply_buy_essential,
                "VOTE": _apply_vote,
            }[tx.action](state, tx)
        state.applied.append(entry)

    # End-of-tick market clearing (deterministic) — spec §9
    market_events = _clear_markets(state, tick, params, ledger)
    state.applied.extend(market_events)

    # End-of-tick governance settlement (deterministic) — spec §6
    gov_events = _settle_proposals(state, tick, params, ledger)
    state.applied.extend(gov_events)

    state.tick = tick
    state.ruleset_version = version_for_tick
    return state
