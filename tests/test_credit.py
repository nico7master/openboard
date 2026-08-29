"""A1 financial depth: the credit union (LOAN / REPAY / credit_phase).

Rules: loans MOVE credits (surplus pool -> borrower -> pool + fee), never
mint. Gated by the optional `credit` rule param; absent = disabled = old
worlds replay byte-identically.
"""
import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from openboard.engine import apply_tick, credit_phase  # noqa: E402
from openboard.errors import Reason  # noqa: E402
from openboard.ledger import Ledger, Transaction  # noqa: E402
from openboard.state import genesis_state  # noqa: E402


def credit_params() -> dict:
    from openboard.rules import DEFAULT_RULESET_PARAMS

    p = copy.deepcopy(DEFAULT_RULESET_PARAMS)
    p["triage_overrides"] = {}
    p["credit"] = {"enabled": True, "max_per_citizen": 1_000,
                   "term_ticks": 50, "fee_bp": 500}
    return p


def _loan(sender, tick, amount, version):
    return Transaction(tick=tick, sender=sender, action="LOAN",
                       payload={"amount": amount}, ruleset_version=version)


def _repay(sender, tick, amount, version):
    return Transaction(tick=tick, sender=sender, action="REPAY",
                       payload={"amount": amount}, ruleset_version=version)


def test_loan_moves_money_never_mints():
    s = genesis_state({"c1": 100, "c2": 100}, ruleset_params=credit_params())
    s.surplus_pool = 5_000
    led = Ledger()
    apply_tick(s, led, [_loan("c1", 1, s.ruleset_version and 300, s.ruleset_version)], current_tick=1)
    assert s.balances["c1"] == 400  # 100 + 300 loan
    assert s.surplus_pool == 4_700  # moved, not minted
    # invariant: loans move money; total stock unchanged
    assert sum(s.balances.values()) + s.surplus_pool == 200 + 5_000
    assert s.loans["c1"]["principal"] == 300
    assert s.loans["c1"]["due_tick"] == 51


def test_repay_with_fee_returns_to_pool():
    s = genesis_state({"c1": 100}, ruleset_params=credit_params())
    s.surplus_pool = 5_000
    led = Ledger()
    apply_tick(s, led, [_loan("c1", 1, 300, s.ruleset_version)], current_tick=1)
    assert s.balances["c1"] == 400 and s.surplus_pool == 4_700
    s.balances["c1"] += 400  # honest earnings arrive from elsewhere
    repay = Transaction(tick=10, sender="c1", action="REPAY",
                        payload={"amount": 315}, ruleset_version=s.ruleset_version)
    apply_tick(s, led, [repay], current_tick=10)
    assert "c1" not in s.loans  # fully closed
    assert s.surplus_pool == 4_700 + 315  # principal + 15 fee back to society
    repay_events = [e for e in s.applied if e.get("action") == "REPAY"]
    assert repay_events and repay_events[-1]["fee_part"] == 15


def test_cap_enforced():
    s = genesis_state({"c1": 100}, ruleset_params=credit_params())
    s.surplus_pool = 5_000
    led = Ledger()
    apply_tick(s, led, [], current_tick=1)
    big = _loan("c1", 1, 5_000, s.ruleset_version)  # cap is 1,000
    apply_tick(s, led, [big], current_tick=1)
    assert "c1" not in s.loans
    assert s.balances["c1"] == 100


def test_one_active_loan_per_citizen():
    s = genesis_state({"c1": 100}, ruleset_params=credit_params())
    s.surplus_pool = 5_000
    led = Ledger()
    apply_tick(s, led, [_loan("c1", 1, 100, s.ruleset_version)], current_tick=1)
    second = _loan("c1", 2, 100, s.ruleset_version)
    apply_tick(s, led, [second], current_tick=2)
    assert s.loans["c1"]["principal"] == 100  # second rejected
    assert s.balances["c1"] == 200  # only the first loan credited


def test_disabled_without_param():
    from openboard.rules import DEFAULT_RULESET_PARAMS
    p = copy.deepcopy(DEFAULT_RULESET_PARAMS)
    s = genesis_state({"c1": 100}, ruleset_params=p)
    s.surplus_pool = 5_000
    led = Ledger()
    tx = _loan("c1", 1, 100, s.ruleset_version)
    apply_tick(s, led, [tx], current_tick=1)
    assert s.loans == {}
    assert s.balances["c1"] == 100  # untouched


def test_overdue_loan_defaults_and_flags():
    s = genesis_state({"c1": 100}, ruleset_params=credit_params())
    s.surplus_pool = 5_000
    led = Ledger()
    apply_tick(s, led, [_loan("c1", 1, 300, s.ruleset_version)], current_tick=1)
    ev = credit_phase(s, 52, s.active_ruleset_params())  # term 50 ticks
    assert len(ev) == 1 and ev[0]["action"] == "LOAN_DEFAULT"
    assert s.loans["c1"]["defaulted"] is True
    assert any(f.get("kind") == "LOAN_DEFAULT" for f in s.flags)
    # defaulted borrower cannot repay (loan record is closed to them)
    repay = Transaction(tick=53, sender="c1", action="REPAY",
                        payload={"amount": 10}, ruleset_version=s.ruleset_version)
    apply_tick(s, led, [repay], current_tick=53)
    assert s.loans["c1"]["defaulted"] is True  # no partial repayment applied


def test_replay_deterministic_with_credit():
    import random

    from openboard.replay import record_history

    def build(seed):
        rng = random.Random(7)
        s = genesis_state({"c1": 100, "c2": 100}, ruleset_params=credit_params())
        s.surplus_pool = 5_000
        led = Ledger()
        for t in range(1, 6):
            txs = []
            if t == 1:
                txs.append(_loan("c1", t, 300, s.ruleset_version))
            if t == 5:
                txs.append(Transaction(tick=t, sender="c1", action="REPAY",
                                       payload={"amount": 315}, ruleset_version=s.ruleset_version))
            apply_tick(s, led, txs, current_tick=t)
        return s

    a, b = build(1), build(2)
    assert a.state_hash() == b.state_hash()
