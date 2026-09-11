"""Stage 5 - Research system tests (spec section 3, plan lines 26-32).

Signal tracking, the published allocation algorithm, delegative
aggregation with cycles, abstain-default to the algorithm, funding
invariance, and unlock bounds (<=20% per tier).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from openboard.engine import apply_tick  # noqa: E402
from openboard.ledger import Ledger  # noqa: E402
from openboard.research import (  # noqa: E402
    FIELDS,
    UNLOCK_PCT_CAP,
    collect_signals,
    effective_allocation,
    fund_pool_phase,
    propose_allocation,
    resolve_delegations,
    unlock_variant,
)
from openboard.state import genesis_state  # noqa: E402


def _world(n: int = 5) -> object:
    s = genesis_state({f"c{i}": 500 for i in range(n)}, ruleset_params={})
    return s


# ---------------------------------------------------------------- signals


def test_signals_track_unmet_and_disease() -> None:
    """Signals read the world transparently: unmet needs per field,
    disease prevalence, population. Pure integers, deterministic."""
    s = _world(4)
    s.unmet_needs = {
        "a": {"bread": True, "water": False},
        "b": {"electricity": True},
        "c": {"bread": True},
    }
    s.citizens_meta["d"] = {"sick": True}
    sig = collect_signals(s)
    assert sig["unmet_food"] == 2  # a and c need bread
    assert sig["unmet_energy"] == 1
    assert sig["disease_prevalence"] == 1
    assert sig["population"] == 4


def test_algorithm_pushes_health_in_pandemic() -> None:
    """The published algorithm shifts weight to health when disease rises
    and to food when food is unmet - from transparent signals only."""
    s = _world(6)
    for c in s.balances:
        s.citizens_meta.setdefault(c, {})
    base = propose_allocation(s, s.active_ruleset_params())
    assert sum(base.values()) == 10_000
    # no pressure: near-even split
    for f in FIELDS:
        assert 0 < base[f] < 10_000

    # pandemic: everyone sick, nothing unmet
    for m in s.citizens_meta.values():
        m["sick"] = True
    pan = propose_allocation(s, s.active_ruleset_params())
    assert pan["health"] > base["health"], "pandemic must raise health share"

    # famine: food unmet for many
    for m in s.citizens_meta.values():
        m["sick"] = False
    s.unmet_needs = {c: {"bread": True} for c in s.balances}
    famine = propose_allocation(s, s.active_ruleset_params())
    assert famine["food"] > pan["food"], "food unmet must raise food share"
    assert sum(famine.values()) == 10_000


# ------------------------------------------------------------- delegation


def test_delegation_chain_and_revocation() -> None:
    """Votes flow through delegation chains; removing the link (revocation)
    returns the weight to the delegator's own vote."""
    votes = {
        "expert": {"health": 100},
        "alice": {"food": 100},
    }
    delegations = {"alice": "expert"}
    totals = resolve_delegations(votes, delegations)
    # delegative semantics: alice's weight follows the expert's split,
    # so health = expert's own 100 + alice's delegated 100
    assert totals["health"] == 200
    assert totals["food"] == 0  # alice's own split superseded

    # revocation: delete the link, alice's own vote counts again
    totals2 = resolve_delegations(votes, {})
    assert totals2["food"] == 100
    assert totals2["health"] == 100


def test_delegation_cycle_resolves_to_abstain() -> None:
    """a->b->a cycles must not double-count or crash: the cycled voter's
    weight abstains (follows the algorithm in effective_allocation)."""
    votes = {
        "a": {"food": 100},
        "b": {"health": 100},
        "c": {"energy": 100},
    }
    delegations = {"a": "b", "b": "a"}  # cycle between a and b
    totals = resolve_delegations(votes, delegations)
    # c votes normally; a and b are in a cycle -> neither counted
    assert totals["health"] == 0 and totals["food"] == 0

    algo = {f: 10_000 // len(FIELDS) for f in FIELDS}
    eff = effective_allocation(votes, delegations, algo, ["a", "b", "c"])
    assert sum(eff.values()) == 10_000
    # c alone (100 pts of 300 total weight) pulls food/health a little;
    # the algorithm dominates the abstainers' 200 pts
    assert eff["computing"] > 0


def test_abstain_default_follows_algorithm() -> None:
    """Citizens who neither vote nor delegate adopt the algorithm's
    proposal - the informed default (spec section 3)."""
    algo = {f: 10_000 // len(FIELDS) for f in FIELDS}
    voters = {"a": {"food": 100}}
    citizens = ["a", "b", "c", "d"]  # 3 abstainers
    eff = effective_allocation(voters, {}, algo, citizens)
    # total weight 400 pts: a's 100 all-food + 300 abstain spread evenly
    assert eff["food"] > 10_000 // len(FIELDS)  # food above even share
    assert sum(eff.values()) == 10_000


# ---------------------------------------------------------------- funding


def test_funding_phase_invariant_neutral_and_gated() -> None:
    """The pool transfer is internal (surplus -> innovation): the money
    total is unchanged; without research params the phase is inert."""
    s = _world(3)
    s.surplus_pool = 10_000
    before = s.surplus_pool + s.innovation_pool

    # inert without config
    events = fund_pool_phase(s, 1, {})
    assert events == []
    assert s.surplus_pool == 10_000 and s.innovation_pool == 0

    # funded at 500bp = 5%
    params = {"research": {"enabled": True, "research_share_bp": 500}}
    events = fund_pool_phase(s, 1, params)
    assert len(events) == 1 and events[0]["amount"] == 500
    assert s.surplus_pool == 9_500 and s.innovation_pool == 500
    assert s.surplus_pool + s.innovation_pool == before  # invariant-neutral

    # engine wiring: a full tick with research enabled books RESEARCH_FUND
    s2 = _world(3)
    s2.rulesets[-1]["params"]["research"] = {"enabled": True, "research_share_bp": 100}
    s2.surplus_pool = 1_000
    apply_tick(s2, Ledger(), [], current_tick=1)
    assert any(e.get("action") == "RESEARCH_FUND" for e in s2.applied)
    # L3 (2026-09-11): the allocation phase now converts the pool into
    # per-field know-how buckets same-tick - same conservation law,
    # finer buckets.
    assert s2.surplus_pool + s2.innovation_pool \
        + sum(s2.research_funding.values()) == 1_000


# ---------------------------------------------------------------- unlocks


def test_unlock_variant_bounds() -> None:
    """Improved variants reduce inputs monotonically, capped at 20%."""
    recipe = {"inputs": {"labor": 100, "steel": 4}, "outputs": {"machines": 1}}
    t1 = unlock_variant(recipe, 1)
    assert t1["inputs"]["labor"] == 95  # 5% tier 1
    t4 = unlock_variant(recipe, 4)
    assert t4["inputs"]["labor"] == 80  # 20%
    t9 = unlock_variant(recipe, 9)  # far beyond cap
    assert t9["inputs"]["labor"] == 80  # still capped at 20%
    assert t9["inputs"]["steel"] == 3  # max(1, floor) respected
    assert t9["outputs"] == recipe["outputs"]  # outputs unchanged


def test_unlock_monotonic_never_below_one() -> None:
    """Higher tiers never increase inputs; min 1 unit stays producible."""
    recipe = {"inputs": {"labor": 3}, "outputs": {"x": 1}}
    prev = 3
    for tier in range(1, 10):
        v = unlock_variant(recipe, tier)
        q = v["inputs"]["labor"]
        assert 1 <= q <= prev
        prev = q
