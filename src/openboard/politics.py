"""Political bots — democracy in the loop (Stage 1 of the world-takeover
roadmap).

A politician is an ordinary economic bot (it works, eats, produces) plus a
political brain that PERCEIVES outcomes, PROPOSES rule changes, and VOTES
self-interestedly. No engine changes: politics rides the existing
PROPOSE/VOTE actions and full-param proposal semantics.

Determinism: all decisions are pure functions of public state (same input ->
same output, stable RNG per tick per citizen via sim's seeding).
"""

from __future__ import annotations

import copy
import random
from typing import Any, Callable

from .bots import DecisionFn, _tx
from .engine import apply_tick, _is_constitutional  # noqa: F401  (apply_tick re-export convenience for tests)
from .ledger import Transaction
from .metrics import gini
from .rules import validate_params
from .state import WorldState

# Cadence: one proposal opportunity per citizen every K ticks.
ELECTION_WINDOW = 50

# Perception -----------------------------------------------------------------


def perceive_gini(state: WorldState) -> int:
    """Current Gini x 1000 (integer, exact — mirrors metrics)."""
    return gini(list(state.balances.values()))


def perceive_deficits(who: str, state: WorldState, params: dict[str, Any]) -> list[str]:
    """Essential goods this citizen holds below half quota (consumption stress)."""
    quota = params.get("essential_need_quota", {})
    inv = state.citizen_inventory.get(who, {})
    return [
        good
        for good, q in quota.items()
        if inv.get(good, 0) * 2 < q
    ]


def perceive_balance(who: str, state: WorldState) -> int:
    return state.balances[who]


def perceive_spread(state: WorldState) -> int:
    """Rich-poor balance ratio x100 (integer). The visible signal of
    inequality — empirically far more discriminating than balance-Gini,
    which peaked at 3,350 (under a 3,500 trigger) while the spread sat
    at 10x for 1,400+ ticks in the untaxed heal run."""
    vals = list(state.balances.values())
    if not vals:
        return 0
    return (max(vals) * 100) // max(min(vals), 1)


# Proposal construction ------------------------------------------------------


def build_proposal(
    who: str,
    tick: int,
    state: WorldState,
    params: dict[str, Any],
    mutate: Callable[[dict[str, Any]], dict[str, Any] | None],
) -> Transaction | None:
    """Build a PROPOSE tx from ACTIVE params + one bounded mutation.

    Proposal params replace the whole set when passed, so we copy the
    active set, apply the mutation, and locally validate before emitting.
    Returns None when the mutation is a no-op or fails validation.
    """
    base = copy.deepcopy(state.active_ruleset_params())
    original = copy.deepcopy(base)
    next_params = mutate(base)
    if next_params is None or next_params == original:
        return None
    if validate_params(next_params, known_goods=set(state.goods.keys())) is not None:
        return None
    window = params.get("governance", {}).get("vote_window_ticks", 3)
    activation = tick + window + 2  # strictly after the window closes
    return _tx(tick, who, "PROPOSE", {"params": next_params, "activation_tick": activation}, state.ruleset_version)


def _has_open_proposal(who: str, state: WorldState) -> bool:
    return any(
        p["status"] == "open" and p["proposer"] == who
        for p in state.proposals.values()
    )


def _open_proposals(state: WorldState, tick: int) -> list[tuple[str, dict[str, Any]]]:
    return [
        (pid, p)
        for pid, p in sorted(state.proposals.items())
        if p["status"] == "open" and tick <= p["closes_tick"]
    ]


# Archetype stances -----------------------------------------------------------


def _delta(proposal_params: dict[str, Any], active: dict[str, Any]) -> dict[str, tuple[Any, Any]]:
    """Changed top-level keys: key -> (old, new). Nested dicts compared shallowly."""
    out: dict[str, tuple[Any, Any]] = {}
    for key in set(proposal_params) | set(active):
        old, new = active.get(key), proposal_params.get(key)
        if old != new:
            out[key] = (old, new)
    return out


