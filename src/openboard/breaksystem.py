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
# Audit C5: uncapped flags x100 made "trigger a flag burst" the optimal
# strategy. Flag damage is capped; real harm (unmet DELTA over the round
# baseline, C4) is what scales — you must actually hurt citizens.
FLAG_DAMAGE_CAP = 20


def round_verdict(state: WorldState, playbook: str, start_tick: int,
                  baseline_streak: int = 0,
                  baseline_money: int | None = None) -> dict[str, Any]:
    """Final/interim verdict for a timed round: damage you caused and how
    the round ends. Damage = capped flags*100 + unmet-streak DELTA*10.
    C4: background bot starvation before you arrived is the baseline —
    only the streak you personally worsened counts against you."""
    score = attack_score(state, attacker_citizen(state), baseline=baseline_money)
    ticks_played = score["tick"] - start_tick
    flags_caused = score["flags"]
    streak_total = score["worst_unmet_streak"]
    streak_caused = max(0, streak_total - int(baseline_streak or 0))
    stopped = flags_caused >= STOP_FLAGS or streak_caused >= STOP_UNMET
    survived = ticks_played >= ROUND_TICKS and not stopped
    damage = min(flags_caused, FLAG_DAMAGE_CAP) * 100 + streak_caused * 10
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
        "worst_unmet_streak": streak_total,
        "streak_caused": streak_caused,
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
    # Audit 2026-09-20 B9: the foreign bucket is part of the fixed supply
    # (its negative IS our trade surplus). Zero in non-trade worlds = exact.
    # P-DESIGN followup (S1 shipped): the research buckets hold POOLED
    # money (surplus -> innovation_pool -> per-field funding; nothing
    # minted — p4 probe's conservation contract). Uncounted, every tick
    # of funding looks like money vanishing and trips the C6 check.
    return (sum(state.balances.values()) + state.surplus_pool + state.capital_fund
            + state.foreign_balance
            + int(getattr(state, "innovation_pool", 0))
            + sum(int(v) for v in getattr(state, "research_funding", {}).values())
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


def worst_unmet_streak(state: WorldState) -> int:
    """Worst essentials streak across all citizens (audit C4: the harm
    signal, measured at round start so only the ATTACKER'S delta counts)."""
    worst = 0
    for streaks in state.unmet_needs.values():
        for _good, t in streaks.items():
            worst = max(worst, int(t or 0))
    return worst


def attack_score(state: WorldState, attacker: str | None = None,
                 baseline: int | None = None) -> dict[str, Any]:
    """Live scoreboard: attacker damage vs system response. With `attacker`
    given, only flags targeting the attacker count as YOUR damage — background
    bots' flags (e.g. baseline FREE_RIDER drift) never count against you.
    Audit C6: pass `baseline` (captured at round start) so the advertised
    money-invariant check is REAL, not the always-self-consistent fallback."""
    from .metrics import gini

    worst_unmet = worst_unmet_streak(state)
    violation = invariants_ok(state, baseline=baseline)
    flags = state.flags
    if attacker is not None:
        flags = [f for f in flags if f.get("target") == attacker]
    return {
        "tick": state.tick,
        "flags": len(flags),
        "flag_kinds": sorted({f.get("kind", "") for f in flags}),
        "all_flags": len(state.flags),
        "gini_bp": gini(list(state.balances.values())),  # int, Gini x 10,000
        "worst_unmet_streak": worst_unmet,
        "invariant_ok": violation is None,
        "invariant_violation": violation,
        "money_total": money_total(state),
    }


from .ledger import Transaction  # noqa: E402  (type name used above)
