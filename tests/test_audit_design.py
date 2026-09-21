"""Audit 2026-09-20 package P-DESIGN: regression pins for the design-layer
findings D1-D9 (+C14) and spec-drift S1/S6/S7 doc fixes. All offline."""
import importlib.util
import json
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "dashboard_server_audit_design", Path(__file__).resolve().parents[1] / "dashboard" / "server.py"
)
server = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(server)


def test_d3_governance_on_by_default():
    """The flagship democracy ships ON (founder-approved flip)."""
    with server.app.test_client() as c:
        r = c.post("/api/reset", json={}).get_json()
        assert r["ok"] is True
        with server.RUN.lock:
            gov = server.RUN.state.active_ruleset_params().get("governance", {})
        assert bool(gov.get("enabled")) is True
        assert int(gov.get("vote_token_bp", 0)) > 0  # founder token ships too


def test_s1_research_ships_on_with_reserve_floor():
    """The Innovation Fund ships enabled, honoring the research-funding-fix
    contract: share taps only surplus ABOVE a reserve floor."""
    with server.app.test_client() as c:
        c.post("/api/reset", json={}).get_json()
        with server.RUN.lock:
            rc = server.RUN.state.active_ruleset_params().get("research", {})
        assert rc.get("enabled") is True
        assert int(rc.get("research_share_bp", 0)) > 0
        assert int(rc.get("reserve_floor", 0)) > 0


def test_d5_explain_plain_language():
    """The explainer turns ruleset deltas into sentences a voter can read."""
    cur = {"wealth_tax": {"rate_bp": 800}, "governance": {"enabled": True}}
    new = {"wealth_tax": {"rate_bp": 1_200}, "governance": {"enabled": True}}
    out = server.explain_proposal(cur, new)
    assert "wealth tax" in out.lower() and "8%" in out and "12%" in out
    out2 = server.explain_proposal(cur, {"governance": {"enabled": False}})
    assert "off" in out2.lower()
    assert server.explain_proposal(cur, dict(cur)) == "No rule changes (copy of the current rules)."


def test_d5_civic_and_seat_expose_explain():
    """Both voting surfaces carry the plain-language summary."""
    with server.app.test_client() as c:
        c.post("/api/reset", json={}).get_json()
        civic = c.get("/api/civic").get_json()
        assert "explain" in civic["proposals"][0] if civic["proposals"] else True
        seat = c.get("/api/seat").get_json()
        for pr in seat.get("open_proposals", []):
            assert "explain" in pr


def test_d6_reign_scoreboard_and_fairness_in_state():
    """/api/state carries the reign scoreboard and the fairness mission."""
    with server.app.test_client() as c:
        c.post("/api/reset", json={"scenario": "unequal"}).get_json()
        v = c.get("/api/state").get_json()
        reign = v.get("reign")
        assert reign and reign["ticks"] >= 1 and "laws_passed" in reign
        assert "invariant_ok" in reign
        f = v.get("fairness")
        assert f and "gini_start" in f and "achieved" in f
        assert v.get("scenario") == "unequal"


def test_d2_attack_style_validated():
    """Pacing style is validated; the playbook stays pinned (C3)."""
    with server.app.test_client() as c:
        c.post("/api/attack/start", json={"playbook": "hoarder", "player": "st9"}).get_json()
        bad = c.post("/api/attack/act", json={"player": "st9", "style": "nuke"}).get_json()
        assert bad["ok"] is False and "style" in bad["error"]
        ok = c.post("/api/attack/act", json={"player": "st9", "style": "bold"}).get_json()
        assert ok["ok"] is True
        assert ok["playbook"] == "hoarder"  # still pinned


def test_d4_d8_ui_marks_present():
    """The seat tab, mission banner and Mercury hook exist in the UI."""
    ui = (Path(server.__file__).parent / "static" / "index.html").read_text()
    assert 'Your Seat' in ui
    assert 'The mission' in ui
    assert 'Mercury serves here' in ui
    assert 'oversight closing in' in ui
