"""Engine + replay tests: determinism, shuffled equivalence, tamper
detection, and the Phase 1 fuzz gate (plan T4/T5).

Fuzz parameters: >=10,000 actions across >=100 ticks, seeded RNG — the
exact gate defined in the Phase 1 plan.
"""

from __future__ import annotations

import random
from dataclasses import replace

import pytest

from openboard import Ledger, Reason, Transaction, apply_tick, genesis_state, record_history, replay
from openboard.replay import InputLog

CITIZENS = {"alice": 1000, "bob": 800, "carol": 600, "dave": 400, "eve": 200}
IDS = list(CITIZENS.keys())


def tx(tick: int, sender: str, to: str, amount: int) -> Transaction:
    return Transaction(tick=tick, sender=sender, action="TRANSFER", payload={"to": to, "amount": amount})


def fuzz_batches(seed: int = 42, ticks: int = 120, per_tick: int = 90) -> dict[int, list[Transaction]]:
    """Seeded pseudo-random history: ~10,800 actions across 120 ticks."""
    rng = random.Random(seed)
    batches: dict[int, list[Transaction]] = {}
    for t in range(1, ticks + 1):
        batch = []
        for _ in range(per_tick):
            sender = rng.choice(IDS)
            to = rng.choice([c for c in IDS if c != sender])
            # amounts mostly affordable -> mix of accepts and rejects
            amount = rng.randint(1, 60)
            batch.append(tx(t, sender, to, amount))
        # sprinkle guaranteed-invalid transactions
        batch.append(tx(t, "ghost", "alice", 10))  # unknown sender
        batch.append(tx(t, sender, "nobody", 5))  # unknown recipient
        batch.append(tx(t, sender, to, 10**9))  # insufficient credits
        batches[t] = batch
    return batches


class TestEngineValidation:
    def test_valid_transfer_moves_credits(self):
        state = genesis_state(dict(CITIZENS))
        ledger = Ledger()
        apply_tick(state, ledger, [tx(1, "alice", "bob", 100)])
        assert state.balances["alice"] == 900
        assert state.balances["bob"] == 900
        assert state.tick == 1

    def test_unknown_sender_rejected(self):
        state = genesis_state(dict(CITIZENS))
        ledger = Ledger()
        apply_tick(state, ledger, [tx(1, "ghost", "alice", 10)])
        assert state.balances["alice"] == 1000
        assert ledger.rejected_count() == 1
        assert ledger.records[0].reason == "UNKNOWN_SENDER"

    def test_insufficient_credits_rejected(self):
        state = genesis_state(dict(CITIZENS))
        ledger = Ledger()
        apply_tick(state, ledger, [tx(1, "eve", "alice", 10**9)])
        assert state.balances["eve"] == 200
        assert ledger.rejected_count() == 1
        assert ledger.records[0].reason == "INSUFFICIENT_CREDITS"

    def test_zero_amount_is_rule_violation(self):
        state = genesis_state(dict(CITIZENS))
        ledger = Ledger()
        apply_tick(state, ledger, [tx(1, "alice", "bob", 0)])
        assert ledger.records[0].reason == "RULE_VIOLATION"

    def test_float_amount_rejected_as_non_integer(self):
        state = genesis_state(dict(CITIZENS))
        ledger = Ledger()
        bad = Transaction(tick=1, sender="alice", action="TRANSFER", payload={"to": "bob", "amount": 1.5})
        apply_tick(state, ledger, [bad])
        assert ledger.records[0].reason == "NON_INTEGER_AMOUNT"

    def test_duplicate_in_tick_rejected(self):
        state = genesis_state(dict(CITIZENS))
        ledger = Ledger()
        t = tx(1, "alice", "bob", 10)
        apply_tick(state, ledger, [t, t])
        assert ledger.accepted_count() == 1
        assert ledger.rejected_count() == 1
        assert ledger.records[1].reason == "DUPLICATE_TRANSACTION"

    def test_wrong_tick_rejected(self):
        state = genesis_state(dict(CITIZENS))
        ledger = Ledger()
        apply_tick(state, ledger, [tx(7, "alice", "bob", 10)])
        assert ledger.records[0].reason == "MALFORMED_TRANSACTION"

    def test_unknown_action_rejected(self):
        state = genesis_state(dict(CITIZENS))
        ledger = Ledger()
        bad = Transaction(tick=1, sender="alice", action="MAGIC", payload={})
        apply_tick(state, ledger, [bad])
        assert ledger.records[0].reason == "INVALID_PAYLOAD"


