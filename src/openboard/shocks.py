"""Stage 5 · Shock engine (spec §1).

Deterministic, seed-driven world events; every event lands in state.applied
so replays stay byte-exact. The 'battery' profile is TEST-ONLY instrumentation
that escalates severity and reports the honest breaking tier.
"""
from __future__ import annotations

import random
from typing import Any

from .state import WorldState

# per_tick_bp: chance (basis points / tick) any shock fires.
# events: weighted [(kind, weight)] table. pandemic only where allowed.
PROFILES: dict[str, dict[str, Any]] = {
    "off": {"per_tick_bp": 0},
    "peaceful": {
        "per_tick_bp": 15,
        "events": [
            ("drought", 3000), ("outage", 2500), ("spoilage", 2000),
            ("demand_shift", 2500)],
    },
    "standard": {
        "per_tick_bp": 40,
        "events": [
            ("drought", 3000), ("outage", 2000), ("spoilage", 1500),
            ("machine_failure_wave", 1500), ("demand_shift", 1500),
            ("pandemic", 500)],
        "pandemic": True,
    },
    "harsh": {
        "per_tick_bp": 80,
        "events": [
            ("drought", 2500), ("outage", 2000), ("spoilage", 1500),
            ("machine_failure_wave", 1500), ("demand_shift", 1000),
            ("pandemic", 1500)],
        "pandemic": True,
    },
    "apocalyptic": {
        "per_tick_bp": 150,
        "events": [
            ("drought", 2000), ("outage", 2000), ("spoilage", 1500),
            ("machine_failure_wave", 1500), ("demand_shift", 1000),
            ("pandemic", 2000)],
        "pandemic": True,
    },
    # TEST-ONLY: severity escalates every tier_ticks until something breaks.
    "battery": {
        "per_tick_bp": 100,
        "events": [
            ("drought", 2500), ("outage", 2000), ("spoilage", 1500),
            ("machine_failure_wave", 1500), ("demand_shift", 1500),
            ("pandemic", 1000)],
        "pandemic": True,
        "escalating": True,
        "tier_ticks": 250,
        "tiers": ["mild", "moderate", "severe", "extreme", "fatal"],
    },
}

# Severity ladders per kind: tier index -> (magnitude_pct, duration_ticks)
LADDERS: dict[str, list[tuple[int, int]]] = {
    "drought": [(20, 60), (35, 90), (50, 120), (65, 150), (80, 200)],
    "outage": [(30, 40), (50, 70), (70, 100), (85, 140), (100, 180)],
    "spoilage": [(15, 1), (25, 1), (35, 2), (45, 3), (60, 4)],
    "machine_failure_wave": [(10, 30), (20, 50), (30, 70), (45, 100), (60, 130)],
    "demand_shift": [(10, 999999), (15, 999999), (20, 999999), (30, 999999), (40, 999999)],
    "pandemic": [(25, 80, 0), (40, 100, 0), (55, 120, 1), (65, 150, 2), (75, 200, 5)],
}
FOOD_GOODS = ("bread", "meat", "eggs", "milk", "cheese", "fruit", "vegetables", "meals")
FARM_RECIPES = ("grain_farming", "vegetable_farming", "orchard")