def _tax_burden(delta: dict[str, tuple[Any, Any]]) -> int:
    """Signed view of wealth-tax change: >0 heavier, <0 lighter, 0 none."""
    if "wealth_tax" not in delta:
        return 0
    old, new = delta["wealth_tax"]
    if old is None:
        return 1
    if new is None:
        return -1
    if new.get("rate_bp", 0) != old.get("rate_bp", 0):
        return 1 if new.get("rate_bp", 0) > old.get("rate_bp", 0) else -1
    return 1 if new.get("threshold", 0) < old.get("threshold", 0) else -1


# Political brains ------------------------------------------------------------


def _egalitarian_proposal(who, tick, state, params) -> Transaction | None:
    if perceive_spread(state) <= 500:  # richest <= 5x poorest: acceptable
        return None
    base_rate = state.active_ruleset_params().get("wealth_tax", {}).get("rate_bp", 0)
    new_rate = min(base_rate + 100, 1_000)

    def mutate(base):
        base["wealth_tax"] = {"threshold": 5_000, "rate_bp": new_rate}
        return base

    return build_proposal(who, tick, state, params, mutate)


def _libertarian_proposal(who, tick, state, params) -> Transaction | None:
    wt = state.active_ruleset_params().get("wealth_tax")
    if not wt or wt.get("rate_bp", 0) < 300:
        return None
    if perceive_spread(state) >= 200:  # won't cut taxes into a spread
        return None

    def mutate(base):
        base["wealth_tax"] = {"threshold": 5_000, "rate_bp": max(wt["rate_bp"] - 100, 0)}
        return base

    return build_proposal(who, tick, state, params, mutate)


def _systemic_trim_good(state: WorldState, params: dict[str, Any]) -> str | None:
    """Ordinary-business trigger (post-RC1 pacing fix, 2026-09-22): the good
    with the MOST CITIZENS in unmet-streak among goods whose quota still
    allows a bounded trim (quota >= 2). Reads the engine's own unmet-needs
    book — a SYSTEMIC delivery failure, not one citizen's pantry. None when
    no trimmable good is under-delivered. Deterministic: count desc,
    quota desc, name asc.

    Evidence probe (2026-09-22, seed-42 dashboard world, 700 ticks): the
    previous personal-pantry trigger NEVER filed — buy-ahead keeps citizen
    inventories near 2x quota, and the sorted-first deficit goods (bread,
    eggs, fish, ...) sit at quota 1 where the floor-1 guard blocks every
    trim — so all 224 bot filings were structural (154 surplus_spending,
    70 wealth_tax) and momentum coalescing had nothing ordinary to
    coalesce around. Systemic streaks, by contrast, concentrated exactly
    where slack exists: transport (quota 2, ~119 citizens streaking for
    600+ ticks), household_goods, heating_fuel.
    """
    quota = params.get("essential_need_quota", {})
    counts: dict[str, int] = {}
    for who_key in sorted(state.unmet_needs or {}):
        streaks = state.unmet_needs.get(who_key) or {}
        for good_key in sorted(streaks):
            if int(streaks.get(good_key) or 0) >= 1 and quota.get(good_key, 0) >= 2:
                counts[good_key] = counts.get(good_key, 0) + 1
    if not counts:
        return None
    return sorted(counts, key=lambda g: (-counts[g], -quota.get(g, 0), g))[0]


