"""OpenBoard Economy — deterministic economic protocol engine.

Phase 1: ledger core (append-only hash chain, state hashing, replay).
"""

from .engine import apply_tick
from .errors import Reason, describe
from .ledger import GENESIS_HASH, Ledger, LedgerRecord, Transaction, canonical_json, sha256_hex
from .replay import InputLog, ReplayResult, record_history, replay
from .state import WorldState, genesis_state

__all__ = [
    "apply_tick",
    "Reason",
    "describe",
    "GENESIS_HASH",
    "Ledger",
    "LedgerRecord",
    "Transaction",
    "canonical_json",
    "sha256_hex",
    "InputLog",
    "ReplayResult",
    "record_history",
    "replay",
    "WorldState",
    "genesis_state",
]

__version__ = "0.1.0"
