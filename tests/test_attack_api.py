"""B2: Break-the-System API — start/act/score roundtrip; bad playbook
rejected; act-before-start is a clean 400. The world's responses flow
through the real Run.tick loop (bots + democracy + oversight)."""
import importlib.util
import sys
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "dashboard_server_attack", Path(__file__).resolve().parents[1] / "dashboard" / "server.py"
)
server = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(server)


def test_act_before_start_is_400(client=None):
    with server.app.test_client() as c:
        r = c.post("/api/attack/act").get_json()
        assert r["ok"] is False


def test_start_bad_playbook_400():
    with server.app.test_client() as c:
        r = c.post("/api/attack/start", json={"playbook": "nonsense"}).get_json()
        assert r["ok"] is False
        assert "playbook" in r["error"]


def test_start_act_score_roundtrip():
    with server.app.test_client() as c:
        st = c.post("/api/attack/start", json={"playbook": "hoarder"}).get_json()
        assert st["ok"] is True
        assert st["attacker"]
        act = c.post("/api/attack/act", json={"playbook": "hoarder"}).get_json()
        assert act["ok"] is True
        assert act["tick"] > st["score"]["tick"]
        assert "score" in act and act["score"]["invariant_ok"] is True
        sc = c.get("/api/attack/score").get_json()
        assert sc["ok"] is True
        assert sc["score"]["tick"] == act["tick"]


def test_wage_mint_roundtrip_flags_or_clean():
    with server.app.test_client() as c:
        st = c.post("/api/attack/start", json={"playbook": "wage_mint"}).get_json()
        assert st["ok"] is True
        act = c.post("/api/attack/act", json={"playbook": "wage_mint"}).get_json()
        assert act["ok"] is True
        assert act["score"]["invariant_ok"] is True