def _pragmatist_proposal(who, tick, state, params) -> Transaction | None:
    deficits = perceive_deficits(who, state, params)
    if not deficits:
        return None
    # Post-RC1 pacing tune (2026-09-22): also file an ORDINARY proposal so
    # the strict-majority path is reachable at all — every other archetype
    # mutates structural keys only, and the founder-approved 60%-of-all tier
    # correctly keeps those beyond bot reach. Trim the SYSTEMICALLY
    # under-delivered good's quota by one bounded step (floor 1): align the
    # need book with what the economy actually delivers — small, popular,
    # non-structural. Target comes from the engine's unmet-streak book
    # (_systemic_trim_good): the previous personal-pantry read never fired
    # (probe evidence in the helper's docstring).
    if tick % (2 * ELECTION_WINDOW) == ELECTION_WINDOW:  # alternate windows
        good = _systemic_trim_good(state, params)
        if good is not None:

            def mutate_quota(base, _good=good):
                quota = dict(base.get("essential_need_quota", {}))
                cur = quota.get(_good, 0)
                if cur <= 1:
                    return None
                quota[_good] = cur - 1
                base["essential_need_quota"] = quota
                return base

            tx = build_proposal(who, tick, state, params, mutate_quota)
            if tx is not None:
                return tx
    # More purchasing power: raise the dividend share a bounded step.
    ss = state.active_ruleset_params().get("surplus_spending", {})
    cur = ss.get("dividend_share_bp", 0)
    new = min(cur + 500, 10_000)
    if new == cur:
        return None

    def mutate(base):
        base["surplus_spending"] = {
            "dividend_share_bp": new,
            "services_share_bp": ss.get("services_share_bp", 0),
            "min_pool_buffer": ss.get("min_pool_buffer", 1_000),
            "max_dividend_per_tick": ss.get("max_dividend_per_tick", 50),
        }
        return base

    return build_proposal(who, tick, state, params, mutate)


_PROPOSERS = {
    "egalitarian": _egalitarian_proposal,
    "libertarian": _libertarian_proposal,
    "pragmatist": _pragmatist_proposal,
}


def _stance(archetype: str, who: str, delta: dict[str, tuple[Any, Any]], state: WorldState) -> str | None:
    """'for' | 'against' | None (abstain) for a proposal delta."""
    # Ordinary business (post-RC1 pacing tune): trimming an undeliverable
    # need-quota aligns the need book with what the economy actually
    # delivers — small, popular, non-structural. Every platform supports it
    # (libertarians: a smaller mandated book; egalitarians: honest needs;
    # pragmatists: their own filing).
    if "essential_need_quota" in delta:
        old_q, new_q = delta["essential_need_quota"]
        old_q = old_q or {}
        new_q = new_q or {}
        if any(new_q.get(k, 0) < v for k, v in old_q.items()):
            return "for"
    tax = _tax_burden(delta)
    if archetype == "egalitarian":
        if tax > 0:
            return "for"
        if tax < 0:
            return "against"
        if "surplus_spending" in delta:
            return "for"
        return None
    if archetype == "libertarian":
        if tax > 0:
            return "against"
        if tax < 0:
            return "for"
        return None
    if archetype == "pragmatist":
        if "surplus_spending" in delta:
            old, new = delta["surplus_spending"]
            if new and new.get("dividend_share_bp", 0) > (old or {}).get("dividend_share_bp", 0):
                return "for"
        if tax > 0:
            return None  # mild: tolerate taxes, don't champion them
        return None
    return None


def _seed_proposal(open_props: list[tuple[str, dict[str, Any]]], state: WorldState, who: str) -> str | None:
    """Cold-start: the lowest-pid ORDINARY proposal (None when there is no
    ordinary business — structural/constitutional fields stay unvoted)."""
    ord_props = _ordinary_open(state, open_props)
    return ord_props[0][0] if ord_props else None


def _ordinary_open(state: WorldState, open_props: list[tuple[str, dict[str, Any]]]) -> list[tuple[str, dict[str, Any]]]:
    """Open proposals OUTSIDE the structural and constitutional tiers — the
    only business bot electorates may legislate (founder-approved A2 tier:
    structural changes stay beyond bot reach; those fail on quorum)."""
    from .engine import _is_constitutional, _is_structural
    active = state.active_ruleset_params()
    return [(pid, p) for pid, p in open_props
            if p.get("intervention") is None
            and not _is_structural(p.get("params") or {}, active)
            and not _is_constitutional(p.get("params") or {}, active)]


def _momentum_leader(open_props: list[tuple[str, dict[str, Any]]], state: WorldState) -> tuple[str, int] | None:
    """The ordinary proposal with the most for-weight committed so far.
    Deterministic: max weight, then lowest proposal id. None when no
    ordinary proposal has traction yet (the caller seeds)."""
    best: tuple[str, int] | None = None
    for pid, proposal in _ordinary_open(state, open_props):
        w = 0
        for ballot in proposal.get("ballots", {}).values():
            if isinstance(ballot, dict):
                if ballot.get("choice") == "for":
                    w += int(ballot.get("bp", 0))
            elif ballot == "for":
                w += 1
        if w > 0 and (best is None or w > best[1] or (w == best[1] and pid < best[0])):
            best = (pid, w)
    return best

