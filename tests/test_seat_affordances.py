"""G-D2 (guide dogfood 2026-09-22): the player guide promises founding,
delegating, whistleblowing, and crisis voting — the engine supported all
four, but the seat surfaced none of them (and offered JOIN_COOP to citizens
who were already members, which the engine rejects with ALREADY_IN_COOP).

Contract: affordances mirror the engine's validators — every button the
seat shows must be submittable through /api/action and ACCEPTED by the
engine within its rule gates (empty flags -> no REPORT button; no crisis
-> no CRISIS_VOTE button).
"""
import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "dashboard_server_aff", Path(__file__).resolve().parents[1] / "dashboard" / "server.py"
)
server = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(server)


def _fresh(seed=42):
    server.RUN = server.Run(seed=seed, governance=True)
    return server.RUN


def _actions_for(citizen):
    with server.app.test_client() as c:
        return c.get(f"/api/seat?citizen={citizen}").get_json()["actions"]


def _types(actions):
    return [a["type"] for a in actions]


def test_member_gets_leave_not_join():
    run = _fresh(seed=5)
    who = next(n for n, b in run.bots.items() if b.get("coop"))
    types = _types(_actions_for(who))
    assert "JOIN_COOP" not in types, types
    assert "LEAVE_COOP" in types, types


def test_coopless_gets_join_and_found():
    run = _fresh(seed=5)
    # force a jobless citizen
    who = next(iter(sorted(run.state.balances.keys())))
    for cid, coop in list(run.state.coops.items()):
        if who in coop.get("members", ()):  # leave via engine-legal action
            run.bots.pop(who, None)
            run.claimed.add(who)
            run.queue_action(who, "LEAVE_COOP", {"coop_id": cid})
            run.tick()
            break
    actions = _actions_for(who)
    types = _types(actions)
    assert "JOIN_COOP" in types, types
    found = [a for a in actions if a["type"] == "FOUND_COOP"]
    assert found, types
    a = found[0]
    # the payload must satisfy the engine's validator: submit + tick + assert accepted
    run.queue_action(who, "FOUND_COOP", a["payload"])
    run.tick()
    evs = [e for e in run.state.applied if isinstance(e, dict)
           and e.get("sender") == who and e.get("action") == "FOUND_COOP"]
    assert evs, "FOUND_COOP affordance rejected by the engine"


def test_delegate_affordance_payload_accepted():
    run = _fresh(seed=5)
    who = sorted(run.state.balances.keys())[0]
    run.bots.pop(who, None); run.claimed.add(who)
    actions = _actions_for(who)
    dele = [a for a in actions if a["type"] == "DELEGATE"]
    assert dele, actions
    run.queue_action(who, "DELEGATE", dele[0]["payload"])
    run.tick()
    assert run.state.delegations.get(who), "DELEGATE affordance rejected"
    # revoke affordance then works too
    actions = _actions_for(who)
    rev = [a for a in actions if a["type"] == "DELEGATE" and a["payload"].get("to") is None]
    assert rev
    run.queue_action(who, "DELEGATE", {"to": None})
    run.tick()
    assert who not in run.state.delegations


def test_no_whistle_or_crisis_buttons_without_their_gates():
    run = _fresh(seed=5)
    who = sorted(run.state.balances.keys())[0]
    run.bots.pop(who, None); run.claimed.add(who)
    types = _types(_actions_for(who))
    unpaid = {(f.get("kind"), f.get("target")) for f in run.state.flags}
    if not unpaid:
        assert "REPORT" not in types
    cr = getattr(run.state, "crisis", None) or {}
    if not (cr.get("active") and not cr.get("ratified")):
        assert "CRISIS_VOTE" not in types


def test_crisis_vote_affordance_when_crisis_open():
    from openboard import crisis as _crisis
    run = _fresh(seed=5)
    who = sorted(run.state.balances.keys())[0]
    run.bots.pop(who, None); run.claimed.add(who)
    _crisis.declare_crisis(run.state, run.state.tick, "famine", "auto")
    types = _types(_actions_for(who))
    assert "CRISIS_VOTE" in types
    run.queue_action(who, "CRISIS_VOTE", {"in_favor": True})
    run.tick()
    assert who in (run.state.crisis.get("voters") or {})
