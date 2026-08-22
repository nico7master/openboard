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
    RULESET_MISMATCH = "RULESET_MISMATCH"
    INVALID_RULESET = "INVALID_RULESET"
    ACTIVATION_IN_PAST = "ACTIVATION_IN_PAST"
    COOP_EXISTS = "COOP_EXISTS"
    NOT_A_MEMBER = "NOT_A_MEMBER"
    ALREADY_IN_COOP = "ALREADY_IN_COOP"
    COOP_NOT_FOUND = "COOP_NOT_FOUND"
    COOP_FULL = "COOP_FULL"
    COOP_TOO_SMALL = "COOP_TOO_SMALL"
    RECIPE_NOT_FOUND = "RECIPE_NOT_FOUND"
    INVALID_RUNS = "INVALID_RUNS"
    INVALID_HOURS = "INVALID_HOURS"
    NOT_ENOUGH_LABOR = "NOT_ENOUGH_LABOR"
    NOT_ENOUGH_INPUTS = "NOT_ENOUGH_INPUTS"
    NOT_ENOUGH_ENERGY = "NOT_ENOUGH_ENERGY"
    GOOD_UNKNOWN = "GOOD_UNKNOWN"
    INVALID_QTY = "INVALID_QTY"
    INVALID_PRICE = "INVALID_PRICE"
    INSUFFICIENT_FUNDS = "INSUFFICIENT_FUNDS"
    NOT_ESSENTIAL = "NOT_ESSENTIAL"
    QUOTA_EXCEEDED = "QUOTA_EXCEEDED"
    NOT_ENOUGH_INVENTORY = "NOT_ENOUGH_INVENTORY"
    PROPOSAL_NOT_FOUND = "PROPOSAL_NOT_FOUND"
    VOTE_WINDOW_CLOSED = "VOTE_WINDOW_CLOSED"
    ALREADY_VOTED = "ALREADY_VOTED"
    INVALID_CHOICE = "INVALID_CHOICE"
    GOVERNANCE_LOCKED = "GOVERNANCE_LOCKED"
    GOVERNANCE_DISABLED = "GOVERNANCE_DISABLED"
    TARGET_VERSION_NOT_FOUND = "TARGET_VERSION_NOT_FOUND"
    CONSTITUTIONAL_GUARD = "CONSTITUTIONAL_GUARD"
    LABOR_POOL_FULL = "LABOR_POOL_FULL"
    NOT_COUNCIL_MEMBER = "NOT_COUNCIL_MEMBER"
    INVALID_INTERVENTION = "INVALID_INTERVENTION"
    INTERVENTION_TYPE_UNKNOWN = "INTERVENTION_TYPE_UNKNOWN"


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
