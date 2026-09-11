"""Realism contract L4 - Land market (spec 2026-09-11-land-market-l4.md).

Land is the canonical NON-PRODUCED asset: fixed supply (Ricardo),
appreciating with population, and the classic inequality channel.
Market-socialism framing: society owns all parcels at genesis; citizens
may buy at the assessed price, sell back to the land bank at 90%
(society keeps the 10% uplift), and pay a Georgist land-value tax
(LVT) that captures the rent for everyone (surplus pool). Unpaid LVT
forecloses the parcel back to society.

Rule-gated via params['land_market']: absent => inert, old worlds replay
byte-identically. Determinism: integer-only, no rng.
"""
from __future__ import annotations

from typing import Any

from .errors import Reason
from .state import WorldState

QUALITY_TIERS = (12_000, 10_000, 8_000)  # bp, cycled by parcel index


def _cfg(params: dict[str, Any]) -> dict[str, Any] | None:
    cfg = params.get("land_market") or {}
    return cfg if cfg.get("enabled") else None


def init_parcels(
    state: WorldState, params: dict[str, Any]
) -> None:
    """Create the FIXED parcel stock at genesis (society-owned). Count
    scales with the founding population; quality tiers cycle by index.
    Called only when the rule is enabled at genesis."""
    cfg = params.get("land_market") or {}
    if not cfg.get("enabled"):
        return
    n = max(4, len(state.balances) // 2)
    for i in range(n):
        state.land_parcels[f"p{i:03d}"] = {
            "owner": "society",
            "quality_bp": QUALITY_TIERS[i % len(QUALITY_TIERS)],
        }
    state.land_genesis_pop = len(state.balances)


def assess(state: WorldState, pid: str, params: dict[str, Any]) -> int:
    """Current assessed price: base x quality_bp // 10000, APPRECIATED by
    population growth (current // genesis, floor 1). Integer, min 1.
    Land appreciates because more people chase the same stock (Ricardo)."""
    cfg = params.get("land_market") or {}
    mc = params.get("money_cap") or {}
    upc = int(mc.get("units_per_credit", 100)) if mc.get("enabled") else 1
    base = max(1, int(cfg.get("base_land_price", 500))) * upc
    parcel = state.land_parcels.get(pid) or {}
    quality = max(1, int(parcel.get("quality_bp", 10_000)))
    gen = max(1, int(state.land_genesis_pop or len(state.balances) or 1))
    growth = max(1, len(state.balances) // gen)
    return max(1, base * quality // 10_000 * growth)


# ------------------------------------------------------------------ phase


def land_phase(state: WorldState, tick: int, params: dict[str, Any]) -> list[dict[str, Any]]:
    """Per-tick Georgist LVT: every privately-held parcel pays
    land_tax_bp of its assessment into the surplus pool. An owner who
    cannot pay accrues a due-counter; past grace_ticks the parcel
    forecloses to society (due-counter cleared). Deterministic order:
    sorted pids."""
    cfg = _cfg(params)
    if not cfg:
        return []
    # 1bp/tick ~= 3.6%/yr at 1 tick = 1 day - the Georgist range
    # (L1 interest uses the same tick=day convention)
    bp = max(0, min(10_000, int(cfg.get("land_tax_bp", 1))))
    grace = max(1, int(cfg.get("grace_ticks", 5)))
    events: list[dict[str, Any]] = []
    if bp <= 0:
        return events
    for pid in sorted(state.land_parcels.keys()):
        parcel = state.land_parcels[pid]
        owner = parcel.get("owner")
        if owner == "society" or owner not in state.balances:
            continue
        tax = assess(state, pid, params) * bp // 10_000
        if tax <= 0:
            continue
        if state.balances[owner] >= tax:
            state.balances[owner] -= tax
            state.surplus_pool += tax
            state.land_tax_due.pop(pid, None)
            events.append({
                "tick": tick,
                "action": "LAND_TAX",
                "parcel": pid,
                "owner": owner,
                "amount": tax,
            })
        else:
            due = state.land_tax_due.get(pid, 0) + 1
            state.land_tax_due[pid] = due
            if due >= grace:
                parcel["owner"] = "society"
                state.land_tax_due.pop(pid, None)
                events.append({
                    "tick": tick,
                    "action": "LAND_FORECLOSE",
                    "parcel": pid,
                    "owner": owner,
                })
            else:
                events.append({
                    "tick": tick,
                    "action": "LAND_TAX_DUE",
                    "parcel": pid,
                    "owner": owner,
                    "due": due,
                })
    return events


# --------------------------------------------------------------- validators


def validate_buy_land(state: WorldState, tx: Any, params: dict[str, Any]) -> str | None:
    """BUY_LAND {pid}: parcel exists, is society-owned, buyer can pay the
    (current, appreciated) assessment."""
    if not _cfg(params):
        return Reason.INVALID_PAYLOAD
    payload = tx.payload or {}
    if set(payload.keys()) != {"pid"}:
        return Reason.INVALID_PAYLOAD
    pid = payload.get("pid")
    parcel = state.land_parcels.get(pid)
    if parcel is None:
        return Reason.INVALID_PAYLOAD
    if parcel.get("owner") != "society":
        return Reason.INVALID_PAYLOAD
    if tx.sender not in state.balances:
        return Reason.UNKNOWN_SENDER
    if state.balances[tx.sender] < assess(state, pid, params):
        return Reason.INSUFFICIENT_CREDITS
    return None


def validate_sell_land(state: WorldState, tx: Any, params: dict[str, Any]) -> str | None:
    """SELL_LAND {pid}: sender privately owns the parcel; the bank pays
    90% of assessment (only ever owes what the pool holds - the pool is
    society's book and always covers 90% of assessments in practice;
    checked against surplus_pool explicitly)."""
    if not _cfg(params):
        return Reason.INVALID_PAYLOAD
    payload = tx.payload or {}
    if set(payload.keys()) != {"pid"}:
        return Reason.INVALID_PAYLOAD
    pid = payload.get("pid")
    parcel = state.land_parcels.get(pid)
    if parcel is None:
        return Reason.INVALID_PAYLOAD
    if parcel.get("owner") != tx.sender:
        return Reason.INVALID_PAYLOAD
    payout = assess(state, pid, params) * 9_000 // 10_000
    if state.surplus_pool < payout:
        return Reason.INSUFFICIENT_CREDITS
    return None


# ----------------------------------------------------------------- appliers


def apply_buy_land(state: WorldState, tx: Any, params: dict[str, Any]) -> dict[str, Any]:
    pid = tx.payload["pid"]
    price = assess(state, pid, params)
    state.balances[tx.sender] -= price
    state.surplus_pool += price  # society's book receives the price
    state.land_parcels[pid]["owner"] = tx.sender
    return {
        "tick": tx.tick,
        "action": "LAND_BOUGHT",
        "parcel": pid,
        "buyer": tx.sender,
        "price": price,
    }


def apply_sell_land(state: WorldState, tx: Any, params: dict[str, Any]) -> dict[str, Any]:
    pid = tx.payload["pid"]
    price = assess(state, pid, params)
    payout = price * 9_000 // 10_000  # 90% buyback; 10% uplift stays social
    state.surplus_pool -= payout
    state.balances[tx.sender] += payout
    state.land_parcels[pid]["owner"] = "society"
    state.land_tax_due.pop(pid, None)
    return {
        "tick": tx.tick,
        "action": "LAND_SOLD",
        "parcel": pid,
        "seller": tx.sender,
        "payout": payout,
        "assessment": price,
    }
