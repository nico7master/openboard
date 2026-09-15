"""Source-model completion tests (spec 2026-09-15 §B): whistleblower
bounty + periodic public audit."""
import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from openboard.engine import apply_tick
from openboard.ledger import Ledger, Transaction
from openboard.rules import DEFAULT_RULESET_PARAMS
from openboard.state import genesis_state


class _Runner:
    """Drives apply_tick with an explicit monotonic tick counter."""

    def __init__(self, s, led):
        self.s, self.led = s, led
        self.now = s.tick

    def run(self, txs):
        self.now += 1
        apply_tick(self.s, self.led, txs, current_tick=self.now)

    def tx(self, sender, action, payload):
        return Transaction(tick=self.now + 1, sender=sender, action=action,
                           payload=payload, ruleset_version=self.s.ruleset_version)


def _world(params=None, n=3):
    p = copy.deepcopy(DEFAULT_RULESET_PARAMS)
    # scarcity default is ON from spec §A; keep the whistleblower tests
    # independent of premium dynamics by disabling it explicitly.
    p["scarcity_pricing"] = {"enabled": False, "max_markup_bp": 2_500,
                             "step_bp": 500, "decay_bp": 250}
    if params:
        p.update(params)
    s = genesis_state({f"c{i}": 100_000 for i in range(n)}, ruleset_params=p)
    return s, Ledger()


def _plant_hoard_flag(s, tick=1):
    s.flags.append({"tick": tick, "kind": "HOARD", "target": "c2",
                    "good": "bread", "held": 100, "threshold": 50})


def test_report_disabled_by_default():
    s, led = _world()
    _plant_hoard_flag(s)
    r = _Runner(s, led)
    r.run([r.tx("c0", "REPORT", {"kind": "HOARD", "target": "c2"})])
    rec = led.records[-1]
    assert not rec.accepted
    assert rec.reason == "REPORT_DISABLED"
    assert not any(e.get("action") == "WHISTLEBLOWER_PAID" for e in s.applied)


def test_first_report_pays_bounty_once():
    wb = {"enabled": True, "reward_credits": 100, "max_per_tick": 10}
    s, led = _world({"whistleblower": wb})
    _plant_hoard_flag(s)
    s.surplus_pool = 10_000  # bounties are paid from the pool; genesis starts at 0
    pool0 = s.surplus_pool
    bal0 = s.balances["c0"]
    r = _Runner(s, led)
    r.run([r.tx("c0", "REPORT", {"kind": "HOARD", "target": "c2"}),
           r.tx("c1", "REPORT", {"kind": "HOARD", "target": "c2"})])
    rec0, rec1 = led.records[-2], led.records[-1]
    assert rec0.accepted
    assert rec1.reason == "ALREADY_REPORTED"
    paid = [e for e in s.applied if e.get("action") == "WHISTLEBLOWER_PAID"]
    assert len(paid) == 1 and paid[0]["reward"] == 100
    assert s.surplus_pool == pool0 - 100
    assert s.balances["c0"] == bal0 + 100
    assert s.balances["c1"] == 100_000  # second reporter earned nothing


def test_self_report_rejected():
    wb = {"enabled": True, "reward_credits": 100, "max_per_tick": 10}
    s, led = _world({"whistleblower": wb})
    _plant_hoard_flag(s)  # target is c2
    r = _Runner(s, led)
    r.run([r.tx("c2", "REPORT", {"kind": "HOARD", "target": "c2"})])
    assert led.records[-1].reason == "SELF_REPORT"


def test_unknown_flag_rejected():
    wb = {"enabled": True, "reward_credits": 100, "max_per_tick": 10}
    s, led = _world({"whistleblower": wb})
    r = _Runner(s, led)
    r.run([r.tx("c0", "REPORT", {"kind": "HOARD", "target": "c2"})])
    assert led.records[-1].reason == "FLAG_NOT_FOUND"


def test_audit_report_on_boundary():
    au = {"enabled": True, "every_ticks": 5}
    s, led = _world({"audits": au})
    r = _Runner(s, led)
    for _ in range(10):
        r.run([])
    audits = [e for e in s.applied if e.get("action") == "AUDIT_REPORT"]
    assert [e["tick"] for e in audits] == [5, 10]
    a = audits[0]
    assert a["chain_ok"] is True
    assert a["records"] == len(led.records)
    assert a["accepted"] == led.accepted_count()
    assert a["surplus_pool"] == s.surplus_pool


def test_audit_off_by_default():
    s, led = _world()
    r = _Runner(s, led)
    for _ in range(12):
        r.run([])
    assert not any(e.get("action") == "AUDIT_REPORT" for e in s.applied)


def test_audit_catches_tampering():
    au = {"enabled": True, "every_ticks": 5}
    s, led = _world({"audits": au})
    r = _Runner(s, led)
    # A rejected REPORT writes a ledger record (any record works for the
    # chain-integrity check; the ledger must not be empty to tamper).
    r.run([r.tx("c0", "REPORT", {"kind": "HOARD", "target": "c2"})])
    # Simulate ledger tampering between ticks.
    from openboard.ledger import LedgerRecord
    old = led.records[-1]
    led.records[-1] = LedgerRecord(seq=old.seq, tick=old.tick, accepted=old.accepted,
                                   tx=dict(old.tx), reason="TAMPERED",
                                   prev_hash=old.prev_hash, tx_hash=old.tx_hash)
    for _ in range(4):  # advance to the next every_ticks=5 boundary
        r.run([])
    audits = [e for e in s.applied if e.get("action") == "AUDIT_REPORT"]
    assert audits and audits[-1]["chain_ok"] is False
