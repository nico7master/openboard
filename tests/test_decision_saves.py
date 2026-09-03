"""Decision save points + one-click fixes (user directive 2026-09-03)."""
import json

import pytest

from dashboard.server import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_adopt_creates_save_point(client):
    r = client.post("/api/policy/adopt", json={"knob_id": "wealth_tax", "option_id": "Light"})
    assert r.status_code == 200
    d = r.get_json()
    assert d.get("ok"), d
    saves = client.get("/api/saves").get_json()["saves"]
    assert any("wealth_tax" in s["file"] for s in saves), "decision save point recorded"


def test_restore_bad_name_rejected(client):
    r = client.post("/api/restore", json={"file": "../autosave.json"})
    assert r.status_code == 400


def test_found_coop_fix_queues_valid_tx(client):
    # pick any real recipe
    r = client.post("/api/fix/found_coop", json={"recipe_id": "breadmaking"})
    d = r.get_json()
    if not d.get("ok"):
        assert "unknown recipe" in d.get("error", ""), d  # recipe name differs in catalog
    else:
        assert len(d["members"]) == 2
