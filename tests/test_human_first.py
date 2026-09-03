"""Human-first dashboard: advisor, availability board, direct-apply policy."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "dashboard"))

import pytest

from server import app


@pytest.fixture()
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_availability_shape(client):
    d = client.get("/api/availability").get_json()
    assert d["ok"] is True
    assert d["rows"]
    for r in d["rows"]:
        assert r["status"] in ("ok", "tight", "missing")
        assert isinstance(r["why"], str) and r["why"]


def test_advice_shape_and_content(client):
    d = client.get("/api/advice").get_json()
    assert d["ok"] is True
    for a in d["advice"]:
        assert a["problem"] and a["cause"] and a["action"]
        assert a["lever"] in ("found_coop", "supply_chain", "lab", "market")


def test_policy_adopt_direct(client):
    """One world: adopting a knob applies it via ledger RULE_CHANGE."""
    r = client.post("/api/policy/adopt",
                    json={"knob_id": "wealth_tax", "option_id": "Light"})
    d = r.get_json()
    assert d["ok"] is True
    assert d["adopted"] == "Light"


def test_policy_adopt_validates(client):
    r = client.post("/api/policy/adopt", json={})
    assert r.status_code == 400
    r = client.post("/api/policy/adopt",
                    json={"knob_id": "nope", "option_id": "x"})
    assert r.status_code == 400


def test_no_twin_run_endpoints(client):
    """The twin-world experiment endpoints are gone by design."""
    r = client.post("/api/policy/experiment/start", json={})
    assert r.status_code == 404


def test_chronicle_shape(client):
    d = client.get("/api/chronicle").get_json()
    assert d["ok"] is True
    assert isinstance(d["events"], list)
