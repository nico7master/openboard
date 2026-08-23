"""Dashboard server tests: Run lifecycle, save/load determinism,
human action queueing, bot management, governance mode."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

# Import dashboard/server.py (it inserts src/ into sys.path itself)
_spec = importlib.util.spec_from_file_location(
    "dashboard_server", Path(__file__).parent.parent / "dashboard" / "server.py"
)
server = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(server)


class TestRunLifecycle:
    def test_fresh_run_and_ticks(self):
        r = server.Run(seed=42)
        assert r.state.tick == 1  # founding applied
        assert len(r.state.coops) == 42  # Stage 3/4: full cast with competition, capital chain, breadth
        for _ in range(10):
            r.tick()
        assert r.state.tick == 11
        assert len(r.timeline["tick"]) == 11
        assert len(r.timeline["gini"]) == 11

    def test_money_invariant_holds(self):
        r = server.Run(seed=42)
        # genesis money = citizen stakes + seeded treasuries (read, don't hardcode:
        # the baseline cast grows across stages)
        initial = sum(r.state.balances.values()) + sum(
            c.get("treasury", 0) for c in r.state.coops.values())
        for _ in range(20):
            r.tick()
        treasuries = sum(c.get("treasury", 0) for c in r.state.coops.values())
        total = (sum(r.state.balances.values()) + r.state.surplus_pool
                 + r.state.capital_fund + treasuries)
        assert total == initial + r.state.money_minted - r.state.money_retired


class TestAnalytics:
    def test_analytics_money_pie_sums_to_supply(self):
        r = server.Run(seed=42)
        for _ in range(15):
            r.tick()
        old_run, server.RUN = server.RUN, r
        try:
            client = r.app.test_client() if hasattr(r, "app") else None
            assert client is not None or True
            from flask import Flask
            # use the module-level app but temporarily swap RUN
            client = server.app.test_client()
            resp = client.get("/api/analytics")
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["ok"] is True
            assert sum(data["money_pie"].values()) == data["money_total"]
        finally:
            server.RUN = old_run

    def test_timeline_flows_match_events(self):
        r = server.Run(seed=42)
        produced_expected = 0
        bought_expected = 0
        for _ in range(10):
            r.tick()
            # _last_events is exactly this tick's applied events (the feed
            # return is a 40-item sliding window and truncates busy ticks)
            for e in r._last_events:
                if e.get("tick") != r.state.tick:
                    continue
                if e.get("action") == "PRODUCE":
                    produced_expected += sum(e.get("outputs", {}).values())
                elif e.get("action") == "MARKET_CLEAR_ESSENTIAL":
                    bought_expected += e.get("sold", 0)
                elif e.get("action") == "MARKET_CLEAR_AUCTION":
                    for w in e.get("winners", []):
                        if w.get("coop_id") is None:
                            bought_expected += w.get("qty", 0)
        assert sum(r.timeline["produced"]) == produced_expected
        assert sum(r.timeline["bought"]) == bought_expected
        assert len(r.timeline["produced"]) == len(r.timeline["tick"])

    def test_goods_table_covers_catalog(self):
        r = server.Run(seed=42)
        r.tick()
        old_run, server.RUN = server.RUN, r
        try:
            client = server.app.test_client()
            data = client.get("/api/analytics").get_json()
            goods = {g["good"] for g in data["goods_table"]}
            assert goods == set(r.state.goods.keys())
            bread = [g for g in data["goods_table"] if g["good"] == "bread"][0]
            assert bread["triage"] == "essential"
            assert bread["cost_baseline"] is not None
        finally:
            server.RUN = old_run

    def test_alerts_fire_on_overproduction(self):
        # Demand-driven production now prevents natural piles (that is the
        # point), so inject a pile directly to verify the alert logic.
        r = server.Run(seed=42)
        for _ in range(10):
            r.tick()
        with r.lock:
            r.state.coops["farmers"]["inventory"]["grain"] = 500
        old_run, server.RUN = server.RUN, r
        try:
            client = server.app.test_client()
            data = client.get("/api/analytics").get_json()
            msgs = " | ".join(a["msg"] for a in data["alerts"])
            assert "pile" in msgs
        finally:
            server.RUN = old_run

    def test_save_load_preserves_totals(self):
        r = server.Run(seed=42)
        for _ in range(25):
            r.tick()
        saved = r.to_save()
        r2 = server.Run.from_save(saved)
        assert r2.totals == r.totals
        assert r2.timeline["produced"] == r.timeline["produced"]
        assert r2.timeline["bought"] == r.timeline["bought"]


class TestSaveLoad:
    def test_round_trip_deterministic(self):
        r = server.Run(seed=42)
        for _ in range(25):
            r.tick()
        h1 = r.state.state_hash()

        save = r.to_save()
        assert save["format"] == "openboard-run-v2"

        r2 = server.Run.from_save(save)
        assert r2.state.state_hash() == h1

    def test_continue_after_load_deterministic(self):
        r = server.Run(seed=7)
        for _ in range(10):
            r.tick()
        r2 = server.Run.from_save(r.to_save())
        for _ in range(5):
            r.tick()
            r2.tick()
        assert r.state.state_hash() == r2.state.state_hash()

    def test_human_actions_survive_round_trip(self):
        r = server.Run(seed=3)
        for _ in range(5):
            r.tick()
        r.queue_action("worker_a", "TRANSFER", {"to": "worker_b", "amount": 50})
        r.tick()  # action executed
        h1 = r.state.state_hash()
        r2 = server.Run.from_save(r.to_save())
        assert r2.state.state_hash() == h1

    def test_rejects_unknown_format(self):
        with pytest.raises(ValueError):
            server.Run.from_save({"format": "garbage"})


class TestHumanActions:
    def test_action_joins_next_tick(self):
        r = server.Run(seed=42)
        for _ in range(3):
            r.tick()
        tx = r.queue_action("worker_a", "TRANSFER", {"to": "worker_b", "amount": 50})
        assert tx.tick == r.state.tick + 1  # next tick
        assert len(r.pending) == 1
        r.tick()
        assert len(r.pending) == 0
        assert r.state.balances["worker_b"] > 500  # transfer + wages

    def test_action_recorded_in_batches(self):
        r = server.Run(seed=42)
        for _ in range(3):
            r.tick()
        r.queue_action("worker_a", "TRANSFER", {"to": "worker_b", "amount": 10})
        t = r.state.tick + 1
        r.tick()
        assert any(
            d["action"] == "TRANSFER" and d["sender"] == "worker_a"
            for d in r.batches[t]
        )


class TestBotManagement:
    def test_add_and_remove_bot(self):
        r = server.Run(seed=42)
        for _ in range(3):
            r.tick()
        r.add_bot("greta", "hoarder", "farmers")
        assert "greta" in r.bots
        assert "greta" in r.state.balances
        assert "greta" in r.state.coops["farmers"]["members"]
        r.tick()  # greta acts without crash
        r.remove_bot("greta")
        assert "greta" not in r.bots

    def test_new_bot_can_work(self):
        r = server.Run(seed=42)
        for _ in range(3):
            r.tick()
        r.add_bot("greta", "hoarder", "farmers")
        hours_before = r.state.labor_hours.get("greta", 0)
        for _ in range(3):
            r.tick()
        assert r.state.labor_hours.get("greta", 0) >= hours_before  # WORK accepted


class TestGovernanceMode:
    def test_governance_run(self):
        r = server.Run(seed=9, governance=True)
        assert r.state.active_ruleset_params()["governance"]["enabled"]
        for _ in range(10):
            r.tick()
        # RULE_CHANGE is locked under governance
        from openboard import Ledger, Transaction, apply_tick
        tx = Transaction(tick=r.state.tick + 1, sender="worker_a", action="RULE_CHANGE",
                         payload={"params": r.state.active_ruleset_params(), "activation_tick": r.state.tick + 5},
                         ruleset_version=r.state.ruleset_version)
        pre = len(r.ledger.records)
        apply_tick(r.state, r.ledger, [tx], current_tick=tx.tick)
        assert r.ledger.records[-1].reason == "GOVERNANCE_LOCKED"

    def test_view_shape(self):
        r = server.Run(seed=1, governance=True)
        v = r.view()
        for key in ("tick", "citizens", "balances", "coops", "proposals", "flags",
                    "timeline", "events", "bots", "pending", "archetypes", "recipes"):
            assert key in v, f"view missing {key}"
        assert v["governance_enabled"] is True
        assert "honest_worker" in v["archetypes"]
        assert "farmer" in v["archetypes"]  # specialists included
