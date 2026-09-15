"""Source-model completion tests (spec 2026-09-15 §C): need-first
allocation of scarce essentials — priority lists and lotteries."""
import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from openboard.engine import apply_tick
from openboard.ledger import Ledger, Transaction
from openboard.rules import DEFAULT_RULESET_PARAMS
from openboard.state import genesis_state


class _Runner:
    def __init__(self, s, led):
        self.s, self.led = s, led
        self.now = s.tick

    def run(self, txs):
        self.now += 1
        apply_tick(self.s, self.led, txs, current_tick=self.now)

    def tx(self, sender, action, payload):
        return Transaction(tick=self.now + 1, sender=sender, action=action,
                           payload=payload, ruleset_version=self.s.ruleset_version)


def _world(params=None, n=3):
    p = copy.deepcopy(DEFAULT_RULESET_PARAMS)
    p["scarcity_pricing"] = {"enabled": False, "max_markup_bp": 2_500,
                             "step_bp": 500, "decay_bp": 250}
    if params:
        p.update(params)
    s = genesis_state({f"c{i}": 100_000 for i in range(n)}, ruleset_params=p)
    return s, Ledger()


def _seed_listing(s, good="bread", qty=1, price=10):
    """A coop with one listing of a scarce essential."""
    s.coops["k0"] = {
        "id": "k0", "name": "bakery", "members": ["c0"], "recipe_intent": "bakery_bread",
        "treasury": 5_000, "founded_tick": 0, "founder": "c0",
    }
    s.listings[good] = [{"coop_id": "k0", "qty": qty, "floor": price, "price": price}]


def _bids(s, r, good="bread", qty=1):
    bids = []
    for who in ("c1", "c2"):
        s.balances.setdefault(who, 100_000)
        bids.append(r.tx(who, "BUY_ESSENTIAL", {"good": good, "qty": qty}))
    return bids


def _last_clear_events(s):
    return [e for e in s.applied if e.get("action") == "MARKET_CLEAR_ESSENTIAL"]


def test_priority_serves_longest_unmet_first():
    na = {"enabled": True, "mode": "priority"}
    s, led = _world({"need_allocation": na})
    _seed_listing(s, qty=1)
    # c1 suffered 7 ticks, c2 never.
    s.unmet_needs["c1"] = {"bread": 7}
    r = _Runner(s, led)
    r.run(_bids(s, r))
    ev = _last_clear_events(s)[-1]
    served = {b["bidder"]: b["qty"] for b in ev["buyers"]}
    assert served.get("c1") == 1, f"longest-unmet c1 must be served first: {served}"
    assert served.get("c2", 0) == 0, f"short supply: c2 must get nothing: {served}"


def test_lottery_deterministic_and_replayable():
    na = {"enabled": True, "mode": "lottery"}
    out = []
    for _ in range(2):
        s, led = _world({"need_allocation": na})
        _seed_listing(s, qty=1)
        s.unmet_needs["c1"] = {"bread": 7}  # lottery ignores streaks
        r = _Runner(s, led)
        r.run(_bids(s, r))
        ev = _last_clear_events(s)[-1]
        out.append({b["bidder"]: b["qty"] for b in ev["buyers"]})
    assert out[0] == out[1], "lottery must be replay-identical"


def test_default_off_keeps_rotation():
    s, led = _world()  # no need_allocation key
    _seed_listing(s, qty=1)
    s.unmet_needs["c1"] = {"bread": 7}
    r = _Runner(s, led)
    r.run(_bids(s, r))
    ev = _last_clear_events(s)[-1]
    served = {b["bidder"]: b["qty"] for b in ev["buyers"]}
    # 2 buyers: rotation off = tick%2; either deterministic outcome is
    # fine as long as it is NOT need-first (c2 must be able to win).
    assert served.get("c1", 0) + served.get("c2", 0) == 1


def test_kcal_food_reads_group_streak():
    na = {"enabled": True, "mode": "priority"}
    p = {"need_allocation": na,
         "kcal_needs": {"enabled": True,
                        "kcal_per_unit": {"bread": 2650, "grain": 3400},
                        "daily_kcal": 2900}}
    s, led = _world(p)
    _seed_listing(s, qty=1)
    # kcal foods report under the group key "food": c1 has a food streak,
    # c2 has none — c1 must win despite per-good "bread" key being absent.
    s.unmet_needs["c1"] = {"food": 7}
    r = _Runner(s, led)
    r.run(_bids(s, r))
    ev = _last_clear_events(s)[-1]
    served = {b["bidder"]: b["qty"] for b in ev["buyers"]}
    assert served.get("c1") == 1, f"kcal group streak must drive priority: {served}"


def test_crisis_forces_priority():
    """Crisis override: even lottery mode must serve need-first."""
    from openboard import crisis as crisis_mod
    na = {"enabled": True, "mode": "lottery"}
    s, led = _world({"need_allocation": na})
    _seed_listing(s, qty=1)
    s.unmet_needs["c1"] = {"bread": 9}
    s.crisis = {"active": True, "kind": "drought", "source": "vote",
                "declared_tick": 1, "ratify_by": None, "ratified": True,
                "votes_for": 2, "votes_against": 0}
    r = _Runner(s, led)
    r.run(_bids(s, r))
    ev = _last_clear_events(s)
    served = {}
    if ev:
        served = {b["bidder"]: b["qty"] for b in ev[-1]["buyers"]}
    assert served.get("c1") == 1, f"crisis must force need-first: {served}"
