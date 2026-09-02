"""Human-first redesign: async policy experiments + chronicle endpoint."""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "dashboard"))

import pytest

from server import app


@pytest.fixture()
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_experiment_start_returns_job(client):
    r = client.post(
        "/api/policy/experiment/start",
        json={"knob_id": "wealth_tax", "option_id": "Light", "ticks": 10},
    )
    assert r.status_code == 200
    d = r.get_json()
    assert d["ok"] is True
    assert d["job_id"].startswith("exp_")


def test_experiment_start_validates(client):
    r = client.post("/api/policy/experiment/start", json={})
    assert r.status_code == 400


def test_experiment_result_unknown_job(client):
    r = client.get("/api/policy/experiment/result?job_id=nope")
    assert r.status_code == 404


def test_experiment_job_completes(client):
    r = client.post(
        "/api/policy/experiment/start",
        json={"knob_id": "wealth_tax", "option_id": "Heavy", "ticks": 10},
    )
    job = r.get_json()["job_id"]
    for _ in range(120):
        d = client.get("/api/policy/experiment/result?job_id=" + job).get_json()
        if d["status"] == "done":
            assert d["result"]["rows"]
            return
        if d["status"] == "error":
            pytest.fail(d["error"])
        time.sleep(1)
    pytest.fail("experiment did not finish in time")


def test_chronicle_shape(client):
    d = client.get("/api/chronicle").get_json()
    assert d["ok"] is True
    assert isinstance(d["events"], list)
    assert d["now"] >= 1
    for ev in d["events"]:
        assert "day" in ev and "text" in ev and "icon" in ev
