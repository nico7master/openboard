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

from .crisis import crisis_active, crisis_field_override
from .state import WorldState

FIELDS = ("food", "health", "energy", "infrastructure", "computing")
UNLOCK_PCT_CAP = 20  # max input reduction per unlock tier (spec)

# The PUBLISHED mapping: which goods belong to which research field
# (collect_signals and recipe_field both read this - one source of truth).
FIELD_GOODS = {
    "food": ("bread", "meat", "milk", "eggs", "cheese", "meals", "vegetables", "grain"),
    "health": ("medicine", "bandages"),
    "energy": ("electricity", "heating_fuel", "coal"),
    "infrastructure": ("water", "housing", "maintenance", "clothing"),
    "computing": ("electronics", "books"),
}


def recipe_field(recipe: dict[str, Any]) -> str | None:
    """Field a recipe draws its productivity from: the field of its FIRST
    catalog output (deterministic dict order = authoring order)."""
    outs = recipe.get("outputs") or {}
    for g in outs:
        for f in FIELDS:
            if g in FIELD_GOODS[f]:
                return f
    return None


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
    field_goods = FIELD_GOODS
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


def allocate_fields_phase(
    state: WorldState, tick: int, params: dict[str, Any]
) -> list[dict[str, Any]]:
    """Convert the innovation pool into CUMULATIVE per-field funding, then
    unlock improved recipe variants as fields cross thresholds.

    Allocation = effective split of the two-layer design with every
    citizen's weight at the abstain default: the published algorithm's
    proposal (engine bots do not cast research votes; citizens may via
    the dashboard layer). Crisis override redirects the whole budget to
    the crisis field (spec section 4).

    Funding is CUMULATIVE KNOW-HOW, not a money balance: credits here are
    the accounting unit of accumulated research (money conservation is
    preserved bucket-to-bucket: surplus_pool -> innovation_pool ->
    research_funding; nothing minted or retired).

    Productivity effect (realism contract L3): recipes draw output bonus
    from their field's funding via research_effect_bp; crossing each
    unlock_threshold in a field unlocks the next variant tier of its
    first recipe in that field (deterministic pick).
    """
    cfg = params.get("research") or {}
    if not cfg.get("enabled"):
        return []
    pool = int(getattr(state, "innovation_pool", 0))
    if pool <= 0:
        return []
    base = propose_allocation(state, params)
    if crisis_active(state):
        base = crisis_field_override(state, params, base)
    funding = state.research_funding
    total_taken = 0
    for f in sorted(FIELDS):
        take = pool * int(base.get(f, 0)) // 10_000
        if take > 0:
            funding[f] = funding.get(f, 0) + take
            total_taken += take
    # Money conservation (bug found by Lever Atlas 2026-09-11): floor
    # division per field leaves a remainder; zeroing the pool destroyed
    # it every tick (measured -1..-17 credits/tick at research=500bp).
    # Unallocated dust STAYS in the pool for the next allocation.
    state.innovation_pool = pool - total_taken
    events: list[dict[str, Any]] = [{
        "tick": tick,
        "action": "RESEARCH_ALLOCATE",
        "split": dict(sorted(base.items())),
        "funding": dict(sorted(funding.items())),
    }]

    # Variant unlocks: each unlock_threshold reached in a field unlocks the
    # next tier of that field's first (alphabetical) recipe not yet at tier.
    threshold = int(cfg.get("unlock_threshold", 50_000))
    if threshold <= 0:
        return events
    unlocks = state.research_unlocked
    for f in sorted(FIELDS):
        tier = funding.get(f, 0) // threshold
        if tier <= 0:
            continue
        for rid in sorted(state.recipes.keys()):
            if recipe_field(state.recipes[rid]) != f:
                continue
            cur = unlocks.get(rid, 0)
            if cur >= min(tier, UNLOCK_PCT_CAP // 5):
                continue  # already unlocked through this tier
            new_tier = cur + 1
            unlocks[rid] = new_tier
            vid = f"{rid}_v{new_tier}"
            state.recipes[vid] = unlock_variant(state.recipes[rid], new_tier)
            events.append({
                "tick": tick,
                "action": "RESEARCH_UNLOCK",
                "field": f,
                "from_recipe": rid,
                "recipe_id": vid,
                "tier": new_tier,
            })
            break  # one unlock per field per tick
    return events


def research_effect_bp(state: WorldState, recipe: dict[str, Any], params: dict[str, Any]) -> int:
    """L3 productivity: output bonus (bp) a recipe earns from its field's
    cumulative funding. Default scale: +250bp per 10,000cr of know-how in
    the field, capped at +2500bp (+25% = the spec's realism magnitude).
    Integer only; 0 when research disabled or field unfunded."""
    cfg = params.get("research") or {}
    if not cfg.get("enabled"):
        return 0
    f = recipe_field(recipe)
    if f is None:
        return 0
    fnd = int(state.research_funding.get(f, 0))
    if fnd <= 0:
        return 0
    per = int(cfg.get("output_bonus_bp_per_10k", 250))
    cap = int(cfg.get("max_output_bonus_bp", 2_500))
    return min(cap, fnd * per // 10_000)


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