def make_politician(inner: DecisionFn, archetype: str, window: int = ELECTION_WINDOW) -> DecisionFn:
    """Economic bot + political brain. Proposes on election ticks, votes
    on every open proposal per archetype stance."""
    assert archetype in _PROPOSERS

    def bot(who: str, state: WorldState, params: dict[str, Any], tick: int, rng: random.Random) -> list[Transaction]:
        out = inner(who, state, params, tick, rng)
        if not params.get("governance", {}).get("enabled"):
            return out
        v = state.ruleset_version
        # propose (once per election window)
        if tick % window == 0 and not _has_open_proposal(who, state):
            tx = _PROPOSERS[archetype](who, tick, state, params)
            if tx is not None:
                out.append(tx)
        # vote on open proposals (one person, one vote — engine enforces).
        # Vote token (2026-09-15 spec): spend the whole remaining monthly
        # budget on the FIRST proposal with a stance, then stop — attention
        # is scarce by design. Legacy mode: one binary vote per proposal.
        active = state.active_ruleset_params()
        token_bp = 0
        gov = active.get("governance", {})
        if gov.get("enabled") and gov.get("vote_token_bp", 0) > 0:
            budget = state.vote_budget.get(who) or {}
            token_bp = budget.get("bp", 0) if budget.get("cycle") == tick // gov.get("vote_cycle_ticks", 30) else 0
        _open_props = list(_open_proposals(state, tick))
        for _idx, (pid, proposal) in enumerate(_open_props):
            if who in proposal["ballots"]:
                continue
            choice = _stance(archetype, who, _delta(proposal["params"], active), state)
            if choice is None:
                # Founder directive 2026-09-16: bots are not smart voters and
                # have no skin in the game — the SYSTEM proposes (bounded
                # archetype mutations only), and politicians approve by
                # default so non-crisis rebalancing never stalls on an
                # indifferent electorate.
                # CAPTURE GUARD (engine._is_constitutional contract): default
                # approval NEVER applies to constitutional matters (voting
                # rules, council, phase). Those need explicit consent — the
                # 2/3-of-all gate counts FOR votes, so rubber stamps would
                # let one faction proposal reach a constitutional majority
                # (defense proven necessary by the faction-capture test).
                from .engine import _is_constitutional
                if _is_constitutional(proposal["params"], active):
                    continue
                # P2 loaded persuasion dice (spec 2026-09-18), opt-in via
                # governance.persuasion: undecided voters roll a SEEDED die —
                # p(yes) rises with the proposer's trust. Hash of
                # (tick, pid, who) => byte-identical replay. Flag off
                # (default) => legacy default-for, byte-identical.
                if gov.get("persuasion"):
                    import hashlib
                    # Audit 2026-09-20 A4: die seeded on proposal content —
                    # no reusable cross-proposal roll tables — and unknown
                    # politicians start at trust 50 (entrenchment fix).
                    _seed = f"{pid}:{proposal.get('change_tx_hash', '')}:{who}"
                    _roll = int.from_bytes(hashlib.sha256(
                        _seed.encode()).digest()[:2], "big") % 101
                    _trust = state.politician_trust.get(proposal.get("proposer", ""), 50)
                    choice = "for" if _roll < _trust else "against"
                else:
                    choice = "for"
            if token_bp > 0:
                # Audit 2026-09-20 A8: no dumping everything on the first
                # (possibly decoy) proposal — but even-split dilution had its
                # own failure mode (post-RC1 pacing probe, 2026-09-22): 0 of
                # 840 proposals passed in 3x2000-tick soak seeds because 29
                # politicians x tiny even slices could not out-weigh the
                # strict-majority abstainers. Founder-approved tune: momentum
                # coalescing — commit the FULL remaining token to the single
                # stance-positive proposal with the most for-weight so far
                # (deterministic tiebreak: lowest proposal id). Zero-traction
                # decoys still get nothing, so the A8 rationale holds.
                _momentum = _momentum_leader(_open_props, state)
                if _momentum is not None:
                    # SYMMETRIC concentration: for- AND against-voters commit
                    # the full remaining token to the traction leader. An
                    # against-dropping electorate would be all-for — the
                    # majority-capture regression the tiers exist to prevent.
                    _pid, _ = _momentum
                    if pid == _pid:
                        out.append(_tx(tick, who, "VOTE",
                                       {"proposal_id": pid, "choice": choice, "bp": token_bp}, v))
                        token_bp = 0
                elif choice == "for" and pid == _seed_proposal(_open_props, state, who):
                    # COLD-START SEED: no traction exists yet — the lowest-pid
                    # ordinary proposal each voter supports gets the first
                    # full-token commitment, so momentum can form at all.
                    out.append(_tx(tick, who, "VOTE",
                                   {"proposal_id": pid, "choice": choice, "bp": token_bp}, v))
                    token_bp = 0
            elif gov.get("vote_token_bp", 0) == 0:
                # Legacy binary mode (pre-token worlds): one vote per open
                # proposal — unchanged by the momentum tune. RESTORED
                # 2026-09-22: the momentum patch nested this branch under
                # `if token_bp > 0`, making it unreachable and silencing
                # every legacy-world vote (caught by
                # test_election_self_correction + test_founder_directives).
                out.append(_tx(tick, who, "VOTE", {"proposal_id": pid, "choice": choice}, v))
        return out

    return bot


