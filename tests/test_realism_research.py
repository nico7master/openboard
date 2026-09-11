"""Realism contract L3 (spec 2026-09-11 Part II, Lever 3): research ->
productivity (endogenous growth).

Real-world effect under contract:
- DIRECTION: R&D spending raises output per hour (TFP); >50% of long-run
  growth in real economies is TFP, not factor accumulation. Unfunded
  fields gain nothing; crisis redirects the whole innovation budget to
  the crisis field (emergency science, like real wartime/mountain-disease
  pushes).
- MECHANISM: surplus -> innovation pool (Stage 5) -> cumulative per-field
  know-how (funding = accumulated research, an accounting bucket - money
  conservation preserved bucket-to-bucket) -> recipes draw an output
  bonus (bp) from their field's funding; crossing thresholds unlocks
  improved recipe VARIANTS (<=20% input reduction per tier, spec).
- MAGNITUDE: +250bp per 10,000cr know-how, capped +2500bp (+25%);
  variants -5% inputs per tier.
- FLIP: crisis override sends 100% of the split to the crisis field;
  research absent/disabled => zero effect, old worlds replay identical.
"""
import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from openboard.crisis import declare_crisis
from openboard.engine import _apply_produce, apply_tick
from openboard.ledger import Ledger, Transaction
from openboard.research import (  # noqa: E402
    allocate_fields_phase,
    recipe_field,
    research_effect_bp,
)
from openboard.rules import DEFAULT_RULESET_PARAMS
from openboard.state import genesis_state


def res_params(**over):
    p = copy.deepcopy(DEFAULT_RULESET_PARAMS)
    p["triage_overrides"] = {}
    p["research"] = {"enabled": True, "research_share_bp": 500,
                     "unlock_threshold": 5_000}
    p.update({k: v for k, v in over.items() if k != "research"})
    return p


def _world(params, n=2):
    return genesis_state({f"c{i}": 5_000 for i in range(n)}, ruleset_params=params)


def _produce_flour_to_bread(s, params, runs=1):
    """Found bakery, stock inputs, produce via the real engine path.
    Returns (produced_bread, base_bread_per_run)."""
    apply_tick(s, Ledger(), [Transaction(
        tick=1, sender="c0", action="FOUND_COOP",
        payload={"coop_id": "bakery", "name": "bakery", "members": ["c0", "c1"]},
        ruleset_version=1)], current_tick=1)
    coop = s.coops["bakery"]
    rec = s.recipes["flour_to_bread"]
    assert recipe_field(rec) == "food"
    for g, q in rec["inputs"].items():
        coop["inventory"][g] = coop["inventory"].get(g, 0) + q * runs * 10
    if rec["energy"]:
        coop["inventory"]["electricity"] = \
            coop["inventory"].get("electricity", 0) + rec["energy"] * runs * 10
    coop["labor_pool_hours"] = rec["labor_hours"] * runs * 10
    tx = Transaction(tick=2, sender="c0", action="PRODUCE",
                     payload={"coop_id": "bakery", "recipe_id": "flour_to_bread",
                              "runs": runs}, ruleset_version=1)
    ev = _apply_produce(s, tx, params)
    return ev["outputs"]["bread"], rec["outputs"]["bread"]


def test_funded_field_raises_output():
    """L3 direction: food know-how raises food-recipe output above base."""
    p = res_params()
    s = _world(p)
    s.research_funding["food"] = 50_000  # 1250bp bonus (50k*250/10k)
    assert research_effect_bp(s, s.recipes["flour_to_bread"], p) == 1_250
    produced, base = _produce_flour_to_bread(s, p)
    assert produced == base + base * 1_250 // 10_000


def test_unfunded_field_gives_no_bonus_and_cap_holds():
    """L3: no know-how => no bonus (TFP is earned, not free); the bonus
    clamps at max_output_bonus_bp however rich the field gets."""
    p = res_params()
    s = _world(p)
    assert research_effect_bp(s, s.recipes["flour_to_bread"], p) == 0
    produced, base = _produce_flour_to_bread(s, p)
    assert produced == base  # exactly base output
    # cap: 1,000,000cr food know-how would naively give 25,000bp -> cap 2500
    s.research_funding["food"] = 1_000_000
    assert research_effect_bp(s, s.recipes["flour_to_bread"], p) == 2_500


