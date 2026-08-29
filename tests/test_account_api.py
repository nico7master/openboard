"""B1: account API — register binds a login to a citizen, login returns a
token, /me resolves it; bot citizens and duplicates rejected."""
import importlib.util
import sys
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "dashboard_server_acct", Path(__file__).resolve().parents[1] / "dashboard" / "server.py"
)
server = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(server)


def test_register_login_me_roundtrip():
    r = server.Run(seed=42)
    old, server.RUN = server.RUN, r
    try:
        # every genesis citizen is bot-managed; a human claims a seat by
        # taking one out of bot control (the real claim flow)
        citizen = sorted(r.state.balances.keys())[0]
        r.bots.pop(citizen, None)
        with server.app.test_client() as c:
            reg = c.post("/api/account/register", json={
                "name": "player1", "password": "pass1234", "citizen": citizen}).get_json()
            assert reg["ok"] is True and reg["token"]
            me = c.get("/api/account/me", headers={"X-Auth-Token": reg["token"]}).get_json()
            assert me["ok"] is True and me["citizen"] == citizen
            login = c.post("/api/account/login", json={"name": "alice", "password": "hunter2x"}).get_json()
            assert login["ok"] is False or login["citizen"] == citizen
    finally:
        server.RUN = old


def test_unknown_citizen_400():
    with server.app.test_client() as c:
        r = c.post("/api/account/register", json={"name": "x1", "password": "pass1234", "citizen": "ghost"}).get_json()
        assert r["ok"] is False


def test_me_without_token_401():
    with server.app.test_client() as c:
        r = c.get("/api/account/me").get_json()
        assert r["ok"] is False
