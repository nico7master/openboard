"""Realism contract L6 (spec 2026-09-11-regional-markets-perf-bundle.md):
regional markets.

Real-world effect under contract:
- DIRECTION: real economies are local markets under global law; scarcity
  is regional before it is global.
- MECHANISM: buyers (citizens AND coops-as-buyers) are partitioned into
  deterministic hash-bucket regions; essential + auction clearing runs
  once per region in tick-rotated order; listings stay CITY-WIDE (coops
  are producers with full visibility); unsold returns are deferred so
  later regions still see remaining supply, then one global sweep + ONE
  global scarcity update close the tick.
- MAGNITUDE: regions = clamp(pop/100, 4..16) or explicit param; money
  conservation is EXACT across all regional passes.
- FLIP: rule absent (or regions=1) => city-wide clearing, byte-identical
  legacy path.
"""
import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from openboard.engine import apply_tick
from openboard.ledger import Ledger, Transaction
from openboard.regions import region_count, region_of, region_order
from openboard.rules import DEFAULT_RULESET_PARAMS, validate_params
from openboard.state import genesis_state


def rm_params(**over):
    p = copy.deepcopy(DEFAULT_RULESET_PARAMS)
    p["triage_overrides"] = {}
    p["regional_markets"] = {"enabled": True, "regions": 3}
    p.update(over)
    return p


def _world(params, n=6):
    return genesis_state({f"c{i}": 50_000 for i in range(n)}, ruleset_params=params)


def _found(s, led, tick=0):
    # founding declares ALL members inline (validator requires members
    # list incl. sender); no separate JOIN_COOP txs needed
    apply_tick(s, led, [Transaction(tick=tick, sender="c0", action="FOUND_COOP",
        payload={"coop_id": "k1", "name": "Bakery",
                 "members": [f"c{i}" for i in range(6)]},
        ruleset_version=1)], current_tick=tick)


def _list_and_bid(s, led, t, qty=10, bids=(("c1", 3), ("c2", 3), ("c4", 3))):
    # the coop produced the bread it is about to list; LIST_GOOD is sent
    # by a MEMBER (c0), payload is exactly {coop_id, good, qty} - the
    # floor is the engine's own cost baseline, not a payload field
    inv = s.coops["k1"]["inventory"]
    inv["bread"] = inv.get("bread", 0) + qty
    txs = [Transaction(tick=t, sender="c0", action="LIST_GOOD",
           payload={"coop_id": "k1", "good": "bread", "qty": qty},
           ruleset_version=1)]
    for who, q in bids:
        txs.append(Transaction(tick=t, sender=who, action="BID",
                 payload={"good": "bread", "qty": q, "max_price": 80},
                 ruleset_version=1))
    apply_tick(s, led, txs, current_tick=t)


def _total(s):
    return (sum(s.balances.values()) + int(s.surplus_pool)
            + sum(int(c.get("treasury", 0)) for c in s.coops.values()))


def test_region_assignment_deterministic_and_total():
    """Region ids are a pure function of the owner id: stable across
    calls, inside [0, n), and every owner gets exactly one region."""
    p = rm_params()
    assert validate_params(p) is None
    n = region_count(p, 966)
    assert n == 3  # explicit param wins over the pop formula
    assert region_count(p, 966) == n  # stable
    for owner in ("c0", "c1", "coop:k1", "zzz"):
        r = region_of(owner, n)
        assert 0 <= r < n
        assert region_of(owner, n) == r
    assert region_count({"regional_markets": {"enabled": False}}, 966) == 1
    # auto formula: clamp(pop/100, 4..16)
    auto = {"enabled": True, "regions": 0}
    assert region_count({"regional_markets": auto}, 966) == 9  # 966//100
    assert region_count({"regional_markets": auto}, 200) == 4  # floor
    assert region_count({"regional_markets": auto}, 50_000) == 16  # cap


def test_rule_off_matches_regions_one_exactly():
    """Backward contract: rule absent and regions=1 produce the identical
    world (the wrapper's degenerate path IS the legacy path)."""
    off = copy.deepcopy(DEFAULT_RULESET_PARAMS)
    off["triage_overrides"] = {}
    one = rm_params(regions=1)
    one["regional_markets"] = {"enabled": True, "regions": 1}
    fps = []
    for params in (off, one):
        s = _world(params)
        led = Ledger()
        _found(s, led)
        for t in range(1, 4):
            _list_and_bid(s, led, t)
        import hashlib, json as _j
        fps.append(hashlib.sha256(_j.dumps(s.applied, sort_keys=True,
                   default=str).encode()).hexdigest())
    assert fps[0] == fps[1]


def test_multi_region_conservation_and_deferred_unsold():
    """L6 conservation: with 3 regions and city-wide supply, every sold
    unit moves money exactly; supply NOT sold in early regions survives
    for later regions (deferred unsold) and is returned exactly once."""
    p = rm_params()
    s = _world(p)
    led = Ledger()
    before = _total(s)
    _found(s, led)
    _list_and_bid(s, led, 1, qty=10)  # 3 buyers in (possibly) different regions, 9 of 10 units
    sold = sum(1 for e in s.applied
               if isinstance(e, dict) and e.get("action") == "MARKET_CLEAR_AUCTION"
               for w in e.get("winners", []))
    assert sold == 3  # all three bids won across regions
    assert _total(s) == before  # exact, nothing minted or burned
    # unsold 1 unit returned to the coop exactly once (10 - 9 = 1)
    assert s.coops["k1"]["inventory"]["bread"] == 1


def test_scarcity_updated_once_per_tick_globally():
    """The L2 scarcity signal is a GLOBAL price signal: with unmet demand
    and R regions, it steps ONCE (+step_bp), not once per region."""
    p = rm_params()
    p["scarcity_pricing"] = {"enabled": True, "step_bp": 500,
                             "max_markup_bp": 2_500, "decay_bp": 250}
    s = _world(p)
    led = Ledger()
    _found(s, led)
    # demand 30 units, supply 10 -> unmet in every region
    _list_and_bid(s, led, 1, qty=10, bids=(("c1", 10), ("c2", 10), ("c4", 10)))
    assert s.scarcity_signal.get("bread", 0) == 500  # exactly one step


def test_regional_rotation_is_deterministic():
    """Tick-rotated region order: varies with tick (fairness) but is a
    pure function of (tick, n) - same inputs, same order, always."""
    assert region_order(3, 1) == [1, 2, 0]
    assert region_order(3, 1) == [1, 2, 0]  # stable
    assert region_order(3, 4) == [1, 2, 0]  # 4 % 3 == 1
    assert region_order(3, 0) == [0, 1, 2]


def test_params_validation_blocks_bad_regions():
    """Strict validation: negative/huge/non-int region counts rejected."""
    p = rm_params()
    assert validate_params(p) is None
    bad = rm_params(regions=-2)
    bad["regional_markets"]["regions"] = -2
    assert validate_params(bad) is not None
    bad = rm_params(regions=10_001)
    bad["regional_markets"]["regions"] = 10_001
    assert validate_params(bad) is not None
    bad = rm_params()
    bad["regional_markets"] = "yes"
    assert validate_params(bad) is not None
