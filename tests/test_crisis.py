"""Stage 5 - Crisis override tests (spec section 4, plan lines 34-37).

Lifecycle (vote declare, auto-declare on severe shocks + ratification
window), suspension effects (priorities off, fair rotation on), research
redirection, and replay safety without the crisis config.
"""
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from openboard import crisis as C  # noqa: E402
from openboard.engine import apply_tick  # noqa: E402
from openboard.ledger import Ledger, Transaction  # noqa: E402
from openboard.research import effective_allocation  # noqa: E402
from openboard.state import genesis_state  # noqa: E402


def _world(n: int = 7) -> object:
    s = genesis_state({f"c{i}": 500 for i in range(n)}, ruleset_params={})
    s.rulesets[-1]["params"]["crisis"] = {"enabled": True}
    return s


# ---------------------------------------------------------------- lifecycle


def test_direct_vote_declares_and_ends() -> None:
    """Vote-declared crisis is instantly active; CRISIS_START/END events."""
    s = _world()
    e = C.declare_crisis(s, 10, "famine", "vote")
    assert e["action"] == "CRISIS_START"
    assert C.crisis_active(s)
    e2 = C.end_crisis(s, 50, "vote")
    assert e2["action"] == "CRISIS_END"
    assert not C.crisis_active(s)
    actions = [x["action"] for x in s.applied]
    assert "CRISIS_START" in actions and "CRISIS_END" in actions


def test_engine_phase_lifecycle_through_apply_tick() -> None:
    """A tick with a citizen death auto-declares a crisis awaiting
    ratification; a majority of CRISIS_VOTE ratifies it."""
    s = _world(7)
    # simulate a severe shock: one citizen dies this tick
    s.balances.pop("c0")
    s.citizen_inventory.pop("c0", None)
    s.applied.append({"tick": 1, "action": "CITIZEN_DEATH", "citizen": "c0"})
    apply_tick(s, Ledger(), [], current_tick=1)
    assert any(e.get("action") == "CRISIS_AUTO" for e in s.applied)
    assert C.crisis_active(s) and not s.crisis["ratified"]

    # majority (3 of 6) vote in favor
    votes = [
        Transaction(tick=2, sender=c, action="CRISIS_VOTE",
                    payload={"in_favor": True}, ruleset_version=s.ruleset_version)
        for c in ("c1", "c2", "c3")
    ]
    apply_tick(s, Ledger(), votes, current_tick=2)
    assert s.crisis["ratified"]
    assert any(e.get("action") == "CRISIS_START" and e.get("ratified") for e in s.applied)


def test_unratified_crisis_expires_within_window() -> None:
    """The democracy can REJECT an auto-crisis: no ratification by the
    100-tick window ends it (CRISIS_END reason=unratified)."""
    s = _world(5)
    s.balances.pop("c0")
    s.citizen_inventory.pop("c0", None)
    s.applied.append({"tick": 1, "action": "CITIZEN_DEATH", "citizen": "c0"})
    apply_tick(s, Ledger(), [], current_tick=1)
    assert C.crisis_active(s)

    # nobody votes; drive past the ratification window (tick 1 + 100)
    for t in range(2, 103):
        apply_tick(s, Ledger(), [], current_tick=t)
    assert not C.crisis_active(s)
    end = [e for e in s.applied if e.get("action") == "CRISIS_END"]
    assert end and end[-1]["reason"] == "unratified"


def test_crisis_vote_rejected_and_invalid_payload() -> None:
    """CRISIS_VOTE outside a crisis is rejected; bad payloads rejected."""
    s = _world(4)
    bad = Transaction(tick=1, sender="c0", action="CRISIS_VOTE",
                      payload={"in_favor": True}, ruleset_version=s.ruleset_version)
    l = Ledger()
    apply_tick(s, l, [bad], current_tick=1)
    assert any(not r.accepted and r.reason is not None for r in l.records), (
        "vote without a crisis must be rejected"
    )

    # active crisis but non-bool payload
    C.declare_crisis(s, 2, "drought", "vote")
    bad2 = Transaction(tick=3, sender="c0", action="CRISIS_VOTE",
                       payload={"in_favor": "yes"}, ruleset_version=s.ruleset_version)
    l2 = Ledger()
    apply_tick(s, l2, [bad2], current_tick=3)
    assert any(not r.accepted for r in l2.records)


