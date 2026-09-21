"""D3 completion pin (2026-09-21 visual pass): the BOOT world ships
democracy ON — the exact path the player guide's quick start leads with
(python dashboard/server.py -> open browser) must give the founder's
design: vote token, reachable quorum, persuasion, not a legacy world
with an apology banner."""
import importlib.util
import json
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "dashboard_server_boot", Path(__file__).resolve().parents[1] / "dashboard" / "server.py"
)
server = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(server)


def test_boot_world_has_democracy_on():
    with server.app.test_client() as c:
        d = c.get("/api/civic").get_json()
        assert d["ok"] is True
        assert d["token_mode"] is True, "boot world must ship the vote token ON"
        # reachable quorum: 10% of citizens, not the legacy 50%
        assert d["quorum_needed"] <= max(1, d["citizens"] // 10 + 1), (
            f"quorum {d['quorum_needed']} of {d['citizens']} is the legacy 50% bar"
        )


def test_reset_default_matches_boot():
    with server.app.test_client() as c:
        r = c.post("/api/reset", json={}).get_json()
        assert r["ok"] is True
        d = c.get("/api/civic").get_json()
        assert d["token_mode"] is True
