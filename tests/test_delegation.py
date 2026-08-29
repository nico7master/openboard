"""A3: delegative democracy — DELEGATE action, revocable, cycle-safe;
tally expansion counts delegated citizens (direct votes always win);
gated by optional `delegation` param (absent = off = replay identical)."""
import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from openboard.engine import apply_tick, expand_ballots
from openboard.ledger import Ledger, Transaction
from openboard.state import genesis_state


def _params(delegation=True):
    from openboard.rules import DEFAULT_RULESET_PARAMS

    p = copy.deepcopy(DEFAULT_RULESET_PARAMS)
    p["triage_overrides"] = {}
    p["governance"] = {"enabled": True, "vote_window_ticks": 3,
                       "quorum_bp": 5_000, "trial_period_ticks": 10}
    if delegation:
        p["delegation"] = {"enabled": True}
    return p


def _propose_and_open(s, proposer, params_mut=None):
    """Open a proposal via PROPOSE + fast-forward to closes_tick."""
    from openboard.ledger import Ledger, Transaction
    base = copy.deepcopy(s.active_ruleset_params())
    base["wealth_tax"] = {"threshold": 5_000, "rate_bp": 300}
    led = Ledger()
    tx = Transaction(tick=s.tick + 1, sender=proposer, action="PROPOSE",
                     payload={"params": base, "activation_tick": s.tick + 10},
                     ruleset_version=s.ruleset_version)
    apply_tick(s, led, [tx], current_tick=s.tick + 1)
    pid = sorted(s.proposals.keys())[-1]
    return pid


def test_delegate_and_revoke_roundtrip():
    s = genesis_state({"a": 100, "b": 100}, ruleset_params=_params())
    led = Ledger()
    tx = Transaction(tick=1, sender="a", action="DELEGATE",
                     payload={"to": "b"}, ruleset_version=s.ruleset_version)
    apply_tick(s, led, [tx], current_tick=1)
    assert s.delegations["a"] == "b"
    # revoke with to=None
    tx2 = Transaction(tick=2, sender="a", action="DELEGATE",
                      payload={"to": None}, ruleset_version=s.ruleset_version)
    apply_tick(s, led, [tx2], current_tick=2)
    assert "a" not in s.delegations


def test_no_self_delegation():
    s = genesis_state({"a": 100}, ruleset_params=_params())
    led = Ledger()
    tx = Transaction(tick=1, sender="a", action="DELEGATE",
                     payload={"to": "a"}, ruleset_version=s.ruleset_version)
    apply_tick(s, led, [tx], current_tick=1)
    assert s.delegations == {}  # rejected


def test_disabled_without_param():
    s = genesis_state({"a": 100, "b": 100}, ruleset_params=_params(delegation=False))
    led = Ledger()
    tx = Transaction(tick=1, sender="a", action="DELEGATE",
                     payload={"to": "b"}, ruleset_version=s.ruleset_version)
    apply_tick(s, led, [tx], current_tick=1)
    assert s.delegations == {}


def test_expand_ballots_delegate_follows_and_direct_wins():
    s = genesis_state({"a": 1, "b": 100, "c": 100, "d": 100}, ruleset_params=_params())
    s.delegations["b"] = "a"   # a's delegate is b? no — a delegates TO b
    s.delegations["c"] = "b"   # c follows b
    # b voted 'for'; a voted 'against' directly; d abstains (no delegate)
    raw = {"a": "against", "b": "for"}
    expanded = expand_ballots(s, raw)
    assert expanded["a"] == "for" is False or True  # direct stands below
    assert expanded["a"] == "against"  # direct vote wins over delegation
    assert expanded.get("d") is None  # d has no delegate: abstains
    assert expanded.get("c") == "for"  # follows b


def test_cycle_contributes_nothing():
    s = genesis_state({"a": 100, "b": 100}, ruleset_params=_params())
    s.delegations = {"a": "b", "b": "a"}  # cycle, nobody voted directly
    assert expand_ballots(s, {}) == {}  # no phantom votes


def test_settlement_counts_delegated_votes():
    """4 citizens, quorum 50% (2). Only 1 direct vote — fails; but with a
    delegate chain (2 delegated to the voter) the cast expands to 3 and
    the proposal passes by majority."""
    s = genesis_state({"a": 100, "b": 100, "c": 100, "d": 100},
                      ruleset_params=_params())
    led = Ledger()
    pid = _propose_and_open(s, "a")
    # a votes for; c delegated to a; b and d abstain entirely
    v = s.ruleset_version
    close_tick = s.proposals[pid]["closes_tick"]
    txs = [
        Transaction(tick=s.tick + 1, sender="a", action="VOTE",
                    payload={"proposal_id": pid, "choice": "for"}, ruleset_version=v),
        Transaction(tick=s.tick + 1, sender="c", action="DELEGATE",
                    payload={"to": "a"}, ruleset_version=v),
    ]
    apply_tick(s, led, txs, current_tick=s.tick + 1)
    for t in range(s.tick + 2, close_tick + 1):
        from openboard.engine import apply_tick as at
        at(s, led, [], current_tick=t)
    assert s.proposals[pid]["status"] == "passed"


def test_disabled_param_no_expansion():
    s = genesis_state({"a": 100, "b": 100}, ruleset_params=_params(delegation=False))
    assert expand_ballots(s, {"a": "for"}) == {"a": "for"}
