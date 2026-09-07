"""B2: 'Break the System' — playable attack mode.

Hands a human the proven Stage 2 adversary toolkit as game playbooks: act
as the attacker citizen each tick, and the engine's defenses (oversight
flags, wealth tax, constitution, invariant) are the live opponent.
Score = damage you cause before the system stops you. The ledger records
everything — cheating is played, not possible.
"""
from __future__ import annotations

from typing import Any

from .state import WorldState

# playbook name -> bot archetype driving the attacker citizen
PLAYBOOKS: dict[str, str] = {
    "hoarder": "hoarder",               # buy + hold essentials past hoard line
    "wash_trade": "price_manipulator",  # listing/bid abuse, price signals
    "faction": "collusive_faction",     # bloc capture of votes
    "wage_mint": "free_rider",          # idle-labor income pumping
}

# B2 v2: timed rounds — a round ends when the system stops you (8 flags or
# essentials streak 30) OR you survive the full tick budget.
ROUND_TICKS = 200
STOP_FLAGS = 8
STOP_UNMET = 30


def round_verdict(state: WorldState, playbook: str, start_tick: int) -> dict[str, Any]:
    """Final/interim verdict for a timed round: damage you caused and how
    the round ends. Damage = flags_caused*100 + worst_unmet_streak*10
    (flags are the system catching you; unmet is real harm to citizens)."""
    score = attack_score(state)
    ticks_played = score["tick"] - start_tick
    flags_caused = score["flags"]
    stopped = flags_caused >= STOP_FLAGS or score["worst_unmet_streak"] >= STOP_UNMET
    survived = ticks_played >= ROUND_TICKS and not stopped
    damage = flags_caused * 100 + score["worst_unmet_streak"] * 10
    if stopped:
        outcome = "stopped_by_system"
    elif survived:
        outcome = "survived_full_round"
    else:
        outcome = "round_in_progress"
    return {
        "playbook": playbook,
        "ticks_played": ticks_played,
        "round_ticks": ROUND_TICKS,
        "flags_caused": flags_caused,
        "flag_kinds": score["flag_kinds"],
        "worst_unmet_streak": score["worst_unmet_streak"],
        "gini_bp": score["gini_bp"],
        "damage": damage,
        "outcome": outcome,
        "invariant_ok": score["invariant_ok"],
    }


def capture_baseline(state: WorldState) -> int:
    """Total money stock at game start; conservation is measured against
    this (mint/retire events legitimately move it, nothing else may)."""
    return money_total(state) - state.money_minted + state.money_retired


def money_total(state: WorldState) -> int:
    return (sum(state.balances.values()) + state.surplus_pool + state.capital_fund
            + sum(c.get("treasury", 0) for c in state.coops.values()))


def invariants_ok(state: WorldState, baseline: int | None = None) -> str | None:
    """Core integrity checks. Negativity is absolute; the money invariant is
    checked against `baseline` when provided (captured at game start), else
    against the current mint/retire accounting (always self-consistent)."""
    for name, bal in state.balances.items():
        if bal < 0:
            return f"negative balance {name}={bal}"
    for cid, c in state.coops.items():
        if c.get("treasury", 0) < 0:
            return f"negative treasury {cid}"
        for good, qty in c.get("inventory", {}).items():
            if qty < 0:
                return f"negative coop stock {cid}.{good}={qty}"
    if state.surplus_pool < 0:
        return "negative surplus pool"
    total = money_total(state)
    if baseline is not None:
        expected = baseline + state.money_minted - state.money_retired
        if total != expected:
            return f"money invariant broken: {total} != {expected}"
    return None


def attack_tick(state: WorldState, attacker: str, tick: int, playbook: str,
                rng, params: dict[str, Any] | None = None) -> list[Transaction]:
    """The attacker citizen's moves for one tick, per playbook."""
    from .bots import ARCHETYPES
    from .engine import _gov_params

    archetype = PLAYBOOKS.get(playbook)
    if archetype is None:
        return []
    fn = ARCHETYPES[archetype]
    params = params or _gov_params({})
    who = attacker if attacker in state.balances else attacker_citizen(state)
    return fn(who, state, params, tick, rng)


def attacker_citizen(state: WorldState) -> str:
    """The game's attacker seat: first citizen (deterministic)."""
    return sorted(state.balances.keys())[0]


def attack_score(state: WorldState) -> dict[str, Any]:
    """Live scoreboard: attacker damage vs system response."""
    from .metrics import gini

    worst_unmet = 0
    for streaks in state.unmet_needs.values():
        for _good, t in streaks.items():
            worst_unmet = max(worst_unmet, int(t or 0))
    violation = invariants_ok(state, baseline=None)
    return {
        "tick": state.tick,
        "flags": len(state.flags),
        "flag_kinds": sorted({f.get("kind", "") for f in state.flags}),
        "gini_bp": gini(list(state.balances.values())),  # int, Gini x 10,000
        "worst_unmet_streak": worst_unmet,
        "invariant_ok": violation is None,
        "invariant_violation": violation,
        "money_total": money_total(state),
    }


from .ledger import Transaction  # noqa: E402  (type name used above)
