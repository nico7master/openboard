"""World state and canonical state hashing.

Spec §4.1: after each tick the engine commits hash(canonical(state)) —
external verifiers compare state hashes without trusting the operator.

Phase 1 state is deliberately minimal (T3): tick, citizen balances, applied
action log. Economy entities arrive in later phases; the hashing pipeline
stays identical.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .ledger import canonical_json, sha256_hex


@dataclass
class WorldState:
    """Minimal v0 world state. Grows per phase; hashing contract is stable."""

    tick: int = 0
    balances: dict[str, int] = field(default_factory=dict)
    applied: list[dict[str, Any]] = field(default_factory=list)

    def snapshot_dict(self) -> dict[str, Any]:
        """Canonical, fully-JSON view of the state (sorted keys downstream)."""
        return {
            "tick": self.tick,
            "balances": dict(sorted(self.balances.items())),
            "applied": list(self.applied),
        }

    def state_hash(self) -> str:
        return sha256_hex(canonical_json(self.snapshot_dict()))

    def clone(self) -> "WorldState":
        return WorldState(
            tick=self.tick,
            balances=dict(self.balances),
            applied=[dict(entry) for entry in self.applied],
        )


def genesis_state(citizens: dict[str, int]) -> WorldState:
    """Genesis allocation: citizen id → starting credit balance (integers)."""
    if not all(isinstance(v, int) and not isinstance(v, bool) for v in citizens.values()):
        raise ValueError("genesis balances must be integers")
    return WorldState(tick=0, balances=dict(citizens), applied=[])
