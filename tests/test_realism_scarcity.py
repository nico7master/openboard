"""Realism contract L2 (spec 2026-09-11 Part II, Lever 2): scarcity pricing.

Real-world effect under contract:
- DIRECTION: persistent unmet demand raises prices above cost (rationing +
  supply signal); when supply serves demand, the premium decays; needs-based
  essential purchases never pay the premium; crisis forces it to zero.
- MECHANISM: the ENGINE sets a market-signal premium (bp of cost floor) from
  economy-wide unmet bid volume — not the seller. Listings are tick-scoped
  (cleared/returned at end of each tick), so the premium is re-justified
  every tick (inherent decay-to-cost). The premium flows through the
  existing clearing paths (producer pass pays the listing price; the
  uniform auction's clearing price already discovers prices above floor
  via bids).
- MAGNITUDE: max_markup_bp votable (default 2500bp = +25%), step 500bp/tick
  of sustained shortage, decay 250bp/tick when served.
- FLIP: crisis zero-gouging rule — signal clamps to 0 while a crisis is
  active; rule absent/disabled => engine behavior byte-identical to before.

Testing note: listings never survive past the tick they are cleared in, so
price assertions use direct _apply_list_good calls (no clearing), while
signal/flow assertions use full apply_tick runs. Integer-only throughout.
"""
import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from openboard.engine import _apply_list_good, apply_tick
from openboard.errors import Reason
from openboard.ledger import Ledger, Transaction
from openboard.rules import DEFAULT_RULESET_PARAMS, validate_params
from openboard.state import genesis_state


def sp_params(**over):
    p = copy.deepcopy(DEFAULT_RULESET_PARAMS)
    p["triage_overrides"] = {}
    p["scarcity_pricing"] = {
        "enabled": True, "max_markup_bp": 2_500,
        "step_bp": 500, "decay_bp": 250,
    }
    p.update({k: v for k, v in over.items() if k != "scarcity_pricing"})
    return p


def _world(params, n=3):
    # 100k each: bids of ~100cr x 50qty must never trip the affordability
    # validator (5,000 balance made 101x50 INSUFFICIENT_FUNDS).
    return genesis_state({f"c{i}": 100_000 for i in range(n)}, ruleset_params=params)


def _found_bakery(s, tick=1):
    apply_tick(s, Ledger(), [Transaction(
        tick=tick, sender="c0", action="FOUND_COOP",
        payload={"coop_id": "bakery", "name": "bakery", "members": ["c0", "c1"]},
        ruleset_version=1)], current_tick=tick)


def _list(s, tick, qty, clearance=False, good="bread", batch_with=None):
    """List within a full tick; optionally batch bids into the SAME tick
    (listings are tick-scoped, so list+bid belong to one apply_tick)."""
    s.coops["bakery"].setdefault("inventory", {})[good] = qty
    payload = {"coop_id": "bakery", "good": good, "qty": qty}
    if clearance:
        payload["clearance"] = True
    txs = [Transaction(
        tick=tick, sender="c0", action="LIST_GOOD", payload=payload,
        ruleset_version=1)]
    if batch_with is not None:
        who, max_price, bq = batch_with
        txs.append(Transaction(
            tick=tick, sender=who, action="BID",
            payload={"good": good, "max_price": max_price, "qty": bq},
            ruleset_version=1))
    apply_tick(s, Ledger(), txs, current_tick=tick)


def _list_price_direct(s, tick, qty, clearance=False, good="bread"):
    """Apply LIST_GOOD without clearing; return the listing's unit price."""
    s.coops["bakery"].setdefault("inventory", {})[good] = qty
    payload = {"coop_id": "bakery", "good": good, "qty": qty}
    if clearance:
        payload["clearance"] = True
    tx = Transaction(tick=tick, sender="c0", action="LIST_GOOD",
                     payload=payload, ruleset_version=1)
    _apply_list_good(s, tx)
    return s.listings[good][-1]["price"]


def _bid(s, tick, who, good, max_price, qty, essential=False):
    action = "BUY_ESSENTIAL" if essential else "BID"
    payload = {"good": good, "max_price": max_price, "qty": qty}
    if essential:
        payload = {"good": good, "qty": qty}  # validator: {good, qty} only
    apply_tick(s, Ledger(), [Transaction(
        tick=tick, sender=who, action=action,
        payload=payload, ruleset_version=1)], current_tick=tick)


def _shortage_tick(s, tick, listed=5, wanted=50):
    """One tick, one batch: supply < demand (the standard shortage step).
    max_price varies by tick — the ledger suppresses duplicate tx payloads."""
    _list(s, tick, listed, batch_with=("c2", 100 + tick, wanted))


def test_scarcity_signal_rises_with_unmet_demand():
    """L2 direction: shortage -> signal ramps step_bp/tick; fresh listings
    carry the current signal as a premium over the cost floor."""
    s = _world(sp_params())
    _found_bakery(s)
    _shortage_tick(s, 2)
    assert s.scarcity_signal["bread"] == 500
    floor = s.good_cost_baseline["bread"]
    # direct listing at tick 3 sees the tick-2 signal
    assert _list_price_direct(s, 3, 5) == floor + floor * 500 // 10_000
    _shortage_tick(s, 3)
    assert s.scarcity_signal["bread"] == 1_000
    assert _list_price_direct(s, 4, 5) == floor + floor * 1_000 // 10_000


