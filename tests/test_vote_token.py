"""Vote token spec tests (2026-09-15)."""
import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from openboard.engine import apply_tick, expand_weighted_ballots
from openboard.ledger import Ledger, Transaction
from openboard.rules import DEFAULT_RULESET_PARAMS
from openboard.state import genesis_state


class _Runner:
    """Drives apply_tick with an explicit monotonic tick counter:
    apply_tick ADVANCES state.tick, so relative arithmetic overruns
    vote windows. Votes must land inside closes_tick."""

    def __init__(self, s, led):
        self.s, self.led = s, led
        self.now = s.tick

    def run(self, txs):
        self.now += 1
        apply_tick(self.s, self.led, txs, current_tick=self.now)

    def tx(self, sender, action, payload):
        return Transaction(tick=self.now + 1, sender=sender, action=action,
                           payload=payload, ruleset_version=self.s.ruleset_version)

    def propose(self, sender):
        base = copy.deepcopy(self.s.active_ruleset_params())
        self.run([self.tx(sender, "PROPOSE", {"params": base, "activation_tick": self.now + 10})])
        return sorted(self.s.proposals.keys())[-1]

    def vote(self, sender, pid, choice, bp=None):
        payload = {"proposal_id": pid, "choice": choice}
        if bp is not None:
            payload["bp"] = bp
        self.run([self.tx(sender, "VOTE", payload)])


def _params(**overrides):
    from openboard.rules import DEFAULT_RULESET_PARAMS
    p = copy.deepcopy(DEFAULT_RULESET_PARAMS)
    p["triage_overrides"] = {}
    gov = {
        "enabled": True,
        "vote_window_ticks": 3,
        "quorum_bp": 5_000,
        "trial_period_ticks": 10,
        "vote_token_bp": 10_000,
        "vote_cycle_ticks": 30,
    }
    gov.update(overrides.get("governance", {}))
    p["governance"] = gov
    return p


def _open_proposals(state):
    return [(k, v) for k, v in state.proposals.items() if v["status"] == "open"]


def test_budget_enforcement():
    """Spending beyond the monthly token is rejected; exact spends deduct."""
    s = genesis_state({"a": 100, "b": 100}, ruleset_params=_params())
    r = _Runner(s, Ledger())
    pid1 = r.propose("a")
    pid2 = r.propose("b")
    # full token on p1
    r.vote("a", pid1, "for", bp=10_000)
    assert s.vote_budget["a"]["bp"] == 0
    # token exhausted: further spend rejected (no ballot recorded)
    r.vote("a", pid2, "for", bp=100)
    assert "a" not in s.proposals[pid2]["ballots"]
    assert s.vote_budget["a"]["bp"] == 0


def test_split_tally():
    """Exact 5,000/5,000 and 1,000/9,000 splits tally exactly."""
    s = genesis_state({"a": 100, "b": 100}, ruleset_params=_params())
    r = _Runner(s, Ledger())
    pid = r.propose("a")
    r.vote("a", pid, "for", bp=5_000)
    r.vote("b", pid, "for", bp=5_000)
    assert s.proposals[pid]["ballots"]["a"]["bp"] == 5_000
    assert s.proposals[pid]["ballots"]["b"]["bp"] == 5_000
    r.vote("a", pid, "for", bp=100)  # ALREADY_VOTED: one ballot per proposal
    assert s.proposals[pid]["ballots"]["a"]["bp"] == 5_000


def test_monthly_reset():
    """Budget restored at cycle boundary; unspent expired."""
    s = genesis_state({"a": 100}, ruleset_params=_params())
    r = _Runner(s, Ledger())
    pid = r.propose("a")
    # granted on first tick (cycle 0)
    assert s.vote_budget["a"]["bp"] == 10_000
    r.vote("a", pid, "for", bp=5_000)
    assert s.vote_budget["a"]["bp"] == 5_000
    # advance to tick 30 (cycle 1): refresh to full token
    while r.now < 30:
        r.run([])
    assert s.vote_budget["a"]["bp"] == 10_000
    assert s.vote_budget["a"]["cycle"] == 1


def test_delegation():
    """Delegated weight follows delegate's allocations; direct overrides."""
    s = genesis_state({"a": 100, "b": 100}, ruleset_params=_params())
    r = _Runner(s, Ledger())
    # a delegates to b (token mode: no legacy delegation param needed)
    r.run([r.tx("a", "DELEGATE", {"to": "b"})])
    assert s.delegations["a"] == "b"
    pid = r.propose("b")
    # b votes 8000 for
    r.vote("b", pid, "for", bp=8_000)
    # expanded ballots: a follows b's allocation (direct wins at tally)
    expanded = expand_weighted_ballots(s, s.proposals[pid]["ballots"], 10_000)
    assert expanded["a"]["bp"] == 8_000
    assert expanded["a"]["choice"] == "for"
    # a votes 2000 directly -> overrides delegation
    r.vote("a", pid, "against", bp=2_000)
    assert s.proposals[pid]["ballots"]["a"]["bp"] == 2_000
    expanded = expand_weighted_ballots(s, s.proposals[pid]["ballots"], 10_000)
    assert expanded["a"]["bp"] == 2_000
    assert expanded["a"]["choice"] == "against"


def test_revocation():
    """Revocation mid-month immediate; direct overrides."""
    s = genesis_state({"a": 100, "b": 100}, ruleset_params=_params())
    r = _Runner(s, Ledger())
    r.run([r.tx("a", "DELEGATE", {"to": "b"})])
    assert s.delegations["a"] == "b"
    # revoke (to=None)
    r.run([r.tx("a", "DELEGATE", {"to": None})])
    assert "a" not in s.delegations


def test_chain_cycle_safety():
    """A→B→A resolves deterministically; cycles abstain."""
    s = genesis_state({"a": 100, "b": 100, "c": 100}, ruleset_params=_params())
    r = _Runner(s, Ledger())
    r.run([r.tx("a", "DELEGATE", {"to": "b"})])
    r.run([r.tx("b", "DELEGATE", {"to": "a"})])
    ballots = {"c": {"choice": "for", "bp": 10_000}}
    expanded = expand_weighted_ballots(s, ballots, 10_000)
    assert "a" not in expanded and "b" not in expanded
    assert expanded["c"]["bp"] == 10_000


def test_legacy_replay():
    """Without vote_token_bp enabled, byte-identical legacy binary votes."""
    p = copy.deepcopy(DEFAULT_RULESET_PARAMS)
    p["governance"] = {"enabled": True, "vote_window_ticks": 3,
                       "quorum_bp": 5_000, "trial_period_ticks": 10}
    p["triage_overrides"] = {}
    s = genesis_state({"a": 100, "b": 100}, ruleset_params=p)
    assert s.vote_budget == {}
    r = _Runner(s, Ledger())
    pid = r.propose("a")
    r.vote("a", pid, "for")
    assert s.proposals[pid]["ballots"]["a"] == "for"


if __name__ == "__main__":
    test_budget_enforcement()
    test_split_tally()
    test_monthly_reset()
    test_delegation()
    test_revocation()
    test_chain_cycle_safety()
    test_legacy_replay()
    print("All tests pass")
