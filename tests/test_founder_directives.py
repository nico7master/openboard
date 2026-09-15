"""Founder-directive tests (2026-09-16).

Bots are not smart voters and have no skin in the game: the SYSTEM
proposes and rebalances.
  1. Politicians default-approve non-constitutional proposals they have
     no stance on (ordinary rebalancing never stalls on an electorate).
  2. Constitutional matters (voting rules, council) NEVER get default
     votes — the 2/3 capture guard stays intact.
  3. Crises auto-balance: with crisis.auto_ratify, a shock-declared
     crisis ratifies without any citizen votes.
"""
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "dashboard"))

from openboard import crisis as C  # noqa: E402
from openboard.engine import apply_tick  # noqa: E402
from openboard.ledger import Ledger, Transaction  # noqa: E402
from openboard.politics import make_politician  # noqa: E402
from openboard.state import genesis_state  # noqa: E402


def _gov_params(**over):
    from server import Run  # noqa: E402

    params = dict(Run(seed=1).state.active_ruleset_params())
    params["governance"] = {
        "enabled": True,
        "vote_window_ticks": 3,
        "quorum_bp": 5_000,
        "trial_period_ticks": 10,
    }
    params.update(over)
    return params


def _cast(params):
    s = genesis_state({f"c{i}": 500 for i in range(1, 9)}, ruleset_params=params)
    led = Ledger()

    def idle(who, state, params, tick, rng):
        return []

    cast = [(f"c{i}", make_politician(idle, "pragmatist", window=10))
            for i in range(1, 9)]
    return s, led, cast


def _drive(s, led, cast, ticks):
    for t in range(1, ticks + 1):
        actions = []
        for name, fn in sorted(cast):
            actions.extend(fn(name, s, s.active_ruleset_params(), t,
                              random.Random(f"d{t}:{name}")))
        apply_tick(s, led, actions, current_tick=t)


def test_default_approve_passes_nonconstitutional_proposal():
    """A pragmatist files a dividend tweak (no stance) — the other
    politicians default-approve and it passes on plain majority."""
    params = _gov_params()
    s, led, cast = _cast(params)
    _drive(s, led, cast, 40)
    settled = [e for e in s.applied if e.get("action") == "PROPOSAL_SETTLED"]
    passed = [e for e in settled if e.get("result") == "passed"]
    assert passed, f"default-approve failed to pass any proposal: {settled[:3]}"
    assert not any(e.get("constitutional") for e in passed)


def test_default_approve_never_rides_constitutional():
    """A faction proposal to lower quorum to 0 must NOT pass via default
    votes: constitutional matters require explicit consent (2/3 of ALL)."""
    params = _gov_params()
    s, led, cast = _cast(params)
    # one pragmatist files a constitutional mutation directly
    from openboard.politics import build_proposal

    def mutate_quorum(base):
        g = dict(base.get("governance", {}))
        g["quorum_bp"] = 0
        base["governance"] = g
        return base

    # quorum: 4 of 8 must cast; default-approve would give 7 FOR easily
    # without the capture guard — this test pins the guard.
    tx = build_proposal("c1", 1, s, s.active_ruleset_params(), mutate_quorum)
    assert tx is not None
    apply_tick(s, led, [tx], current_tick=1)
    _drive(s, led, cast, 30)
    active = s.active_ruleset_params()
    assert active["governance"]["quorum_bp"] != 0, "capture via default votes!"
    settled = [e for e in s.applied if e.get("action") == "PROPOSAL_SETTLED"]
    assert any(e.get("constitutional") and e.get("result") == "failed"
               for e in settled), settled[-3:]


def test_auto_ratified_crisis_needs_no_votes():
    """With crisis.auto_ratify, a shock-declared crisis ratifies the same
    tick with zero citizen votes — the system auto-balances."""
    params = _gov_params()
    params["crisis"] = {"enabled": True, "auto_ratify": True, "max_ticks": 50}
    s = genesis_state({f"c{i}": 500 for i in range(1, 8)}, ruleset_params=params)
    led = Ledger()
    # simulate a severe shock: one citizen dies this tick -> auto-declare
    # + instant ratification (no CRISIS_VOTE transactions at all)
    s.balances.pop("c1")
    s.citizen_inventory.pop("c1", None)
    s.applied.append({"tick": 1, "action": "CITIZEN_DEATH", "citizen": "c1"})
    apply_tick(s, led, [], current_tick=1)
    c = s.crisis
    assert c and c.get("active") and c.get("ratified"), s.crisis
    assert c.get("votes_for", 0) == 0 and c.get("votes_against", 0) == 0
    starts = [e for e in s.applied if e.get("action") == "CRISIS_START"]
    assert starts and starts[-1].get("auto") is True


def test_legacy_crisis_still_needs_ratification():
    """Without auto_ratify (legacy worlds), unratified crises still expire
    at the window — replay safety of the founder directive."""
    params = _gov_params()
    params["crisis"] = {"enabled": True}
    s = genesis_state({f"c{i}": 500 for i in range(1, 8)}, ruleset_params=params)
    led = Ledger()
    s.balances.pop("c1")
    s.citizen_inventory.pop("c1", None)
    s.applied.append({"tick": 1, "action": "CITIZEN_DEATH", "citizen": "c1"})
    apply_tick(s, led, [], current_tick=1)
    assert s.crisis and s.crisis.get("active") and not s.crisis.get("ratified")
    # drive past the 100-tick window: expires unratified
    for t in range(2, 105):
        apply_tick(s, led, [], current_tick=t)
    end = [e for e in s.applied if e.get("action") == "CRISIS_END"]
    assert end and end[-1].get("reason") == "unratified"


def test_crisis_param_validation():
    """crisis param: strict keys, bool checks, bounded max_ticks."""
    from openboard.rules import Reason, validate_params

    def base(over=None):
        p = _gov_params()
        p.pop("crisis", None)
        if over:
            p.update(over)
        return p

    ok = dict(base(), crisis={"enabled": True, "auto_ratify": True,
                              "max_ticks": 600})
    assert validate_params(ok, None) is None
    probe = dict(base(), crisis={"enabled": True})
    assert validate_params(probe, None) is None
    bad_keys = dict(base(), crisis={"enabled": True, "wat": 1})
    assert validate_params(bad_keys, None) == Reason.INVALID_RULESET
    bad_ticks = dict(base(), crisis={"enabled": True, "max_ticks": 0})
    assert validate_params(bad_ticks, None) == Reason.INVALID_RULESET
    bad_bool = dict(base(), crisis={"enabled": True, "auto_ratify": "yes"})
    assert validate_params(bad_bool, None) == Reason.INVALID_RULESET
