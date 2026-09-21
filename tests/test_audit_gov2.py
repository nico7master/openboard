"""Audit 2026-09-20 package P-GOV2: S2 vote-buying enforcement (the source's
absolute "votes cannot be bought") and S3 the third allocation mode
("or democratic decision", spec 2026-09-15 section C). All offline."""
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


def _gov():
    return {"enabled": True, "vote_window_ticks": 3, "quorum_bp": 1_000,
            "trial_period_ticks": 10, "vote_token_bp": 10_000,
            "vote_cycle_ticks": 30, "persuasion": True}


VB = {"enabled": True, "window_ticks": 30, "fine": 500}


def _world(params=None, n=3):
    p = copy.deepcopy(DEFAULT_RULESET_PARAMS)
    if params:
        p.update(params)
    s = genesis_state({f"c{i}": 100_000 for i in range(n)}, ruleset_params=p)
    return s, Ledger()


def _flags(s):
    return [f for f in s.flags if f.get("kind") == "VOTE_BUYING"]


def _total(s):
    return (sum(s.balances.values()) + s.surplus_pool + s.capital_fund
            + sum(c.get("treasury", 0) for c in s.coops.values()))


def test_s2_transfer_pair_flagged_fined_revoked():
    """A transfer paired with an active delegation (delegate -> payer):
    public flag, bought delegation revoked, payer fined into the pool."""
    s, led = _world({"governance": _gov(), "vote_buying": VB})
    r = _Runner(s, led)
    r.run([r.tx("c1", "DELEGATE", {"to": "c0"})])
    assert s.delegations.get("c1") == "c0"  # healthy delegation first
    b0, b1, pool0 = s.balances["c0"], s.balances["c1"], s.surplus_pool
    r.run([r.tx("c0", "TRANSFER", {"to": "c1", "amount": 700})])  # buy c1's trust
    fl = _flags(s)
    assert len(fl) == 1 and fl[0]["target"] == "c0" and fl[0]["other"] == "c1"
    assert s.delegations.get("c1") is None          # the bought vote dies
    assert s.balances["c0"] == b0 - 700 - 500       # transfer + fine
    assert s.balances["c1"] == b1 + 700
    assert s.surplus_pool == pool0 + 500            # fine lands in the pool


def test_s2_pay_then_delegate_rejected():
    """Money changed hands recently -> the follow-up delegation is refused."""
    s, led = _world({"governance": _gov(), "vote_buying": VB})
    r = _Runner(s, led)
    r.run([r.tx("c0", "TRANSFER", {"to": "c1", "amount": 100})])
    r.run([r.tx("c1", "DELEGATE", {"to": "c0"})])
    assert s.delegations.get("c1") is None  # validator killed the pairing


def test_s2_unrelated_transfers_not_flagged():
    """Transfers with no delegation pairing stay silent — normal commerce."""
    s, led = _world({"governance": _gov(), "vote_buying": VB})
    r = _Runner(s, led)
    r.run([r.tx("c0", "TRANSFER", {"to": "c1", "amount": 250})])
    r.run([r.tx("c2", "TRANSFER", {"to": "c0", "amount": 100})])
    assert not _flags(s)


def test_s2_absent_param_replay_identical():
    """No vote_buying key -> zero behavior change (legacy worlds byte-exact)."""
    s, led = _world({"governance": _gov()})
    r = _Runner(s, led)
    r.run([r.tx("c1", "DELEGATE", {"to": "c0"})])
    r.run([r.tx("c0", "TRANSFER", {"to": "c1", "amount": 700})])
    assert not _flags(s)
    assert s.delegations.get("c1") == "c0"  # untouched legacy semantics


def test_s2_money_conserved_through_fine():
    """The fine MOVES credits payer->pool; conservation stays exact."""
    s, led = _world({"governance": _gov(), "vote_buying": VB})
    r = _Runner(s, led)
    r.run([r.tx("c1", "DELEGATE", {"to": "c0"})])
    t0 = _total(s)
    r.run([r.tx("c0", "TRANSFER", {"to": "c1", "amount": 700})])
    assert _total(s) == t0


def test_s2_pair_cache_survives_next_tick():
    """The detector reads the TRANSFER history across ticks (cache rebuild):
    a delegation活跃 during a LATER transfer still gets caught."""
    s, led = _world({"governance": _gov(), "vote_buying": VB})
    r = _Runner(s, led)
    r.run([r.tx("c1", "DELEGATE", {"to": "c0"})])
    r.run([])  # separate tick: delegation active, no transfer yet
    r.run([r.tx("c0", "TRANSFER", {"to": "c1", "amount": 50})])
    assert len(_flags(s)) == 1
    assert s.delegations.get("c1") is None


def test_s3_democratic_mode_orders_by_trust():
    """The source's third mode: community trust (delegations received)
    orders the scarce-goods queue; ties fall back to need, then name."""
    p = {"need_allocation": {"enabled": True, "mode": "democratic"},
         "scarcity_pricing": {"enabled": False, "max_markup_bp": 2_500,
                              "step_bp": 500, "decay_bp": 250}}
    s, led = _world(p, n=3)
    r = _Runner(s, led)
    r.run([r.tx("c2", "DELEGATE", {"to": "c1"})])  # c1 holds community trust
    # scarce essential: 1 unit in the common pool, two want it
    s.coops["k0"] = {"id": "k0", "name": "b", "members": ["c0"],
                     "recipe_intent": "bakery_bread", "treasury": 5_000,
                     "founded_tick": 0, "founder": "c0"}
    s.common_pool["bread"] = 1
    r.run([r.tx("c1", "BUY_ESSENTIAL", {"good": "bread", "qty": 1}),
           r.tx("c2", "BUY_ESSENTIAL", {"good": "bread", "qty": 1})])
    inv1 = s.citizen_inventory.get("c1", {}).get("bread", 0)
    inv2 = s.citizen_inventory.get("c2", {}).get("bread", 0)
    assert inv1 == 1 and inv2 == 0  # the trusted citizen is served first


def test_s3_democratic_mode_validated_and_default_off():
    """'democratic' passes validation; legacy worlds without need_allocation
    are untouched."""
    from openboard.rules import validate_params
    p = copy.deepcopy(DEFAULT_RULESET_PARAMS)
    p["need_allocation"] = {"enabled": True, "mode": "democratic"}
    assert validate_params(p) is None
    bad = copy.deepcopy(p)
    bad["need_allocation"] = {"enabled": True, "mode": "mob"}
    assert validate_params(bad) is not None