def test_premium_capped():
    """L2 magnitude: signal clamps at max_markup_bp."""
    p = sp_params()
    p["scarcity_pricing"]["step_bp"] = 900
    s = _world(p)
    _found_bakery(s)
    for t in (2, 3, 4, 5):
        _shortage_tick(s, t)
    assert s.scarcity_signal["bread"] == 2_500  # cap
    floor = s.good_cost_baseline["bread"]
    assert _list_price_direct(s, 6, 5) == floor + floor * 2_500 // 10_000


def test_signal_decays_when_served():
    """L2 decay: a fully served tick lowers the signal by decay_bp, then
    clears it; the premium falls with it back to cost."""
    s = _world(sp_params())
    _found_bakery(s)
    _shortage_tick(s, 2)
    assert s.scarcity_signal["bread"] == 500
    # fully served: supply covers the whole bid (one batch)
    _list(s, 3, 100, batch_with=("c2", 100, 50))
    assert s.scarcity_signal["bread"] == 250  # decayed one step
    assert _list_price_direct(s, 4, 5) == s.good_cost_baseline["bread"] + \
        s.good_cost_baseline["bread"] * 250 // 10_000
    # another fully-served tick clears it entirely
    _list(s, 4, 100, batch_with=("c2", 100, 50))
    assert "bread" not in s.scarcity_signal
    assert _list_price_direct(s, 5, 10) == s.good_cost_baseline["bread"]


def test_essential_never_pays_premium():
    """L2 need-first: BUY_ESSENTIAL settlement stays at the cost floor even
    while a scarcity premium inflates the same good's listing price.
    Asserted via the buyer's balance (robust to pool pre-serving)."""
    s = _world(sp_params())
    _found_bakery(s)
    _shortage_tick(s, 2)
    assert s.scarcity_signal["bread"] >= 500
    floor = s.good_cost_baseline["bread"]
    before = s.balances["c2"]
    # essential buyer + fresh premium-priced listing in one tick
    s.coops["bakery"].setdefault("inventory", {})["bread"] = 10
    apply_tick(s, Ledger(), [
        Transaction(tick=3, sender="c0", action="LIST_GOOD",
                    payload={"coop_id": "bakery", "good": "bread", "qty": 10},
                    ruleset_version=1),
        Transaction(tick=3, sender="c2", action="BUY_ESSENTIAL",
                    payload={"good": "bread", "qty": 1},  # quota 1 (true-need balance)
                    ruleset_version=1),
    ], current_tick=3)
    paid = before - s.balances["c2"]
    assert paid == 1 * floor  # floor, NOT premium price


def test_crisis_zeroes_scarcity_premium():
    """L2 flip: anti-gouging — while a crisis is ACTIVE the premium clamps
    to zero (new listings price at floor; the signal freezes at 0)."""
    s = _world(sp_params())
    _found_bakery(s)
    _shortage_tick(s, 2)
    assert s.scarcity_signal["bread"] == 500
    from openboard.crisis import declare_crisis
    declare_crisis(s, 3, "famine", "vote")
    assert _list_price_direct(s, 4, 5) == s.good_cost_baseline["bread"]
    _shortage_tick(s, 4)  # shortage persists, but signal frozen at 0
    assert s.scarcity_signal.get("bread", 0) == 0


def test_rule_off_replays_identical_pricing():
    """Backward contract: rule absent => listing price equals floor exactly
    as before (and no signal state is created)."""
    p = copy.deepcopy(DEFAULT_RULESET_PARAMS)
    p["triage_overrides"] = {}
    s = _world(p)
    _found_bakery(s)
    _shortage_tick(s, 2)
    assert _list_price_direct(s, 3, 5) == s.good_cost_baseline["bread"]
    assert s.scarcity_signal == {}


def test_scarcity_param_validation():
    """Param schema: strict keys/types/bounds when present."""
    ok = sp_params()
    assert validate_params(ok) is None
    bad_key = sp_params()
    bad_key["scarcity_pricing"]["surprise"] = 1
    assert validate_params(bad_key) == Reason.INVALID_RULESET
    bad_type = sp_params()
    bad_type["scarcity_pricing"]["max_markup_bp"] = "big"
    assert validate_params(bad_type) == Reason.INVALID_RULESET
    bad_bound = sp_params()
    bad_bound["scarcity_pricing"]["step_bp"] = 0
    assert validate_params(bad_bound) == Reason.INVALID_RULESET


def test_clearance_listing_ignores_premium():
    """Clearance stays a sub-floor glut-dump; premium never mixes in."""
    p = sp_params(clearance=True)
    s = _world(p)
    _found_bakery(s)
    _shortage_tick(s, 2)
    assert s.scarcity_signal["bread"] >= 500
    price = _list_price_direct(s, 3, 8, clearance=True)
    floor = s.good_cost_baseline["bread"]
    assert price < floor  # discounted, not marked up
