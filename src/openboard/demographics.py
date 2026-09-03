"""Stage 5 - Demographics: births, childhood, real death integration.

Spec section 2 (2026-08-26): the world simulates real life - births always
flow, children consume (scaled) needs and take time to grow before they can
WORK; shocks kill for real (see shocks._kill_citizen). Rule-gated via
params['demographics']: absent means inert, old worlds replay identically.

Determinism: no rng here; birth timing is pure modular arithmetic on the
tick, citizen ids are assigned from an internal counter.
"""
from __future__ import annotations

from typing import Any

from .state import WorldState


def _demog(params: dict[str, Any]) -> dict[str, Any] | None:
    cfg = params.get("demographics") or {}
    return cfg if cfg.get("enabled") else None


def _next_citizen_id(state: WorldState) -> str:
    """Deterministic id: 'gen2_1', 'gen2_2', ... (birth order only)."""
    n = 0
    for cid in state.balances:
        if cid.startswith("gen2_"):
            try:
                n = max(n, int(cid.split("_", 1)[1]))
            except ValueError:
                continue
    return f"gen2_{n + 1}"


def demographics_phase(
    state: WorldState, tick: int, params: dict[str, Any]
) -> list[dict[str, Any]]:
    """Births + aging, run before market phases each tick.

    Birth (every birth_interval_ticks): new citizen with the standard
    500-credit stake, MINTED (mirrors genesis stakes; keeps the money
    invariant exact: total = base + money_minted - money_retired).
    Emits CITIZEN_BORN.

    Aging: every living citizen's age += 1 per tick. CITIZEN_ADULT fires
    once, at the tick the citizen crosses adulthood_ticks.

    Children (age < adulthood_ticks):
      - may NOT WORK (engine _validate_work rejects),
      - consume scaled needs (child_need_pct, integer),
      - are still full citizens: dividends and dignity floor apply.
    """
    cfg = _demog(params)
    if not cfg:
        return []
    events: list[dict[str, Any]] = []

    # 1) birth
    interval = max(1, int(cfg.get("birth_interval_ticks", 400)))
    # Crisis birth suppression (realism pack): families don't grow during
    # famines/emergencies. Skip the birth slot while a ratified crisis is
    # active — the slot is simply skipped (next birth at the next interval
    # multiple), keeping ids and the invariant untouched.
    from .crisis import crisis_active
    if tick % interval == 0 and not crisis_active(state):
        stake = 500
        # D14 flaw fix L3: the welcome stake is society's cost, not new
        # money. Fund it from the surplus pool first; mint only the
        # shortfall. Opt-in via params["birth_stake_from_pool"]; legacy
        # worlds (param absent) keep the v0.01 mint-everything behavior.
        # Fixed supply (money_cap): minting is FORBIDDEN — the stake is
        # what the pool can afford (never minted).
        minted = stake
        mc = (params or {}).get("money_cap") or {}
        if mc.get("enabled"):
            upc = int(mc.get("units_per_credit", 100))
            stake = 500 * upc
            from_pool = min(int(state.surplus_pool), stake)
            state.surplus_pool -= from_pool
            minted = 0  # fixed supply never mints
            stake = from_pool  # citizen receives what society could give
        elif (params or {}).get("birth_stake_from_pool"):
            from_pool = min(int(state.surplus_pool), stake)
            state.surplus_pool -= from_pool
            minted = stake - from_pool
        cid = _next_citizen_id(state)
        if stake > 0:
            state.balances[cid] = stake
        state.money_minted += minted
        state.citizen_inventory[cid] = {}
        meta = state.citizens_meta.setdefault(cid, {})
        meta["age"] = 0
        meta["alive"] = True
        meta["child"] = True
        events.append({
            "tick": tick,
            "action": "CITIZEN_BORN",
            "citizen": cid,
            "stake": stake,
        })

    # 2) aging + adulthood crossing
    adulthood = max(1, int(cfg.get("adulthood_ticks", 600)))
    for cid in sorted(state.balances.keys()):
        meta = state.citizens_meta.setdefault(cid, {})
        if not meta.get("alive", True):
            continue
        if "age" not in meta:
            # Genesis citizens (and pre-demographics worlds) are ADULTS:
            # baseline them beyond adulthood instead of age 0 (which
            # would wrongly classify every existing citizen as a child
            # and freeze all labor).
            meta["age"] = adulthood + 1
        age = int(meta["age"]) + 1
        meta["age"] = age
        if age == adulthood + 1:  # crossed during childhood (birth age 0)
            meta["adult"] = True
            events.append({"tick": tick, "action": "CITIZEN_ADULT", "citizen": cid})
        elif age > adulthood and not meta.get("adult"):
            # existing-world citizens (genesis adults) are marked on the
            # first tick under demographics, without a false ADULT event
            # storm: only the crossing tick emits the event.
            meta["adult"] = True
    return events


def is_child(state: WorldState, cid: str, params: dict[str, Any]) -> bool:
    """True while the citizen is under adulthood_ticks (demographics on)."""
    cfg = _demog(params)
    if not cfg:
        return False
    meta = state.citizens_meta.get(cid)
    if not meta or not meta.get("alive", True):
        return False
    if "age" not in meta:
        return False  # no age recorded: genesis/pre-demographics adult
    return int(meta["age"]) <= int(cfg.get("adulthood_ticks", 600))


def child_need_pct(params: dict[str, Any]) -> int:
    """Children consume this integer percentage of each quota (default 50)."""
    cfg = params.get("demographics") or {}
    return max(1, min(100, int(cfg.get("child_need_pct", 50))))
