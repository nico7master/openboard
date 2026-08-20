"""OpenBoard Economy — deterministic economic protocol engine.

Phase 1: ledger core (append-only hash chain, state hashing, replay).
Phase 2: rules-as-data interpreter, goods catalog, recipes, cooperatives.
"""

from .catalog import GOODS, RECIPES, Recipe, validate_catalog
from .engine import apply_tick
from .errors import Reason, describe
from .ledger import GENESIS_HASH, Ledger, LedgerRecord, Transaction, canonical_json, sha256_hex
from .replay import InputLog, ReplayResult, record_history, replay
from .rules import DEFAULT_RULESET_PARAMS, REQUIRED_PARAMS, VALID_TRIAGE, RuleSetDoc, active_ruleset, active_version, validate_params
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
    "GOODS",
    "RECIPES",
    "Recipe",
    "validate_catalog",
    "DEFAULT_RULESET_PARAMS",
    "REQUIRED_PARAMS",
    "VALID_TRIAGE",
    "RuleSetDoc",
    "active_ruleset",
    "active_version",
    "validate_params",
]

__version__ = "0.3.0"
