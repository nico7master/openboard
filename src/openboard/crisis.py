"""Stage 5 - Crisis override: need-first distribution under emergency.

Spec section 4 (2026-08-26): a crisis (pandemic, famine, blackout) is
declared by citizen vote; a SEVERE shock auto-declares one subject to
citizen RATIFICATION within 100 ticks (the democracy can reject it).
During an active crisis:
  - all advantages/priorities are suspended (no producer-input priority,
    no patronage advantages),
  - fair-clearing rotation is forced ON (need-based distribution),
  - research redirects to the crisis field (emergency redirection).
Crisis ends by citizen vote or when the votable max duration expires.
Everything is rule-gated via params['crisis']: absent => inert, old
worlds replay byte-identically. Deterministic integer logic only.
"""
from __future__ import annotations

from typing import Any

from .state import WorldState

RATIFY_WINDOW_TICKS = 100  # spec: auto-declare needs ratification <= 100 ticks
DEFAULT_MAX_TICKS = 600

# crisis kind -> research field that receives emergency funding
KIND_TO_FIELD = {
    "pandemic": "health",
    "drought": "food",
    "famine": "food",
    "blackout": "energy",
    "outage": "energy",
}


def _cfg(params: dict[str, Any]) -> dict[str, Any] | None:
    cfg = params.get("crisis") or {}
    return cfg if cfg.get("enabled") else None


def crisis_active(state: WorldState) -> bool:
    """True while a ratified crisis is active (engine suspension hook)."""
    c = getattr(state, "crisis", None)
    return bool(c and c.get("active"))


def crisis_field(state: WorldState) -> str | None:
    """The research field the crisis redirects to, if any."""
    c = getattr(state, "crisis", None)
    if not c or not c.get("active"):
        return None
    return KIND_TO_FIELD.get(str(c.get("kind", "")))


def _emit(state: WorldState, tick: int, action: str, **kw: object) -> dict[str, Any]:
    e = {"tick": tick, "action": action}
    e.update(kw)
    state.applied.append(e)
    return e


def declare_crisis(
    state: WorldState, tick: int, kind: str, source: str
) -> dict[str, Any]:
    """Enter crisis state. source: 'auto' (severe shock, needs ratification)
    or 'vote' (directly ratified by citizens). Emits CRISIS_AUTO/START."""
    if crisis_active(state):
        return state.applied[-1]
    state.crisis = {
        "active": True,
        "kind": kind,
        "source": source,
        "declared_tick": tick,
        "ratify_by": tick + RATIFY_WINDOW_TICKS if source == "auto" else None,
        "ratified": source == "vote",
        "votes_for": 0,
        "votes_against": 0,
    }
    e = {
        "tick": tick,
        "action": "CRISIS_START" if source == "vote" else "CRISIS_AUTO",
        "kind": kind,
        "ratify_by": tick + RATIFY_WINDOW_TICKS if source == "auto" else None,
    }
    state.applied.append(e)
    return e


def end_crisis(state: WorldState, tick: int, reason: str) -> dict[str, Any]:
    """End the active crisis (vote or expiry). Emits CRISIS_END."""
    c = getattr(state, "crisis", None)
    if not c or not c.get("active"):
        return state.applied[-1]
    c["active"] = False
    c["ended_tick"] = tick
    e = {"tick": tick, "action": "CRISIS_END", "reason": reason,
         "kind": c.get("kind")}
    state.applied.append(e)
    return e


def crisis_phase(
    state: WorldState, tick: int, params: dict[str, Any]
) -> list[dict[str, Any]]:
    """End-of-tick crisis lifecycle (rule-gated; runs after governance).

    - auto-declare on severe shocks: any citizen death this tick under
      shocks declares a crisis awaiting ratification (spec: subject to
      ratification <=100 ticks - citizens can REJECT it),
    - ratification tally from this tick's CRISIS_VOTE transactions,
    - expiry: unratified autos expire at the deadline; ratified crises
      end at the votable max duration.
    """
    if not _cfg(params):
        return []
    c = getattr(state, "crisis", None)

    # 1) severe-shock auto-declare: deaths this tick (scan this tick's tail)
    if not (c and c.get("active")):
        deaths = [
            e for e in state.applied
            if e.get("tick") == tick and e.get("action") == "CITIZEN_DEATH"
        ]
        if deaths:
            declare_crisis(state, tick, "pandemic", "auto")
            c = state.crisis

    if not (c and c.get("active")):
        return []

    # 2) ratification tally (votes collected this tick by _apply_crisis_vote)
    pop = len(state.balances)
    if not c.get("ratified"):
        needed = max(1, pop // 2)
        if c.get("votes_for", 0) > c.get("votes_against", 0) and c["votes_for"] >= needed:
            c["ratified"] = True
            state.applied.append({
                "tick": tick, "action": "CRISIS_START", "kind": c.get("kind"),
                "ratified": True,
            })
        elif c.get("ratify_by") is not None and tick > c["ratify_by"]:
            # democracy refused to ratify in time: crisis dies
            c["active"] = False
            state.applied.append({
                "tick": tick, "action": "CRISIS_END", "reason": "unratified",
                "kind": c.get("kind"),
            })
            return []

    # 3) max duration
    if c.get("ratified"):
        max_ticks = int(_cfg(params).get("max_ticks", DEFAULT_MAX_TICKS))
        if tick - c["declared_tick"] >= max_ticks:
            end_crisis(state, tick, "max_duration")
    return []


def tally_crisis_vote(state: WorldState, who: str, in_favor: bool) -> None:
    """Record one citizen's crisis vote (called by the engine on apply)."""
    c = getattr(state, "crisis", None)
    if not c or not c.get("active"):
        return
    if in_favor:
        c["votes_for"] = c.get("votes_for", 0) + 1
    else:
        c["votes_against"] = c.get("votes_against", 0) + 1


def crisis_field_override(
    state: WorldState, params: dict[str, Any], base: dict[str, int]
) -> dict[str, int]:
    """Emergency research redirection: during a crisis the whole innovation
    budget flows to the field matching the crisis kind (spec section 4)."""
    from .research import FIELDS

    field = crisis_field(state)
    if field is None or field not in FIELDS:
        return base
    out = {f: 0 for f in FIELDS}
    out[field] = 10_000
    return out
