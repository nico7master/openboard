"""Stage 5 - Research system: algorithmic proposal, delegative vote, funding.

Spec section 3 (2026-08-26): society steers research direction through a
two-layer loop - the PUBLISHED ALGORITHM proposes field splits from
transparent signals; citizens vote directly, delegate, or abstain (their
weight then follows the algorithm's proposal). The algorithm itself is an
ordinary votable item; temporary overrides auto-expire. Funding flows from
the innovation pool (research_share_bp of surplus) to fields, then within
each field to centers/proposals. Completed research unlocks improved
recipe variants, capped at <=20% input reduction per tier.

Rule-gated via params['research']: absent => inert, old worlds replay
byte-identically. Determinism: pure functions over state + params, no rng.
"""
from __future__ import annotations

from typing import Any

from .state import WorldState

FIELDS = ("food", "health", "energy", "infrastructure", "computing")
UNLOCK_PCT_CAP = 20  # max input reduction per unlock tier (spec)


def _cfg(params: dict[str, Any]) -> dict[str, Any] | None:
    cfg = params.get("research") or {}
    return cfg if cfg.get("enabled") else None


# ------------------------------------------------------------------ signals


def collect_signals(state: WorldState) -> dict[str, int]:
    """Transparent, integer-only signals the algorithm (and any citizen)
    can read. Published each cycle so the proposal is auditable.

    - unmet_<field>: total citizens with unmet needs mapping to the field
    - disease_prevalence: currently sick citizens (pandemic pressure)
    - population: living citizens
    """
    field_goods = {
        "food": ("bread", "meat", "milk", "eggs", "cheese", "meals", "vegetables", "grain"),
        "health": ("medicine", "bandages"),
        "energy": ("electricity", "heating_fuel", "coal"),
        "infrastructure": ("water", "housing", "maintenance", "clothing"),
        "computing": ("electronics", "books"),
    }
    signals: dict[str, int] = {"population": len(state.balances)}
    for f in FIELDS:
        signals[f"unmet_{f}"] = 0
    for cid, unmet in sorted(state.unmet_needs.items()):
        if not unmet:
            continue
        for g in sorted(unmet.keys()):
            if not unmet.get(g):
                continue
            for f in FIELDS:
                if g in field_goods[f]:
                    signals[f"unmet_{f}"] += 1
                    break
    signals["disease_prevalence"] = sum(
        1 for m in state.citizens_meta.values() if m.get("sick")
    )
    return signals


