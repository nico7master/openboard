"""Rejection reason codes for the OpenBoard ledger.

Spec §14: every rejected action is a permanent public record with a reason —
failure is transparent, never silent.
"""

from __future__ import annotations

from enum import Enum


class Reason(str, Enum):
    """Why a transaction was rejected. Stable public API — never renumber."""

    UNKNOWN_SENDER = "UNKNOWN_SENDER"
    INVALID_PAYLOAD = "INVALID_PAYLOAD"
    NON_INTEGER_AMOUNT = "NON_INTEGER_AMOUNT"
    INSUFFICIENT_CREDITS = "INSUFFICIENT_CREDITS"
    UNKNOWN_CITIZEN = "UNKNOWN_CITIZEN"
    RULE_VIOLATION = "RULE_VIOLATION"
    MALFORMED_TRANSACTION = "MALFORMED_TRANSACTION"
    DUPLICATE_TRANSACTION = "DUPLICATE_TRANSACTION"


REJECTION_TEXT = {
    Reason.UNKNOWN_SENDER: "sender is not a registered citizen",
    Reason.INVALID_PAYLOAD: "payload does not match the action schema",
    Reason.NON_INTEGER_AMOUNT: "amounts must be integers (no floats in the ledger)",
    Reason.INSUFFICIENT_CREDITS: "sender balance too low for this action",
    Reason.UNKNOWN_CITIZEN: "payload references an unknown citizen",
    Reason.RULE_VIOLATION: "action violates the active rule-set",
    Reason.MALFORMED_TRANSACTION: "transaction object itself is malformed",
    Reason.DUPLICATE_TRANSACTION: "identical transaction already applied this tick",
}


def describe(reason: Reason) -> str:
    """Human-readable explanation of a rejection (for dashboards)."""
    return REJECTION_TEXT.get(reason, "unspecified")
