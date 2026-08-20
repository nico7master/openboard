"""Deterministic tick engine (Phase 1).

Spec §5/T4: one tick = one action batch, settled in fixed deterministic
order — sorted by (sender, action, content hash, ruleset version). No
wall-clock, no randomness. Rejections are ledger records, never crashes.
"""

from __future__ import annotations

from typing import Any

from .errors import Reason
from .ledger import Ledger, Transaction
from .state import WorldState

SUPPORTED_ACTIONS = frozenset({"TRANSFER"})


def _validate_transfer(state: WorldState, tx: Transaction) -> Reason | None:
    """Return a rejection reason, or None if the action is applicable."""
    payload: dict[str, Any] = tx.payload

    if tx.sender not in state.balances:
        return Reason.UNKNOWN_SENDER

    if not isinstance(payload, dict) or set(payload.keys()) != {"to", "amount"}:
        return Reason.INVALID_PAYLOAD

    amount = payload.get("amount")
    to = payload.get("to")

    if isinstance(amount, bool) or not isinstance(amount, int):
        return Reason.NON_INTEGER_AMOUNT
    if to not in state.balances:
        return Reason.UNKNOWN_CITIZEN
    if amount <= 0:
        return Reason.RULE_VIOLATION
    if state.balances[tx.sender] < amount:
        return Reason.INSUFFICIENT_CREDITS
    return None


_VALIDATORS = {"TRANSFER": _validate_transfer}


def _apply_transfer(state: WorldState, tx: Transaction) -> dict[str, Any]:
    """Mutate state; return the applied-action entry for the public log."""
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


_APPLIERS = {"TRANSFER": _apply_transfer}


def apply_tick(
    state: WorldState,
    ledger: Ledger,
    actions: list[Transaction],
    *,
    current_tick: int | None = None,
) -> WorldState:
    """Process one tick's action batch deterministically.

    Ordering: sort_key() — (sender, action, content_hash, ruleset_version).
    Duplicate transactions within a tick are rejected after the first.
    The ledger records every outcome; the state hash changes only via
    accepted actions and the tick counter.
    """
    tick = state.tick + 1 if current_tick is None else current_tick

    seen: set[str] = set()
    for tx in sorted(actions, key=Transaction.sort_key):
        # Transactions must reference the tick being processed
        if tx.tick != tick:
            ledger.reject(tx, Reason.MALFORMED_TRANSACTION)
            continue

        if tx.action not in SUPPORTED_ACTIONS:
            ledger.reject(tx, Reason.INVALID_PAYLOAD)
            continue

        content_hash = tx.content_hash()
        if content_hash in seen:
            ledger.reject(tx, Reason.DUPLICATE_TRANSACTION)
            continue

        reason = _VALIDATORS[tx.action](state, tx)
        if reason is not None:
            ledger.reject(tx, reason)
            continue

        seen.add(content_hash)
        ledger.accept(tx)
        entry = _APPLIERS[tx.action](state, tx)
        state.applied.append(entry)

    state.tick = tick
    return state
