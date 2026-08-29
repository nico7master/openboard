"""A1: Citizen Seat exposes credit-union affordances when enabled, and
nothing credit-related when disabled."""
import copy
import importlib.util
import sys
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "dashboard_server_seat", Path(__file__).resolve().parents[1] / "dashboard" / "server.py"
)
server = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(server)

from openboard.engine import apply_tick
from openboard.ledger import Ledger, Transaction
from openboard.rules import RuleSetDoc


def _run_with_credit(credit=True):
    r = server.Run(seed=42)
    with r.lock:
        s = r.state
        cur = dict(s.active_ruleset_params())
        if credit:
            cur["credit"] = {"enabled": True, "max_per_citizen": 1_000,
                             "term_ticks": 50, "fee_bp": 500}
        else:
            cur.pop("credit", None)
        s.rulesets.append(RuleSetDoc(version=s.ruleset_version + 1,
                                     params=cur, activated_at=s.tick,
                                     change_tx_hash="test").to_dict())
        s.ruleset_version += 1
        s.surplus_pool = 2_000
    return r


def test_seat_offers_borrow_when_enabled():
    r = _run_with_credit(True)
    old, server.RUN = server.RUN, r
    try:
        with server.app.test_client() as c:
            resp = c.get("/api/seat").get_json()
    finally:
        server.RUN = old
    assert any(a["type"] == "LOAN" for a in resp["actions"])
    assert resp["loan"] is None  # no active loan yet


def test_seat_shows_repay_and_badge_with_active_loan():
    r = _run_with_credit(True)
    with r.lock:
        s = r.state
        who = sorted(s.balances.keys())[0]
        led = Ledger()
        tx = Transaction(tick=s.tick + 1, sender=who, action="LOAN",
                         payload={"amount": 300}, ruleset_version=s.ruleset_version)
        apply_tick(s, led, [tx], current_tick=s.tick + 1)
    old, server.RUN = server.RUN, r
    try:
        with server.app.test_client() as c:
            resp = c.get(f"/api/seat?citizen={who}").get_json()
    finally:
        server.RUN = old
    assert resp["loan"]["principal"] == 300
    assert resp["loan"]["owed"] == 315  # 300 + 5% fee
    assert any(a["type"] == "REPAY" for a in resp["actions"])


def test_seat_silent_when_credit_disabled():
    r = _run_with_credit(False)
    old, server.RUN = server.RUN, r
    try:
        with server.app.test_client() as c:
            resp = c.get("/api/seat").get_json()
    finally:
        server.RUN = old
    assert resp.get("loan") is None
    assert not any(a["type"] in ("LOAN", "REPAY") for a in resp["actions"])
