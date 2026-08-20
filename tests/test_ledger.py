"""Ledger tests: chain integrity, append-only, rejections logged (plan T1/T2)."""

from __future__ import annotations

import copy

import pytest

from openboard import GENESIS_HASH, Ledger, Reason, Transaction, canonical_json


def make_tx(tick: int = 1, sender: str = "alice", to: str = "bob", amount: int = 10) -> Transaction:
    return Transaction(tick=tick, sender=sender, action="TRANSFER", payload={"to": to, "amount": amount})


class TestChain:
    def test_empty_ledger_verifies(self):
        ledger = Ledger()
        assert ledger.verify_chain()
        assert ledger.head_hash == GENESIS_HASH

    def test_accepted_tx_chains(self):
        ledger = Ledger()
        r1 = ledger.accept(make_tx())
        r2 = ledger.accept(make_tx(tick=2, sender="bob", to="alice"))
        assert ledger.verify_chain()
        assert r2.prev_hash == r1.record_hash()
        assert r1.seq == 0 and r2.seq == 1

    def test_rejected_tx_is_permanent_record(self):
        ledger = Ledger()
        ledger.accept(make_tx())
        rec = ledger.reject(make_tx(tick=1, sender="ghost"), Reason.UNKNOWN_SENDER)
        assert rec.accepted is False
        assert rec.reason == "UNKNOWN_SENDER"
        assert ledger.verify_chain()
        assert ledger.rejected_count() == 1

    def test_tampering_breaks_verification(self):
        ledger = Ledger()
        ledger.accept(make_tx())
        ledger.accept(make_tx(tick=2, sender="bob", to="alice"))
        ledger.accept(make_tx(tick=3, sender="alice", to="carol"))

        tampered = copy.deepcopy(ledger)
        tampered.records[1].tx["payload"]["amount"] = 999  # forge an amount
        assert tampered.verify_chain() is False

    def test_reordering_breaks_verification(self):
        ledger = Ledger()
        ledger.accept(make_tx())
        ledger.accept(make_tx(tick=2, sender="bob", to="alice"))
        tampered = copy.deepcopy(ledger)
        tampered.records.reverse()
        assert tampered.verify_chain() is False


class TestSerialization:
    def test_canonical_json_is_order_insensitive(self):
        a = canonical_json({"b": 1, "a": 2})
        b = canonical_json({"a": 2, "b": 1})
        assert a == b

    def test_floats_are_sanitized_not_crashed(self):
        tx = Transaction(tick=1, sender="alice", action="TRANSFER", payload={"to": "bob", "amount": 1.5})
        d = tx.to_dict()
        # float preserved as evidence, clearly marked — never a raw float in the chain
        assert "__float_forbidden__" in d["payload"]["amount"]

    def test_identical_tx_same_hash(self):
        t1 = make_tx()
        t2 = make_tx()
        assert t1.content_hash() == t2.content_hash()

    def test_different_payload_different_hash(self):
        assert make_tx(amount=10).content_hash() != make_tx(amount=11).content_hash()