def _tier(profile_cfg: dict[str, Any], tick: int) -> int:
    if not profile_cfg.get("escalating"):
        return 1  # fixed profiles run at 'moderate' magnitude
    return min(len(profile_cfg["tiers"]) - 1, tick // profile_cfg["tier_ticks"])


def _roll(rng: random.Random, cfg: dict[str, Any]) -> str | None:
    if rng.random() * 10000 >= cfg["per_tick_bp"]:
        return None
    total = sum(w for _, w in cfg["events"])
    x = rng.randrange(total)
    acc = 0
    for kind, w in cfg["events"]:
        acc += w
        if x < acc:
            return kind
    return None  # pragma: no cover


# ------------------------------------------------------------ death & meta


def _citizen_meta(state: WorldState, cid: str) -> dict[str, Any]:
    return state.citizens_meta.setdefault(cid, {"age": 0, "sick": False, "alive": True})


def _kill_citizen(state: WorldState, tick: int, cid: str) -> None:
    """Real death (spec §1): stake → surplus pool, inventory → common pool,
    memberships end. Dignity floor: only shock events kill, never markets."""
    meta = _citizen_meta(state, cid)
    if not meta.get("alive", True):
        return
    meta["alive"] = False
    state.surplus_pool += state.balances.pop(cid, 0)
    inv = state.citizen_inventory.pop(cid, {})
    for g, q in inv.items():
        state.common_pool[g] = state.common_pool.get(g, 0) + q
    for coop in state.coops.values():
        members = coop.get("members", [])
        if cid in members:
            members.remove(cid)
    state.unmet_needs.pop(cid, None)
    # remove from labor pools of coops
    for coop in state.coops.values():
        pool = coop.get("labor_pool_hours", {})
        if isinstance(pool, dict) and cid in pool:
            del pool[cid]
    state.applied.append({"tick": tick, "action": "CITIZEN_DEATH", "citizen": cid})


def _sick_factor(state: WorldState, cid: str) -> int:
    """Labor-hours multiplier in ‰ (1000 = healthy) for pandemic reduction.
    Pure integer; applied at produce-time aggregation."""
    meta = state.citizens_meta.get(cid)
    if meta and meta.get("sick"):
        return 400  # sick citizens contribute ~40%
    return 1000


# ------------------------------------------------------------- tick driver


def roll_shock(state: WorldState, tick: int, rng: random.Random) -> None:
    """Roll one event per tick under the active profile (rule-gated).
    Deterministic: rng must be constructed per-tick from the world seed."""
    cfg_shocks = state.active_ruleset_params().get("shocks") or {}
    if not cfg_shocks.get("enabled"):
        return
    prof_name = cfg_shocks.get("profile", "off")
    cfg = PROFILES.get(prof_name)
    if not cfg or cfg["per_tick_bp"] <= 0:
        return
    kind = _roll(rng, cfg)
    if kind == "pandemic" and not cfg.get("pandemic", False):
        kind = None
    if kind is None:
        return
    tier = _tier(cfg, tick)
    ladder = LADDERS[kind]
    spec = ladder[min(tier, len(ladder) - 1)]
    magnitude, duration = int(spec[0]), int(spec[1])
    event: dict[str, Any] = {
        "tick": tick,
        "action": "SHOCK_START",
        "kind": kind,
        "magnitude_pct": magnitude,
        "duration_ticks": duration,
        "tier": tier,
    }
    if kind == "demand_shift":
        non_essential = [g for g in state.goods if g not in FOOD_GOODS and g != "electricity" and g != "water"]
        good = sorted(non_essential)[rng.randrange(len(non_essential))]
        direction = rng.choice(["up", "down"])
        event["good"] = good
        event["direction"] = direction
        state.research["demand_shift"] = {"good": good, "direction": direction}
    state.active_shocks.append({
        "kind": kind, "start": tick, "end": tick + duration,
        "magnitude_pct": magnitude, **({k: event[k] for k in ('good', 'direction')} if 'good' in event else {}),
    })
    # immediate-effect kinds resolve now
    if kind == "spoilage":
        destroyed_total = 0
        for g in FOOD_GOODS:
            for cid in list(state.citizen_inventory.keys()):
                inv = state.citizen_inventory[cid]
                if g in inv:
                    take = inv[g] * magnitude // 100
                    inv[g] -= take
                    destroyed_total += take
            for coop in state.coops.values():
                cinv = coop.get("inventory", {})
                if g in cinv:
                    take = cinv[g] * magnitude // 100
                    cinv[g] -= take
                    destroyed_total += take
        event["destroyed_units"] = destroyed_total
    elif kind == "machine_failure_wave":
        event["applies_to"] = "produce_runs"
    elif kind == "pandemic":
        kills = int(spec[2]) if len(spec) > 2 else 0
        alive = [c for c, m in state.citizens_meta.items()
                 if m.get("alive", True)] if state.citizens_meta else []
        alive = alive or sorted(state.balances.keys())
        victims = sorted(alive)[:kills]  # deterministic victim choice
        for v in victims:
            _kill_citizen(state, tick, v)
        for cid in state.balances:
            _citizen_meta(state, cid)["sick"] = True
        event["deaths"] = victims
        event["sickened"] = len(state.balances)
    state.applied.append(event)


# ------------------------------------------------------- effect accessors


def _active(state: WorldState, kind: str) -> dict[str, Any] | None:
    for sh in state.active_shocks:
        if sh["kind"] == kind and sh["end"] > state.tick:
            return sh
    return None


def farm_output_factor(state: WorldState) -> int:
    """Farm output multiplier in ‰ (1000 = normal)."""
    d = _active(state, "drought")
    return 1000 - d["magnitude_pct"] * 10 if d else 1000


def power_disabled(state: WorldState) -> bool:
    return _active(state, "outage") is not None


def machine_failure_pct(state: WorldState) -> int:
    m = _active(state, "machine_failure_wave")
    return m["magnitude_pct"] if m else 0


def expire_finished(state: WorldState, tick: int) -> list[dict[str, Any]]:
    """End shocks whose duration elapsed; clear sickness with pandemics."""
    ended = [sh for sh in state.active_shocks if sh["end"] <= tick]
    if not ended:
        return []
    state.active_shocks = [sh for sh in state.active_shocks if sh["end"] > tick]
    events = []
    for sh in ended:
        ev = {"tick": tick, "action": "SHOCK_END", "kind": sh["kind"],
              "start": sh["start"], "magnitude_pct": sh["magnitude_pct"]}
        if sh["kind"] == "pandemic":
            recovered = 0
            for meta in state.citizens_meta.values():
                if meta.get("sick"):
                    meta["sick"] = False
                    recovered += 1
            ev["recovered"] = recovered
        state.applied.append(ev)
        events.append(ev)
    return events
