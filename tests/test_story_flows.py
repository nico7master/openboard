"""D9: story + flows endpoints — plain-language cards severity-classified,
flow volumes reconcile with real events, shapes stable."""
import importlib.util
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "dashboard"))

from openboard.story import build_story
from openboard.flows import build_flows


def _run():
    spec = importlib.util.spec_from_file_location(
        "ds_story", Path(__file__).resolve().parents[1] / "dashboard" / "server.py"
    )
    server = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(server)
    return server.Run(seed=42)


def test_story_endpoint_shape():
    r = _run()
    story = build_story(r.state, r.timeline)
    assert story["tick"] == r.state.tick
    assert len(story["cards"]) >= 5
    for card in story["cards"]:
        assert card["icon"] and card["sentence"] and card["severity"] in {"good", "watch", "bad", "info"}


def test_story_severity_ordering():
    r = _run()
    story = build_story(r.state, r.timeline)
    order = {"bad": 0, "watch": 1, "info": 2, "good": 3}
    sevs = [order[c["severity"]] for c in story["cards"]]
    assert sevs == sorted(sevs)


def test_shortage_card_detects_unmet():
    r = _run()
    s = r.state
    for c in s.balances:
        s.unmet_needs[c] = {"bread": 25}
    story = build_story(s, r.timeline)
    card = next(c for c in story["cards"] if c["id"] == "shortage")
    assert card["severity"] == "bad"
    assert "bread" in card["sentence"]


def test_shock_card_when_active():
    r = _run()
    r.state.active_shocks = [{"kind": "pandemic", "intensity": 5, "until_tick": r.state.tick + 10}]
    story = build_story(r.state, r.timeline)
    assert any(c["id"] == "shock" for c in story["cards"])


def test_flows_reconcile_with_production():
    """Nodes' produced totals must match real PRODUCE events in the window."""
    r = _run()
    flows = build_flows(r)
    assert flows["tick"] == r.state.tick
    assert len(flows["nodes"]) == len(r.state.coops)
    produced_sum = sum(n["produced"] for n in flows["nodes"])
    real = 0
    for t in range(max(r.state.tick - 4, 1), r.state.tick + 1):
        for ev in r.batches.get(t, []):
            if ev.get("action") == "PRODUCE":
                real += sum((ev.get("outputs") or {}).values())
    assert produced_sum == real


def test_flows_edges_reference_real_coops():
    r = _run()
    flows = build_flows(r)
    ids = {n["id"] for n in flows["nodes"]}
    for e in flows["edges"]:
        assert e["from"] in ids and e["to"] in ids


def test_flows_population_ring():
    r = _run()
    ring = build_flows(r)["population"]
    assert ring["total"] == len(r.state.balances)
    assert 0 <= ring["met_share"] <= 100
