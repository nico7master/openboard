"""B2: Break-the-System API — start/act/score roundtrip; bad playbook
rejected; act-before-start is a clean 400. The world's responses flow
through the real Run.tick loop (bots + democracy + oversight)."""
import importlib.util
import json
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


def test_v2_start_includes_round_metadata():
    with server.app.test_client() as c:
        st = c.post("/api/attack/start",
                    json={"playbook": "hoarder", "player": "tester"}).get_json()
        assert st["ok"] is True
        assert st["round_ticks"] == 200
        assert st["player"] == "tester"


def test_v2_act_returns_verdict_shape():
    with server.app.test_client() as c:
        c.post("/api/attack/start", json={"playbook": "hoarder", "player": "vtester"})
        act = c.post("/api/attack/act", json={"playbook": "hoarder"}).get_json()
        assert act["ok"] is True
        v = act["verdict"]
        assert v["playbook"] == "hoarder"
        assert v["ticks_played"] >= 1
        assert v["outcome"] in ("round_in_progress", "stopped_by_system",
                                "survived_full_round")
        assert isinstance(v["damage"], int) and v["damage"] >= 0


def test_v2_leaderboard_endpoint_and_persistence(tmp_path, monkeypatch):
    lb = tmp_path / "attack_leaderboard.json"
    monkeypatch.setattr(server, "LEADERBOARD_PATH", lb)
    with server.app.test_client() as c:
        r = c.get("/api/attack/leaderboard").get_json()
        assert r["ok"] is True and r["board"] == []
        # record a finished round directly through the recorder
        entry = server._leaderboard_record("vtester", {
            "playbook": "hoarder", "damage": 1234, "flags_caused": 9,
            "worst_unmet_streak": 33, "ticks_played": 77,
            "outcome": "stopped_by_system",
        })
        assert entry["player"] == "vtester" and entry["damage"] == 1234
        board = server._leaderboard_load()
        assert board and board[0]["damage"] == 1234
        r = c.get("/api/attack/leaderboard").get_json()
        assert r["ok"] is True and r["board"][0]["player"] == "vtester"


def test_v2_full_round_survives_to_verdict():
    """A quiet-ish playbook round ends by tick budget or stop; verdict + board."""
    with server.app.test_client() as c:
        st = c.post("/api/attack/start",
                    json={"playbook": "wage_mint", "player": "roundtester"}).get_json()
        assert st["ok"] is True
        final = None
        for _ in range(210):
            act = c.post("/api/attack/act", json={"playbook": "wage_mint"}).get_json()
            assert act["ok"] is True
            if act["over"]:
                final = act
                break
        assert final is not None, "round should end within 210 ticks"
        v = final["verdict"]
        assert v["outcome"] in ("stopped_by_system", "survived_full_round")
        assert final["leaderboard_entry"]["player"] == "roundtester"
        # cleanup: remove the test entry so the real board stays clean
        board = [e for e in server._leaderboard_load() if e["player"] != "roundtester"]
        server.LEADERBOARD_PATH.write_text(json.dumps(board))
