"""Realism contract L5 - Foreign sector (spec 2026-09-11-foreign-sector-l5.md).

An open economy arbitrages the world price: it imports what is cheaper
abroad and exports what earns more abroad. World-price shocks transmit
into domestic scarcity (terms-of-trade stress for the adversary lab).
The world market is a PRICE-TAKER counterparty: unlimited quantity at
the posted integer price, netted in ONE conserved money bucket
(state.foreign_balance). A negative bucket is a trade SURPLUS in our
favor (the world owes us - a real claim, exactly like real trade
balances); a positive bucket is what we owe for imports. No-mint is
preserved because every unit the world pays is offset inside its own
bucket: balances + pool + treasuries + foreign_balance is constant.

Rule-gated via params['foreign_sector']: absent => closed economy,
old worlds replay byte-identically. Determinism: integer-only, no rng
(shocks are a tick-scheduled table in params).
"""
from __future__ import annotations

from typing import Any

from .errors import Reason
from .state import WorldState


def _cfg(params: dict[str, Any]) -> dict[str, Any] | None:
    cfg = params.get("foreign_sector") or {}
    return cfg if cfg.get("enabled") else None


def world_price(state: WorldState, good: str, params: dict[str, Any]) -> int:
    """Effective world price (units) for a good: the params table entry,
    then the LAST applied shock at or before this tick (deterministic
    scan of the sorted schedule). 0 if the good is not traded."""
    cfg = _cfg(params)
    if not cfg:
        return 0
    table = cfg.get("world_prices") or {}
    if good not in table:
        return 0
    price = int(table[good])
    tick = state.tick
    for shock in sorted(cfg.get("shocks") or [], key=lambda s: (s.get("tick", 0), s.get("good", ""))):
        if shock.get("good") == good and int(shock.get("tick", 0)) <= tick:
            price = int(shock.get("price", price))
    return max(1, price)


def _units(params: dict[str, Any]) -> int:
    mc = params.get("money_cap") or {}
    return int(mc.get("units_per_credit", 100)) if mc.get("enabled") else 1


# --------------------------------------------------------------- validators


def validate_import(state: WorldState, tx: Any, params: dict[str, Any]) -> Reason | None:
    """IMPORT_GOOD {good, qty}: good is traded, qty positive integer,
    buyer (citizen or coop treasury) can pay price x (1 + tariff)."""
    if not _cfg(params):
        return Reason.INVALID_PAYLOAD
    payload = tx.payload or {}
    if set(payload.keys()) != {"good", "qty"}:
        return Reason.INVALID_PAYLOAD
    good, qty = payload.get("good"), payload.get("qty")
    if good not in state.goods:
        return Reason.GOOD_UNKNOWN
    if not isinstance(qty, int) or isinstance(qty, bool) or qty <= 0:
        return Reason.INVALID_QTY
    if tx.sender not in state.balances:
        return Reason.UNKNOWN_SENDER
    price = world_price(state, good, params)
    if price <= 0:
        return Reason.GOOD_UNKNOWN
    tariff = int(_cfg(params).get("tariff_bp", 0))
    cost = price * qty * (10_000 + tariff) // 10_000
    if state.balances[tx.sender] < cost:
        return Reason.INSUFFICIENT_CREDITS
    return None


def validate_export(state: WorldState, tx: Any, params: dict[str, Any]) -> Reason | None:
    """EXPORT_GOOD {good, qty}: good is traded, qty positive integer,
    seller (citizen) holds the inventory, and the world's bucket can pay
    (never negative - the world only buys what it was first sold)."""
    if not _cfg(params):
        return Reason.INVALID_PAYLOAD
    payload = tx.payload or {}
    if set(payload.keys()) != {"good", "qty"}:
        return Reason.INVALID_PAYLOAD
    good, qty = payload.get("good"), payload.get("qty")
    if good not in state.goods:
        return Reason.GOOD_UNKNOWN
    if not isinstance(qty, int) or isinstance(qty, bool) or qty <= 0:
        return Reason.INVALID_QTY
    if tx.sender not in state.balances:
        return Reason.UNKNOWN_SENDER
    if world_price(state, good, params) <= 0:
        return Reason.GOOD_UNKNOWN
    held = (state.citizen_inventory.get(tx.sender) or {}).get(good, 0)
    if held < qty:
        return Reason.NOT_ENOUGH_INPUTS
    # NOTE: no foreign_balance floor here - a negative bucket IS a trade
    # surplus in our favor (the world owes us, a real claim). No-mint is
    # preserved: every paid unit is offset inside the world's bucket, so
    # the extended conservation identity holds exactly.
    return None


# ----------------------------------------------------------------- appliers


def apply_import(state: WorldState, tx: Any, params: dict[str, Any]) -> dict[str, Any]:
    good, qty = tx.payload["good"], tx.payload["qty"]
    cfg = _cfg(params)
    tariff = int(cfg.get("tariff_bp", 0))
    price = world_price(state, good, params)
    net = price * qty                      # what the world receives
    tariff_take = net * tariff // 10_000   # the people's cut
    gross = net + tariff_take              # what the buyer pays
    state.balances[tx.sender] -= gross
    state.foreign_balance += net           # the world receives its price
    state.surplus_pool += tariff_take      # tariff = the people's cut
    inv = state.citizen_inventory.setdefault(tx.sender, {})
    inv[good] = inv.get(good, 0) + qty
    return {
        "tick": tx.tick,
        "action": "IMPORT_DONE",
        "sender": tx.sender,
        "good": good,
        "qty": qty,
        "world_price": price,
        "tariff": tariff_take,
    }


def apply_export(state: WorldState, tx: Any, params: dict[str, Any]) -> dict[str, Any]:
    good, qty = tx.payload["good"], tx.payload["qty"]
    earnings = world_price(state, good, params) * qty
    inv = state.citizen_inventory.setdefault(tx.sender, {})
    inv[good] = inv.get(good, 0) - qty
    state.foreign_balance -= earnings     # the world pays from its bucket
    state.balances[tx.sender] += earnings
    return {
        "tick": tx.tick,
        "action": "EXPORT_DONE",
        "sender": tx.sender,
        "good": good,
        "qty": qty,
        "world_price": world_price(state, good, params),
        "earnings": earnings,
    }
