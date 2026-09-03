"""A2: emergent entrepreneurship — the entrepreneur bot detects a chronic
shortage (unmet >= 5 ticks, zero active listings) and FOUND_COOPs with a
declared recipe_id. Market entry without capitalists."""
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from openboard.bots import ARCHETYPES, entrepreneur
from openboard.engine import apply_tick
from openboard.ledger import Ledger
from openboard.state import genesis_state


def _params():
    from openboard.rules import DEFAULT_RULESET_PARAMS
    import copy

    p = copy.deepcopy(DEFAULT_RULESET_PARAMS)
    p["triage_overrides"] = {}
    p["needs"] = {"books": 1}
    p["essential_need_quota"] = {"books": 1}
    return p


def _world():
    s = genesis_state({"e1": 800, "f1": 500, "w1": 500}, ruleset_params=_params())
    # f1 and w1 are seeded into a coop by genesis in the real world; here
    # they start free so the entrepreneur can recruit them.
    return s


def test_no_shortage_no_action():
    s = _world()
    txs = entrepreneur("e1", s, s.active_ruleset_params(), 1, random.Random(1))
    # founders buy their own needs (feeding fix) but must NOT found
    assert all(t.action != "FOUND_COOP" for t in txs)


def test_chronic_shortage_triggers_founding():
    s = _world()
    # books unmet for 7 ticks, zero listings
    for c in s.balances:
        s.unmet_needs[c] = {"books": 7}
    txs = entrepreneur("e1", s, s.active_ruleset_params(), 1, random.Random(1))
    found = [t for t in txs if t.action == "FOUND_COOP"]
    assert len(found) == 1
    tx = found[0]
    assert tx.action == "FOUND_COOP"
    assert tx.payload["recipe_id"] == "book_printing"  # produces books
    assert tx.payload["members"] == ["e1", "f1"]  # self + first free citizen
    assert tx.sender == "e1"


def test_covered_good_ignored():
    s = _world()
    for c in s.balances:
        s.unmet_needs[c] = {"books": 7}
    s.listings["books"] = [{"seller": "x", "floor": 5, "qty": 3, "tick": 1}]
    txs = entrepreneur("e1", s, s.active_ruleset_params(), 1, random.Random(1))
    assert all(t.action != "FOUND_COOP" for t in txs)  # market already covers books


def test_already_in_coop_no_action():
    s = _world()
    s.coops["existing"] = {"name": "X", "members": ["e1"], "inventory": {}}
    for c in s.balances:
        s.unmet_needs[c] = {"books": 9}
    txs = entrepreneur("e1", s, s.active_ruleset_params(), 1, random.Random(1))
    # seated founders now WORK (join-and-work fallback) but never re-found
    assert all(t.action != "FOUND_COOP" for t in txs)


def test_founding_applies_end_to_end():
    """Integration: the entrepreneur's tx passes the engine and the coop
    exists with recipe_intent set."""
    s = _world()
    for c in s.balances:
        s.unmet_needs[c] = {"books": 7}
    bot = ARCHETYPES["entrepreneur"]
    txs = bot("e1", s, s.active_ruleset_params(), 1, random.Random(1))
    led = Ledger()
    apply_tick(s, led, txs, current_tick=1)
    coop_id = [t for t in txs if t.action == "FOUND_COOP"][0].payload["coop_id"]
    assert coop_id in s.coops
    assert s.coops[coop_id]["recipe_intent"] == "book_printing"
    assert "e1" in s.coops[coop_id]["members"]