class TestDeterminism:
    def test_same_inputs_same_state_hash(self):
        batches = fuzz_batches(seed=7)
        _, _, s1 = record_history(dict(CITIZENS), batches)
        _, _, s2 = record_history(dict(CITIZENS), batches)
        assert s1.state_hash() == s2.state_hash()

    def test_input_order_irrelevant(self):
        """Shuffled submission order must produce the identical state hash."""
        rng = random.Random(99)
        batches = fuzz_batches(seed=5, ticks=10, per_tick=20)
        shuffled = {
            t: rng.sample(batch, len(batch))  # true shuffle, not sorted
            for t, batch in batches.items()
        }
        _, _, s1 = record_history(dict(CITIZENS), batches)
        _, _, s2 = record_history(dict(CITIZENS), shuffled)
        assert s1.state_hash() == s2.state_hash()

    def test_replay_matches_original(self):
        batches = fuzz_batches(seed=13)
        log, _, state = record_history(dict(CITIZENS), batches)
        result = replay(log)
        assert result.ok, f"replay failed at tick {result.mismatch_tick}"
        assert result.final_state_hash == state.state_hash()

    def test_replay_twice_identical(self):
        batches = fuzz_batches(seed=17)
        log, _, _ = record_history(dict(CITIZENS), batches)
        r1 = replay(log)
        r2 = replay(log)
        assert r1.ok and r2.ok
        assert r1.final_state_hash == r2.final_state_hash


class TestTamperDetection:
    def test_tampered_amount_detected(self):
        batches = fuzz_batches(seed=23, ticks=5, per_tick=10)
        log, _, _ = record_history(dict(CITIZENS), batches)
        forged = replace(log)
        first_tx = forged.batches[1][0]
        forged.batches[1] = [
            replace(first_tx, payload={"to": first_tx.payload["to"], "amount": first_tx.payload["amount"] + 1})
        ] + list(forged.batches[1][1:])
        result = replay(forged)
        assert result.ok is False
        assert result.mismatch_tick == 1

    def test_removed_action_detected(self):
        batches = fuzz_batches(seed=29, ticks=5, per_tick=10)
        log, _, _ = record_history(dict(CITIZENS), batches)
        forged = replace(log)
        forged.batches[3] = list(forged.batches[3][1:])  # drop first action
        result = replay(forged)
        assert result.ok is False

    def test_altered_genesis_detected(self):
        batches = fuzz_batches(seed=31, ticks=5, per_tick=10)
        log, _, _ = record_history(dict(CITIZENS), batches)
        forged = replace(log, genesis={**CITIZENS, "alice": 1001})
        result = replay(forged)
        assert result.ok is False

    def test_forged_state_hash_detected(self):
        batches = fuzz_batches(seed=37, ticks=5, per_tick=10)
        log, _, _ = record_history(dict(CITIZENS), batches)
        forged = replace(log)
        forged.state_hashes[2] = "f" * 64
        result = replay(forged)
        assert result.ok is False
        assert result.mismatch_tick == 2


class TestPhaseOneGate:
    """The exact gate: 10k+ actions, 100+ ticks, full fuzz battery."""

    def test_gate_fuzz_full(self):
        batches = fuzz_batches(seed=2026, ticks=120, per_tick=90)
        total_actions = sum(len(b) for b in batches.values())
        assert total_actions >= 10_000

        log, ledger, state = record_history(dict(CITIZENS), batches)
        assert ledger.verify_chain(), "chain integrity"

        result = replay(log)
        assert result.ok, f"replay mismatch at tick {result.mismatch_tick}"
        assert result.ticks_replayed == 120
        assert result.final_state_hash == state.state_hash()

        # conservation: total credits never changed (transfers only)
        assert sum(state.balances.values()) == sum(CITIZENS.values())

        # both outcomes present in a healthy mixed history
        assert ledger.accepted_count() > 0
        assert ledger.rejected_count() > 0

    def test_gate_multiple_seeds(self):
        for seed in (1, 2, 3):
            batches = fuzz_batches(seed=seed, ticks=100, per_tick=100)
            log, ledger, state = record_history(dict(CITIZENS), batches)
            assert ledger.verify_chain()
            result = replay(log)
            assert result.ok, f"seed {seed} failed at {result.mismatch_tick}"
            assert result.final_state_hash == state.state_hash()

    def test_no_floats_in_chain(self):
        batches = fuzz_batches(seed=77, ticks=3, per_tick=10)
        _, ledger, _ = record_history(dict(CITIZENS), batches)
        for rec in ledger.records:
            as_json = str(rec.to_dict())
            assert "__float_forbidden__" not in as_json

    def test_engine_rejects_float_amount_fuzz(self):
        state = genesis_state(dict(CITIZENS))
        ledger = Ledger()
        floats = [
            Transaction(tick=1, sender=s, action="TRANSFER", payload={"to": t, "amount": 3.14})
            for s, t in zip(IDS, IDS[1:] + IDS[:1])
        ]
        apply_tick(state, ledger, floats)
        assert ledger.accepted_count() == 0
        assert ledger.rejected_count() == len(floats)
        assert all(r.reason == "NON_INTEGER_AMOUNT" for r in ledger.records)
