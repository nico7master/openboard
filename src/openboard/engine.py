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

SUPPORTED_ACTIONS = frozenset({"TRANSFER", "RULE_CHANGE", "FOUND_COOP", "JOIN_COOP", "WORK", "PRODUCE"})


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

    # Cost baseline: (labor + energy + material inputs) // total output units
    labor_cost = recipe["labor_hours"] * runs  # 1 credit/hour base accounting
    energy_cost = energy_consumed * params.get("energy_price", 2)
    input_cost = sum(
        qty * runs * state.good_cost_baseline.get(good, 1) for good, qty in recipe["inputs"].items()
    )
    total_units = sum(outputs_produced.values())

    baselines_stamped: dict[str, int] = {}
    if total_units > 0:
        unit_baseline = (labor_cost + energy_cost + input_cost) // total_units
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


# -------------------------------------------------------------------- ENGINE


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
        else:
            entry = {
                "TRANSFER": _apply_transfer,
                "JOIN_COOP": _apply_join_coop,
            }[tx.action](state, tx)
        state.applied.append(entry)

    state.tick = tick
    state.ruleset_version = version_for_tick
    return state
