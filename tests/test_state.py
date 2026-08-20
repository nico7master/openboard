"""State tests: canonical hashing, immutability-by-value (plan T3)."""

from __future__ import annotations

import pytest

from openboard import WorldState, genesis_state


class TestGenesis:
    def test_genesis_hash_stable(self):
        s1 = genesis_state({"alice": 100, "bob": 50})
        s2 = genesis_state({"alice": 100, "bob": 50})
        assert s1.state_hash() == s2.state_hash()

    def test_genesis_order_insensitive(self):
        a = genesis_state({"alice": 100, "bob": 50})
        b = genesis_state({"bob": 50, "alice": 100})
        assert a.state_hash() == b.state_hash()

    def test_genesis_rejects_floats(self):
        with pytest.raises(ValueError):
            genesis_state({"alice": 100.5})

    def test_genesis_rejects_bools(self):
        with pytest.raises(ValueError):
            genesis_state({"alice": True})


class TestStateHash:
    def test_any_mutation_changes_hash(self):
        s = genesis_state({"alice": 100, "bob": 50})
        h0 = s.state_hash()
        s.balances["alice"] -= 1
        s.balances["bob"] += 1
        assert s.state_hash() != h0

    def test_tick_advances_hash(self):
        s = genesis_state({"alice": 100})
        h0 = s.state_hash()
        s.tick = 1
        assert s.state_hash() != h0

    def test_clone_is_independent(self):
        s = genesis_state({"alice": 100, "bob": 50})
        c = s.clone()
        c.balances["alice"] = 0
        assert s.balances["alice"] == 100

    def test_applied_log_changes_hash(self):
        s = genesis_state({"alice": 100, "bob": 50})
        h0 = s.state_hash()
        s.applied.append({"tick": 1, "sender": "alice", "action": "TRANSFER", "to": "bob", "amount": 10})
        assert s.state_hash() != h0