def propose_allocation(
    state: WorldState, params: dict[str, Any]
) -> dict[str, int]:
    """THE published algorithm: propose a field split (per-mille, sums to
    1000) from transparent signals. Pure function - same state, same
    proposal. Health pressure and unmet needs raise a field's share;
    the reasoning is embedded in the signals themselves (public)."""
    signals = collect_signals(state)
    # demand weights: base even split, then add pressure per unit signal
    pressure = {
        f: signals.get(f"unmet_{f}", 0) * 10 + (
            signals["disease_prevalence"] * 20 if f == "health" else 0
        )
        for f in FIELDS
    }
    total = sum(pressure.values())
    if total == 0:
        # no pressure: even split
        return {f: 10_000 // len(FIELDS) for f in FIELDS}
    # integer per-mille: floor share, distribute remainder deterministically
    out: dict[str, int] = {}
    allocated = 0
    for f in FIELDS:
        share = pressure[f] * 10_000 // total
        out[f] = share
        allocated += share
    # remainder to the largest-pressure field (deterministic tie-break: name)
    rest = 10_000 - allocated
    if rest > 0:
        top = max(sorted(FIELDS), key=lambda f: pressure[f])
        out[top] += rest
    return out


# --------------------------------------------------------------- delegation


def resolve_delegations(
    votes: dict[str, dict[str, int]],
    delegations: dict[str, str],
    citizens: list[str] | None = None,
) -> dict[str, int]:
    """Aggregate 100-point splits with delegative democracy.

    Each citizen carries 100 points of weight. A citizen who delegates
    (delegations[who] = delegate) contributes their weight via the
    DELEGATE's split - chains are followed (expert voting health casts
    for every follower too). Revocation = removing the link: the weight
    returns to the citizen's own vote. A delegation CYCLE (a->b->a)
    resolves every cycled member's weight to ABSTAIN (handled by the
    caller via effective_allocation). Non-voters abstain by default.
    """
    if citizens is None:
        citizens = sorted(set(votes) | set(delegations))
    totals: dict[str, int] = {f: 0 for f in FIELDS}
    for who in sorted(citizens):
        # follow the delegation chain (bounded by the citizen set size)
        seen: set[str] = set()
        cur = who
        while cur in delegations and delegations[cur] != cur and cur not in seen:
            seen.add(cur)
            cur = delegations[cur]
        if cur in seen:
            continue  # cycle: this citizen's weight abstains
        split = votes.get(cur)
        if split is None:
            continue  # abstain (counted via the algorithm in effective_allocation)
        for f, pts in split.items():
            if f in totals:
                totals[f] += max(0, int(pts))
    return totals


def effective_allocation(
    votes: dict[str, dict[str, int]],
    delegations: dict[str, str],
    algorithm: dict[str, int],
    citizens: list[str],
) -> dict[str, int]:
    """Final field split: expressed votes + abstainers' weight following
    the algorithm's proposal (integer per-mille, sums to 10_000).

    Abstain = the citizen's weight does NOT land on a real split: they
    do not vote, do not delegate, or sit in a delegation cycle. All
    such weight follows the published algorithm (the informed default)."""
    totals = resolve_delegations(votes, delegations, citizens)
    n_abstain = 0
    for who in citizens:
        seen: set[str] = set()
        cur = who
        while cur in delegations and delegations[cur] != cur and cur not in seen:
            seen.add(cur)
            cur = delegations[cur]
        if cur in seen or cur not in votes:
            n_abstain += 1
    algo_total = sum(algorithm.values()) or 1
    out = dict(totals)
    if n_abstain > 0:
        abstain_pts = n_abstain * 100
        for f in FIELDS:
            out[f] = out.get(f, 0) + abstain_pts * algorithm.get(f, 0) // algo_total
    total = sum(out.values())
    if total == 0:
        return {f: 10_000 // len(FIELDS) for f in FIELDS}
    norm: dict[str, int] = {}
    alloc = 0
    for f in sorted(FIELDS):
        norm[f] = out.get(f, 0) * 10_000 // total
        alloc += norm[f]
    rest = 10_000 - alloc
    if rest > 0:
        norm[max(sorted(FIELDS), key=lambda f: out.get(f, 0))] += rest
    return norm


# ----------------------------------------------------------------- funding


def fund_pool_phase(
    state: WorldState, tick: int, params: dict[str, Any]
) -> list[dict[str, Any]]:
    """Move research_share_bp of the surplus pool into the innovation pool
    each tick (deterministic, integer floor). Emits RESEARCH_FUND."""
    cfg = params.get("research") or {}
    if not cfg.get("enabled"):
        return []
    bp = max(0, min(10_000, int(cfg.get("research_share_bp", 500))))
    take = state.surplus_pool * bp // 10_000
    if take <= 0:
        return []
    state.surplus_pool -= take
    state.innovation_pool = getattr(state, "innovation_pool", 0) + take
    return [{
        "tick": tick,
        "action": "RESEARCH_FUND",
        "amount": take,
        "pool": state.innovation_pool,
    }]


def unlock_variant(recipe: dict[str, Any], tier: int) -> dict[str, Any]:
    """Improved recipe variant: inputs scaled down by the unlock pct,
    CAPPED at 20% per tier (spec). Deterministic integer floor, min 1."""
    pct = min(UNLOCK_PCT_CAP, max(1, int(tier * 5)))  # 5%/tier, cap 20%
    variant = {
        "inputs": {
            g: max(1, q * (10_000 - pct * 100) // 10_000)
            for g, q in recipe.get("inputs", {}).items()
        },
        "outputs": dict(recipe.get("outputs", {})),
    }
    return variant
