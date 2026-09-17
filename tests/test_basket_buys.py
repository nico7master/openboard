"""WP4.2 performance floor (spec docs/superpowers/specs/2026-09-16-
performance-floor.md): BUY_ESSENTIAL_BASKET — one tx per citizen per tick
for ALL essential buys (~87% of ledger volume at 975 pop was singles).

Convention (every realism pack):
- FLIP: rule absent (basket_buys key missing or disabled) => basket txs are
  rejected and bots emit singles; old rulesets/worlds replay identically.
- Enabled => clearing-equivalent to the individual path: same bid dicts,
  same per-good buyer order, same settlements.
"""
import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from openboard.engine import apply_tick
from openboard.ledger import Ledger, Transaction
from openboard.rules import DEFAULT_RULESET_PARAMS
from openboard.state import genesis_state


class _Runner:
    """Drives apply_tick with an explicit monotonic tick counter."""

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
    if params:
        p.update(params)
    s = genesis_state({f"c{i}": 100_000 for i in range(n)}, ruleset_params=p)
    return s, Ledger()


def _essential_goods(s, k=3):
    """Pick k essential goods with positive quota + baseline, deterministic."""
    quota = s.active_ruleset_params().get("essential_need_quota", {})
    out = {}
    for good in sorted(quota):
        info = s.goods.get(good)
        if info and info.get("triage") in ("essential", "emergency") and quota[good] > 0:
            out[good] = min(quota[good], 1)
        if len(out) == k:
            break
    assert len(out) == k, f"need {k} essentials, got {list(out)}"
    return out


# --- FLIP: absent/disabled => inert -----------------------------------------

def test_basket_absent_is_rejected():
    """DEFAULT_RULESET_PARAMS has no basket_buys key => basket tx rejected."""
    assert "basket_buys" not in DEFAULT_RULESET_PARAMS  # legacy shape intact
    s, led = _world()
    goods = _essential_goods(s, 1)
    r = _Runner(s, led)
    r.run([r.tx("c0", "BUY_ESSENTIAL_BASKET", {"goods": goods})])
    rec = led.records[-1]
    assert not rec.accepted
    assert s.bids == []


def test_basket_disabled_is_rejected():
    s, led = _world({"basket_buys": {"enabled": False}})
    goods = _essential_goods(s, 1)
    r = _Runner(s, led)
    r.run([r.tx("c0", "BUY_ESSENTIAL_BASKET", {"goods": goods})])
    assert not led.records[-1].accepted


def test_basket_enabled_accepts_and_enqueues_sorted():
    s, led = _world({"basket_buys": {"enabled": True}})
    goods = _essential_goods(s, 3)
    r = _Runner(s, led)
    r.run([r.tx("c0", "BUY_ESSENTIAL_BASKET", {"goods": goods})])
    rec = led.records[-1]
    assert rec.accepted
    # clearing runs at end-of-tick and consumes s.bids, so assert on the
    # applied event entry (deterministic sorted-goods map):
    entry = [e for e in s.applied
             if e.get("action") == "BUY_ESSENTIAL_BASKET" and e.get("sender") == "c0"][-1]
    assert entry["goods"] == {g: goods[g] for g in sorted(goods)}


def test_basket_applier_enqueues_sorted_bids():
    """Unit: the applier builds byte-identical essential-bid dicts to the
    single path, in sorted(goods) order (clearing-order determinism)."""
    from openboard.engine import _apply_buy_essential_basket

    s, _ = _world({"basket_buys": {"enabled": True}})
    goods = _essential_goods(s, 3)
    tx = Transaction(tick=1, sender="c0", action="BUY_ESSENTIAL_BASKET",
                     payload={"goods": goods}, ruleset_version=s.ruleset_version)
    _apply_buy_essential_basket(s, tx)
    assert [(b["good"], b["qty"]) for b in s.bids] == [
        (g, goods[g]) for g in sorted(goods)
    ]
    assert all(b["essential"] and b["coop_id"] is None for b in s.bids)
    assert all(b["max_price"] == s.good_cost_baseline[b["good"]] for b in s.bids)


def test_basket_atomic_rejection():
    """One bad good (over quota) rejects the WHOLE basket — no partial bids."""
    s, led = _world({"basket_buys": {"enabled": True}})
    goods = _essential_goods(s, 1)
    bad = dict(goods)
    over = sorted(s.active_ruleset_params()["essential_need_quota"].items())
    for g, q in over:
        if g in s.goods and s.goods[g].get("triage") in ("essential", "emergency"):
            bad[g] = q + 1  # over quota
            break
    r = _Runner(s, led)
    r.run([r.tx("c0", "BUY_ESSENTIAL_BASKET", {"goods": bad})])
    assert not led.records[-1].accepted
    assert s.bids == []


