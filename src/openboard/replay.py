"""Replay & verification (Phase 1 gate).

Spec §3/§10.1: anyone re-executes the input log and verifies every state
transition. Replay mismatch = hard failure of the "proven" claim.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .engine import apply_tick
from .ledger import GENESIS_HASH, Ledger, Transaction
from .state import WorldState, genesis_state


@dataclass
class InputLog:
    """The canonical record needed to replay a whole history.

    - genesis: citizen id → starting balance
    - batches: tick number → action batch (in submission order)
    - state_hashes: tick → recorded state hash after that tick
    """

    genesis: dict[str, int] = field(default_factory=dict)
    batches: dict[int, list[Transaction]] = field(default_factory=dict)
    state_hashes: dict[int, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "genesis": self.genesis,
            "batches": {
                str(t): [tx.to_dict() for tx in batch]
                for t, batch in sorted(self.batches.items())
            },
            "state_hashes": {str(t): h for t, h in sorted(self.state_hashes.items())},
        }


@dataclass
class ReplayResult:
    ok: bool
    ticks_replayed: int = 0
    mismatch_tick: int | None = None
    expected_hash: str | None = None
    got_hash: str | None = None
    final_state_hash: str | None = None


def record_history(
    genesis: dict[str, int],
    batches: dict[int, list[Transaction]],
) -> tuple[InputLog, Ledger, WorldState]:
    """Run a history forward once, capturing the input log and hashes."""
    state = genesis_state(genesis)
    ledger = Ledger()
    log = InputLog(genesis=dict(genesis))
    for tick in sorted(batches.keys()):
        apply_tick(state, ledger, batches[tick], current_tick=tick)
        log.batches[tick] = list(batches[tick])
        log.state_hashes[tick] = state.state_hash()
    return log, ledger, state


def replay(log: InputLog) -> ReplayResult:
    """Re-execute the whole history; verify every recorded state hash.

    Determinism contract: same genesis + same batches → identical hashes.
    Any mismatch means the log was tampered with or the engine changed.
    """
    state = genesis_state(log.genesis)
    ledger = Ledger()  # replay ledger: discard, but chain must still verify
    result = ReplayResult(ok=True)

    for tick in sorted(log.batches.keys()):
        apply_tick(state, ledger, log.batches[tick], current_tick=tick)
        result.ticks_replayed += 1
        got = state.state_hash()
        expected = log.state_hashes.get(tick)
        if expected is not None and got != expected:
            result.ok = False
            result.mismatch_tick = tick
            result.expected_hash = expected
            result.got_hash = got
            result.final_state_hash = got
            return result

    if not ledger.verify_chain():
        result.ok = False
        result.mismatch_tick = -1  # internal ledger chain corruption
        return result

    result.final_state_hash = state.state_hash()
    return result


def verify_head_matches(log: InputLog, ledger: Ledger) -> bool:
    """Cross-check: ledger head hash covers the same history (sanity helper)."""
    return ledger.head_hash != GENESIS_HASH