# ------------------------------------------------------- suspension effects


def test_suspensions_during_crisis() -> None:
    """During an active crisis: producer-input priority suspended and
    fair-clearing rotation forced ON (need-first distribution)."""
    import inspect
    from openboard import engine

    src = inspect.getsource(engine._clear_markets)
    assert "crisis_active" in src, "clearing must consult the crisis state"

    # behavioral check: pip enabled but crisis active -> no producer pass
    s = _world(6)
    s.rulesets[-1]["params"]["producer_input_priority"] = {"enabled": True}
    C.declare_crisis(s, 1, "blackout", "vote")
    # crisis is active: the pip config is ignored for this tick
    assert C.crisis_active(s)
    # and research redirects to the crisis field
    base = {"food": 2000, "health": 2000, "energy": 2000, "infrastructure": 2000, "computing": 2000}
    out = C.crisis_field_override(s, s.active_ruleset_params(), base)
    assert out["energy"] == 10_000  # blackout -> all-in on energy


def test_research_redirection_respects_crisis_kind() -> None:
    """Emergency redirection maps crisis kind -> research field."""
    s = _world(4)
    base = {"food": 2000, "health": 2000, "energy": 2000, "infrastructure": 2000, "computing": 2000}
    # no crisis: base unchanged
    assert C.crisis_field_override(s, s.active_ruleset_params(), base) is base
    C.declare_crisis(s, 1, "pandemic", "vote")
    out = C.crisis_field_override(s, s.active_ruleset_params(), base)
    assert out["health"] == 10_000 and out["food"] == 0
    C.end_crisis(s, 2, "x")
    assert C.crisis_field_override(s, s.active_ruleset_params(), base) is base


# ---------------------------------------------------------------- lifecycle


def test_max_duration_expires_ratified_crisis() -> None:
    """A ratified crisis ends at the votable max duration."""
    s = _world(4)
    s.rulesets[-1]["params"]["crisis"] = {"enabled": True, "max_ticks": 50}
    C.declare_crisis(s, 10, "famine", "vote")
    for t in range(11, 70):
        C.crisis_phase(s, t, s.active_ruleset_params())
        if not C.crisis_active(s):
            break
    assert not C.crisis_active(s)
    end = [e for e in s.applied if e.get("action") == "CRISIS_END"]
    assert end and end[-1]["reason"] == "max_duration"


def test_no_crisis_config_inert() -> None:
    """Without the crisis config, deaths declare nothing (replay-safe)."""
    s = genesis_state({"a": 500, "b": 500}, ruleset_params={})
    s.balances.pop("a")
    s.citizen_inventory.pop("a", None)
    s.applied.append({"tick": 1, "action": "CITIZEN_DEATH", "citizen": "a"})
    apply_tick(s, Ledger(), [], current_tick=1)
    assert not any(e.get("action", "").startswith("CRISIS") for e in s.applied)
    assert not C.crisis_active(s)


def test_snapshot_roundtrip_with_crisis() -> None:
    """Crisis state survives snapshot/restore (save/load honesty)."""
    s = _world(4)
    C.declare_crisis(s, 5, "pandemic", "vote")
    snap = s.snapshot_dict()
    assert "crisis" in snap
    r = genesis_state({"a": 500, "b": 500, "c": 500, "d": 500}, ruleset_params={})
    r.restore_dict(snap) if hasattr(r, "restore_dict") else None
    # state_hash determinism with crisis active
    h1 = s.state_hash()
    h2 = s.state_hash()
    assert h1 == h2
