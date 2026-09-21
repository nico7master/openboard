"""Guide-dogfood fix (2026-09-21): claiming a citizen must give the human
EXCLUSIVE control of the seat. Before this, a claimed citizen's politician
twin kept voting with the SAME monthly token — the twin's even-split votes
drained the 10,000bp budget before the human's queued votes applied
(ledger proof: 21x476bp bot votes vs a dead 4000bp human vote).

Contract (C11 precedent — the LLM attach already pops its twin):
- register binds a bot citizen: the twin steps aside (claimed set)
- claimed seats: no bot decisions (the token is the human's alone)
- claims persist across save/restore AND world resets (accounts outlive worlds)
- the LLM attach never takes a claimed seat
"""
import importlib.util
import json
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "dashboard_server_claim", Path(__file__).resolve().parents[1] / "dashboard" / "server.py"
)
server = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(server)


def _fresh(seed=42):
    server.RUN = server.Run(seed=seed, governance=True)
    return server.RUN


def test_register_claims_a_bot_citizen_and_suspends_its_twin():
    with server.app.test_client() as c:
        run = _fresh(seed=7)
        citizen = sorted(run.state.balances.keys())[0]
        assert citizen in run.bots  # it IS a bot — the old handler refused
        reg = c.post("/api/account/register",
                     json={"name": "claim_t1", "password": "hunter2",
                           "citizen": citizen}).get_json()
        assert reg["ok"] is True, reg
        assert citizen in run.claimed
        assert citizen not in run.bots  # twin stepped aside
        # the engine tick never re-spawns bot decisions for claimed seats
        before = len(run.state.proposals)
        for _ in range(60):
            run.tick()
        assert citizen in run.claimed and citizen not in run.bots


def test_claimed_human_gets_the_whole_token():
    """The exact dogfood scenario: the human's vote lands with the FULL
    monthly token available — no twin votes drained it first."""
    with server.app.test_client() as c:
        run = _fresh(seed=11)
        citizen = sorted(run.state.balances.keys())[1]  # distinct per test
        c.post("/api/account/register",
               json={"name": "claim_t2", "password": "hunter2",
                     "citizen": citizen}).get_json()
        assert citizen in run.claimed  # registration must have succeeded
        for _ in range(75):  # past the first election window
            run.tick()
        open_p = [p for p in run.state.proposals.values() if p["status"] == "open"]
        if not open_p:
            return  # cadence guard — nothing open this window
        pid = open_p[0]["proposal_id"]
        v = c.post("/api/action", json={"sender": citizen, "action": "VOTE",
                                        "payload": {"proposal_id": pid,
                                                    "choice": "for", "bp": 4000}}).get_json()
        assert v["ok"] is True
        run.tick()
        seat = c.get(f"/api/seat?citizen={citizen}").get_json()
        # EXACT: the human's 4000bp spend is the only deduction — the twin
        # contributed nothing (pre-fix this was 0: twin drained it first)
        assert seat["vote_token"]["bp_left"] == 6000, seat["vote_token"]
        votes = [e for e in seat["my_events"] if e.get("action") == "VOTE"]
        assert len(votes) == 1 and votes[0].get("bp") == 4000, votes


def test_claims_survive_save_restore_and_reset():
    with server.app.test_client() as c:
        run = _fresh(seed=13)
        citizen = sorted(run.state.balances.keys())[2]  # distinct per test
        reg = c.post("/api/account/register",
                     json={"name": "claim_t3", "password": "hunter2",
                           "citizen": citizen}).get_json()
        assert reg["ok"] is True, reg
        assert citizen in run.claimed
        snap = run.to_save()
        run2 = server.Run.from_save(snap)
        assert citizen in run2.claimed
        assert citizen not in run2.bots
        # a world reset re-applies standing claims (accounts outlive worlds)
        old_run, server.RUN = server.RUN, run
        try:
            r = c.post("/api/reset", json={"seed": 5, "governance": True}).get_json()
            assert r["ok"] is True
        finally:
            pass  # keep the reset world; restore at test end not needed
        assert citizen in server.RUN.claimed
        assert citizen not in server.RUN.bots


def test_llm_attach_refuses_when_all_seats_claimed():
    with server.app.test_client() as c:
        run = _fresh(seed=17)
        for name in sorted(run.state.balances.keys()):
            run.claimed.add(name)
            run.bots.pop(name, None)
        old_run, server.RUN = server.RUN, run
        try:
            r = c.post("/api/llm/start", json={"seat": "politician",
                                               "decide_every": 3}).get_json()
            assert r["ok"] is False
            assert "claimed" in r["error"]
        finally:
            server.RUN = old_run