def make_faction(inner: DecisionFn, members: frozenset[str], window: int = ELECTION_WINDOW) -> DecisionFn:
    """Capture attacker: coordinated bloc. Agenda —
    step 1: 'innocent' quorum reduction (quorum_bp -> 0);
    step 2: once quorum is 0, repeal the wealth tax (rich bloc shields wealth).
    Members vote FOR their own agenda, AGAINST everything else."""

    def bot(who: str, state: WorldState, params: dict[str, Any], tick: int, rng: random.Random) -> list[Transaction]:
        out = inner(who, state, params, tick, rng)
        if not params.get("governance", {}).get("enabled"):
            return out
        v = state.ruleset_version
        active = state.active_ruleset_params()

        def wants_repeal() -> bool:
            gov = active.get("governance", {})
            return gov.get("quorum_bp", 5_000) == 0

        if tick % window == 0 and not _has_open_proposal(who, state):
            def mutate_quorum(base):
                g = dict(base.get("governance", {}))
                g["quorum_bp"] = 0
                base["governance"] = g
                return base

            def mutate_repeal(base):
                base.pop("wealth_tax", None)
                return base

            if wants_repeal():
                tx = build_proposal(who, tick, state, params, mutate_repeal)
            else:
                tx = build_proposal(who, tick, state, params, mutate_quorum)
            if tx is not None:
                out.append(tx)

        # Vote token (2026-09-15 spec): full remaining budget on the first
        # proposal, then stop. Legacy: binary vote per proposal.
        gov = active.get("governance", {})
        token_bp = 0
        if gov.get("enabled") and gov.get("vote_token_bp", 0) > 0:
            budget = state.vote_budget.get(who) or {}
            token_bp = budget.get("bp", 0) if budget.get("cycle") == tick // gov.get("vote_cycle_ticks", 30) else 0
        _open_props = list(_open_proposals(state, tick))
        for _idx, (pid, proposal) in enumerate(_open_props):
            if who in proposal["ballots"]:
                continue
            proposer_is_faction = proposal["proposer"] in members
            choice = "for" if proposer_is_faction else "against"
            if token_bp > 0:
                out.append(_tx(tick, who, "VOTE",
                               {"proposal_id": pid, "choice": choice, "bp": token_bp}, v))
                token_bp = 0
            elif gov.get("vote_token_bp", 0) == 0:
                out.append(_tx(tick, who, "VOTE",
                               {"proposal_id": pid, "choice": choice}, v))
        return out

    return bot