def test_crisis_redirects_all_innovation():
    """L3 flip: during an active crisis the whole allocation lands in the
    crisis kind's field (pandemic -> health)."""
    p = res_params()
    s = _world(p)
    s.innovation_pool = 10_000
    declare_crisis(s, 1, "pandemic", "vote")
    ev = allocate_fields_phase(s, 1, p)
    assert ev and ev[0]["action"] == "RESEARCH_ALLOCATE"
    assert s.research_funding.get("health", 0) == 10_000
    for f in ("food", "energy", "infrastructure", "computing"):
        assert s.research_funding.get(f, 0) == 0


def test_variant_unlock_lowers_input_cost():
    """L3 technology: crossing the unlock threshold in a field unlocks the
    next variant tier of that field's recipe - fewer inputs, same output
    (<=20%/tier cap)."""
    p = res_params()
    p["research"]["unlock_threshold"] = 5_000
    s = _world(p)
    s.innovation_pool = 50_000  # even split (no unmet needs): 10k/field >= threshold
    ev = allocate_fields_phase(s, 1, p)
    unlocks = [e for e in ev if e["action"] == "RESEARCH_UNLOCK"]
    assert unlocks, "no variant unlocked at threshold"
    for e in unlocks:
        base_r = s.recipes[e["from_recipe"]]
        var = s.recipes[e["recipe_id"]]
        assert var["outputs"] == base_r["outputs"]
        # inputs never increase; recipes with >1-unit inputs must shrink
        # at tier 1, but single-unit inputs stay at the min-1 floor (a
        # required input cannot drop to zero)
        for g, q in base_r["inputs"].items():
            assert var["inputs"][g] <= q
        assert e["tier"] == 1
    cheaper = [
        sum(s.recipes[e["recipe_id"]]["inputs"].values())
        < sum(s.recipes[e["from_recipe"]]["inputs"].values())
        for e in unlocks
    ]
    assert any(cheaper), "no variant actually cheaper at tier 1"


def test_money_conservation_across_buckets():
    """The research loop MOVES credits (surplus -> innovation pool ->
    know-how buckets); nothing is minted or retired."""
    p = res_params()
    p["research"]["research_share_bp"] = 10_000  # drain all surplus
    s = _world(p)
    s.surplus_pool = 100_000
    apply_tick(s, Ledger(), [], current_tick=1)
    total_knowhow = sum(s.research_funding.values()) + s.innovation_pool
    assert s.surplus_pool == 0
    assert total_knowhow == 100_000
    assert sum(s.balances.values()) + s.surplus_pool \
        + sum(int(c.get("treasury", 0)) for c in s.coops.values()) == 10_000


def test_absent_research_replays_unchanged():
    """Backward contract: research param absent => no funding, no bonus,
    no variants, produce byte-identical to the legacy path."""
    p = copy.deepcopy(DEFAULT_RULESET_PARAMS)
    p["triage_overrides"] = {}
    s = _world(p)
    s.innovation_pool = 50_000  # stale pool without the rule: untouched
    ev = allocate_fields_phase(s, 1, p)
    assert ev == []
    assert s.research_funding == {} and s.research_unlocked == {}
    assert research_effect_bp(s, s.recipes["flour_to_bread"], p) == 0
    produced, base = _produce_flour_to_bread(s, p)
    assert produced == base


def test_pipeline_end_to_end_and_error_visibility():
    """Full tick: surplus funds the pool, allocation converts it, produce
    feels it next tick. A broken allocation surfaces as an OVERSIGHT_FLAG,
    never a silent swallow."""
    p = res_params()
    p["research"]["research_share_bp"] = 10_000
    s = _world(p)
    s.surplus_pool = 100_000
    apply_tick(s, Ledger(), [], current_tick=1)
    assert s.research_funding  # allocation ran inside the real pipeline
    assert s.innovation_pool == 0
    # error visibility: force a broken state -> flag, not silence
    s2 = _world(p)
    s2.innovation_pool = 10_000
    s2.recipes_broken = True  # hostile attr won't matter; use monkey type err
    from openboard.research import allocate_fields_phase as afp
    orig = afp
    import openboard.research as rmod
    def boom(*a, **k):
        raise RuntimeError("synthetic")
    rmod.allocate_fields_phase = boom
    try:
        apply_tick(s2, Ledger(), [], current_tick=1)
    finally:
        rmod.allocate_fields_phase = orig
    assert any(f.get("kind") == "RESEARCH_ALLOCATE_ERROR" for f in s2.flags)
