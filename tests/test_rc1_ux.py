"""RC1 UX wiring (2026-09-19): founder-design governance defaults in live
runs, the Civic Board API, and the live LLM politician lifecycle — all
offline (fake client, no network).

Determinism discipline: LLM decisions are ledger inputs; replays stay exact.
The survival gates stay bot-only.
"""
import copy
import importlib.util
import json
import time
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "dashboard_server_ux", Path(__file__).resolve().parents[1] / "dashboard" / "server.py"
)
server = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(server)


def _gov_world():
    return server.Run(seed=99, governance=True)


def test_run_ships_founder_governance_trio():
    """Governance worlds launch with token + persuasion + reachable quorum."""
    g = _gov_world()
    gov = g.state.rulesets[-1]["params"]["governance"]
    assert gov["vote_token_bp"] == 10_000
    assert gov["vote_cycle_ticks"] == 30
    assert gov["persuasion"] is True
    assert gov["quorum_bp"] == 1_000  # reachable by the political cast
    assert gov["enabled"] is True


def test_run_legacy_world_stays_binary():
    """Non-governance worlds keep governance DISABLED (replay safety).
    rules.py ships vote_token_bp=10_000 as a default param value, but it is
    inert while enabled=False — the engine rejects every vote with
    GOVERNANCE_DISABLED before the bp contract is even consulted."""
    from openboard import Ledger, Transaction, apply_tick
    r = server.Run(seed=1, governance=False)
    gov = r.state.active_ruleset_params().get("governance", {})
    assert gov.get("enabled", False) is False
    s = r.state
    led = Ledger()
    apply_tick(s, led, [Transaction(tick=s.tick + 1, sender="worker_a",
                                    action="VOTE",
                                    payload={"proposal_id": "p", "choice": "for",
                                             "bp": 100},
                                    ruleset_version=s.ruleset_version)],
               current_tick=s.tick + 1)
    assert led.records[-1].reason == "GOVERNANCE_DISABLED"


def test_human_vote_action_carries_bp():
    """An open proposal must produce a seat VOTE affordance WITH bp —
    token-mode validation requires exact keys {proposal_id, choice, bp}.
    This was the silent human-vote killer (INVALID_PAYLOAD) before the fix."""
    from openboard.ledger import Transaction
    g = _gov_world()
    base = copy.deepcopy(g.state.active_ruleset_params())
    # file a REAL change — the NO_OP_PROPOSAL guard rejects identical params
    base["transfer_limit"] = (base.get("transfer_limit") or 0) + 1
    g.pending.append(Transaction(
        tick=g.state.tick + 1, sender="worker_a", action="PROPOSE",
        payload={"params": base, "activation_tick": g.state.tick + 10},
        ruleset_version=g.state.ruleset_version))
    g.tick()  # bots decide first, then pending merges — nobody voted yet
    server.RUN = g
    with server.app.test_client() as c:
        d = c.get("/api/seat?citizen=baker_a").get_json()
    votes = [a for a in d.get("actions", []) if a.get("type") == "VOTE"]
    assert votes, "an open proposal must produce a VOTE affordance"
    for a in votes:
        assert a["payload"].get("bp") == 10_000, "human VOTE must carry the token bp"


def test_civic_api_governance_world():
    """Civic Board endpoint returns the full shape on a token world."""
    server.RUN = _gov_world()
    with server.app.test_client() as c:
        d = c.get("/api/civic").get_json()
    assert d["ok"] is True
    assert d["token_mode"] is True
    assert d["vote_cycle_ticks"] == 30
    assert d["quorum_needed"] >= 1
    assert isinstance(d["proposals"], list)
    assert isinstance(d["events"], list)
    assert isinstance(d["trust"], dict)
    assert d["citizens"] >= 1


def test_civic_api_legacy_world_flags_no_token():
    """Legacy worlds must NOT claim token mode (enabled AND bp>0)."""
    server.RUN = server.Run(seed=1, governance=False)
    with server.app.test_client() as c:
        d = c.get("/api/civic").get_json()
    assert d["ok"] is True
    assert d["token_mode"] is False


def test_llm_start_unknown_seat_400():
    server.RUN = _gov_world()
    with server.app.test_client() as c:
        d = c.post("/api/llm/start", json={"seat": "nonsense"}).get_json()
    assert d["ok"] is False
    assert "seat" in d["error"]


def test_llm_start_needs_governance_world():
    """The seat's contract is token-mode votes; attaching to a legacy world
    would silently silence it (bp rejected as an extra key)."""
    server.RUN = server.Run(seed=1, governance=False)
    with server.app.test_client() as c:
        d = c.post("/api/llm/start", json={"seat": "politician"}).get_json()
    assert d["ok"] is False
    assert "governance" in d["error"]


def test_llm_lifecycle_fake_client():
    """Attach → daemon consults the (fake) model, fills accounting and the
    watch-me-think fields → stop clears the flag. NO network."""
    g = _gov_world()
    server.RUN = g
    calls = {"n": 0}

    def fake_call_factory():
        def call(_prompt):
            calls["n"] += 1
            return json.dumps({"reasoning": "fake deliberation", "actions": []})
        call.usage = [{"prompt_tokens": 100, "completion_tokens": 10,
                       "total_tokens": 110, "cost_usd": 0.0}]
        return call

    import openboard.llm_politician as lp
    orig = lp.politician_client
    lp.politician_client = fake_call_factory  # daemon imports at thread start
    try:
        with server.app.test_client() as c:
            st = c.post("/api/llm/start",
                        json={"seat": "politician", "decide_every": 1}).get_json()
            assert st["ok"] is True
            who = st["who"]
            assert who and who not in g.bots  # bot twin popped
            status = c.get("/api/llm/status").get_json()
            assert status["running"] is True and status["who"] == who
            # world must run for the seat to act
            g.autoplay["running"] = True
            deadline = time.time() + 10
            while calls["n"] == 0 and time.time() < deadline:
                time.sleep(0.05)
            assert calls["n"] >= 1, "daemon never consulted the model"
            deadline = time.time() + 5
            while not server._LLM["last_thought"] and time.time() < deadline:
                time.sleep(0.05)
            assert "fake deliberation" in server._LLM["last_thought"]
            acc = server._LLM["accounting"]
            assert acc["llm_calls"] >= 1 and acc["total_tokens"] >= 110
            stop = c.post("/api/llm/stop").get_json()
            assert stop["ok"] is True
            assert server._LLM["running"] is False
    finally:
        lp.politician_client = orig
        server._LLM["running"] = False


def test_llm_reset_clears_running_flag():
    """A fresh world clears the stale 'running' seat flag (daemon self-exits
    via its RUN-is-game check)."""
    server.RUN = _gov_world()
    server._LLM["running"] = True
    with server.app.test_client() as c:
        d = c.post("/api/reset", json={"governance": True, "seed": 1}).get_json()
    assert d["ok"] is True
    assert server._LLM["running"] is False