def test_basket_rejects_unknown_and_nonessential():
    s, led = _world({"basket_buys": {"enabled": True}})
    goods = _essential_goods(s, 1)
    r = _Runner(s, led)

    r.now += 1
    apply_tick(s, led, [Transaction(tick=r.now, sender="c0",
                                    action="BUY_ESSENTIAL_BASKET",
                                    payload={"goods": {**goods, "no_such_good": 1}},
                                    ruleset_version=s.ruleset_version)],
               current_tick=r.now)
    assert not led.records[-1].accepted

    # find a market-triage good => NOT_ESSENTIAL
    market_good = next(g for g, info in sorted(s.goods.items())
                       if info.get("triage") == "market")
    r.run([r.tx("c0", "BUY_ESSENTIAL_BASKET", {"goods": {**goods, market_good: 1}})])
    assert not led.records[-1].accepted
    assert s.bids == []  # atomic: even the valid part never enqueues


def test_basket_funds_check_per_good_not_cumulative():
    """Matches the individual path: validation is per-good; settlement (not
    validation) drops takes the citizen cannot pay at clearing time. A
    cumulative pre-check would wrongly zero out citizens the individual
    path would have partially served."""
    from openboard.engine import _validate_buy_essential_basket

    s, led = _world({"basket_buys": {"enabled": True}})
    goods = _essential_goods(s, 3)
    cost = sum(s.good_cost_baseline[g] * q for g, q in goods.items())
    s.balances["c0"] = cost - 1  # individually affordable, cumulatively not
    tx = Transaction(tick=s.tick + 1, sender="c0", action="BUY_ESSENTIAL_BASKET",
                     payload={"goods": goods}, ruleset_version=s.ruleset_version)
    # validator passes (per-good check only — cumulative would reject)
    assert _validate_buy_essential_basket(s, tx, s.active_ruleset_params()) is None
    r = _Runner(s, led)
    r.run([tx])
    assert led.records[-1].accepted
    entry = [e for e in s.applied
             if e.get("action") == "BUY_ESSENTIAL_BASKET" and e.get("sender") == "c0"][-1]
    assert entry["goods"] == {g: goods[g] for g in sorted(goods)}


def test_basket_insufficient_funds_for_one_good_rejects():
    s, led = _world({"basket_buys": {"enabled": True}})
    goods = _essential_goods(s, 1)
    g, q = next(iter(goods.items()))
    s.balances["c0"] = s.good_cost_baseline[g] * q - 1
    r = _Runner(s, led)
    r.run([r.tx("c0", "BUY_ESSENTIAL_BASKET", {"goods": goods})])
    assert not led.records[-1].accepted


# --- clearing equivalence ----------------------------------------------------

def test_basket_clearing_equivalent_to_singles():
    """Identical worlds: one citizen files k singles vs 1 basket with the
    same goods/qtys => identical inventories/balances/pool after clearing."""
    results = []
    for basket in (True, False):
        s, led = _world({"basket_buys": {"enabled": basket}})
        goods = _essential_goods(s, 3)
        # stock every producer coop's inventory so listings exist
        for coop in s.coops.values():
            for g in goods:
                if g in coop.get("inventory", {}):
                    coop["inventory"][g] += 500
        r = _Runner(s, led)
        if basket:
            txs = [r.tx("c0", "BUY_ESSENTIAL_BASKET", {"goods": goods})]
        else:
            txs = [r.tx("c0", "BUY_ESSENTIAL", {"good": g, "qty": goods[g]})
                   for g in sorted(goods)]
        r.run(txs)
        r.run([])  # clearing happens end-of-tick; second tick settles rest
        inv = dict(s.citizen_inventory.get("c0", {}))
        results.append({
            "inv": {g: inv.get(g, 0) for g in goods},
            "bal": s.balances["c0"],
            "pool": s.surplus_pool,
        })
    assert results[0]["inv"] == results[1]["inv"]
    assert results[0]["bal"] == results[1]["bal"]
    assert results[0]["pool"] == results[1]["pool"]


# --- bot side ----------------------------------------------------------------

def test_bots_emit_basket_when_enabled_and_singles_when_absent():
    from openboard.bots import personal_needs

    s, _ = _world({"basket_buys": {"enabled": True}})
    who = "c0"
    s.balances[who] = 100_000
    params = s.active_ruleset_params()
    txs = personal_needs(who, s, params, s.tick + 1)
    baskets = [t for t in txs if t.action == "BUY_ESSENTIAL_BASKET"]
    singles = [t for t in txs if t.action == "BUY_ESSENTIAL"]
    assert singles == []
    assert len(baskets) <= 1
    if baskets:
        goods = baskets[0].payload["goods"]
        assert isinstance(goods, dict) and goods
        assert all(isinstance(q, int) and q > 0 for q in goods.values())

    # legacy: key absent => singles only, no basket
    s2, _ = _world()
    s2.balances[who] = 100_000
    txs2 = personal_needs(who, s2, s2.active_ruleset_params(), s2.tick + 1)
    assert all(t.action != "BUY_ESSENTIAL_BASKET" for t in txs2)


def test_new_game_params_enable_basket():
    """server._params() (new games) carries basket_buys enabled."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "dashboard"))
    from server import Run

    run = Run(seed=42)
    assert run._params().get("basket_buys", {}).get("enabled") is True
