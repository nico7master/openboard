"""The Open Board — append-only, hash-chained transaction ledger.

Spec §4.1: every transaction t[n] includes hash(t[n-1]); no edits, no deletions.
Rejected transactions are also permanent records with reason codes (§14).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

from .errors import Reason

GENESIS_HASH = "0" * 64


def canonical_json(obj: Any) -> str:
    """Deterministic serialization: sorted keys, no whitespace, ASCII-safe."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_hex(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _sanitize(obj: Any) -> Any:
    """Make arbitrary data chain-safe: no floats, no NaN, JSON-only types.

    Floats are forbidden in the ledger (plan invariant). Any non-JSON scalar
    becomes its repr string so a malformed payload is still recorded verbatim
    as evidence rather than crashing the chain.
    """
    if isinstance(obj, bool) or obj is None or isinstance(obj, str):
        return obj
    if isinstance(obj, int):
        return obj
    if isinstance(obj, float):
        return {"__float_forbidden__": repr(obj)}
    if isinstance(obj, (list, tuple)):
        return [_sanitize(x) for x in obj]
    if isinstance(obj, dict):
        return {str(k): _sanitize(v) for k, v in obj.items()}
    return repr(obj)


@dataclass(frozen=True)
class Transaction:
    """An action submitted to the ledger (runtime fields only).

    seq/prev_hash/tx_hash are assigned by the Ledger — never by the sender.
    """

    tick: int
    sender: str
    action: str
    payload: dict[str, Any]
    ruleset_version: int = 1

    def to_dict(self) -> dict[str, Any]:
        # Memoized: frozen tx => dict is immutable and this is called several
        # times per tx per tick (sort_key -> content_hash, ledger accept,
        # batch records). Pure dedup; byte-identical output.
        cached = self.__dict__.get("_to_dict_cache")
        if cached is None:
            cached = {
                "tick": self.tick,
                "sender": self.sender,
                "action": self.action,
                "payload": _sanitize(self.payload),
                "ruleset_version": self.ruleset_version,
            }
            object.__setattr__(self, "_to_dict_cache", cached)
        return cached

    def content_hash(self) -> str:
        # Memoized: frozen tx => hash is immutable. Pure dedup; identical bytes.
        cached = self.__dict__.get("_content_hash")
        if cached is None:
            cached = sha256_hex(canonical_json(self.to_dict()))
            object.__setattr__(self, "_content_hash", cached)
        return cached

    def sort_key(self) -> tuple[str, str, str, int]:
        """Deterministic ordering inside a tick (plan T4)."""
        return (self.sender, self.action, self.content_hash(), self.ruleset_version)


@dataclass(frozen=True)
class LedgerRecord:
    """A permanent ledger entry — accepted or rejected."""

    seq: int
    tick: int
    accepted: bool
    tx: dict[str, Any]
    reason: str | None
    prev_hash: str
    tx_hash: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "seq": self.seq,
            "tick": self.tick,
            "accepted": self.accepted,
            "tx": self.tx,
            "reason": self.reason,
            "prev_hash": self.prev_hash,
            "tx_hash": self.tx_hash,
        }

    def record_hash(self) -> str:
        """Chain hash over the record's identity + linkage fields.

        The tx CONTENT is committed separately by tx_hash (computed once
        from the Transaction at accept/reject time); verify_chain() checks
        every record's tx against its tx_hash, so tampering with content
        still breaks the chain — but appending no longer re-serializes the
        full tx dict per record. Memoized: records are immutable.
        (v2 format, pre-anchor window: hash VALUES differ from v1.)"""
        cached = self.__dict__.get("_record_hash")
        if cached is None:
            cached = sha256_hex(canonical_json(self._chaining_fields()))
            object.__setattr__(self, "_record_hash", cached)
        return cached

    def _chaining_fields(self) -> dict[str, Any]:
        return {
            "seq": self.seq,
            "tick": self.tick,
            "accepted": self.accepted,
            "reason": self.reason,
            "prev_hash": self.prev_hash,
            "tx_hash": self.tx_hash,
        }


class Ledger:
    """Append-only ledger. Both outcomes are chained public records."""

    def __init__(self) -> None:
        self.records: list[LedgerRecord] = []
        self._head_hash = GENESIS_HASH

    @property
    def head_hash(self) -> str:
        return self._head_hash

    def _append_record(self, record: LedgerRecord) -> None:
        self.records.append(record)
        self._head_hash = record.record_hash()

    def accept(self, tx: Transaction) -> LedgerRecord:
        rec = LedgerRecord(
            seq=len(self.records),
            tick=tx.tick,
            accepted=True,
            tx=tx.to_dict(),
            reason=None,
            prev_hash=self._head_hash,
            tx_hash=tx.content_hash(),
        )
        self._append_record(rec)
        return rec

    def reject(self, tx: Transaction, reason: Reason) -> LedgerRecord:
        rec = LedgerRecord(
            seq=len(self.records),
            tick=tx.tick,
            accepted=False,
            tx=tx.to_dict(),
            reason=reason.value,
            prev_hash=self._head_hash,
            tx_hash=tx.content_hash(),
        )
        self._append_record(rec)
        return rec

    def verify_chain(self) -> bool:
        """Recompute the whole chain; any tampering anywhere breaks it.

        Two checks per record: (1) content — the record's tx dict must
        hash to its committed tx_hash; (2) linkage — chaining fields must
        recompute record_hash, and prev links must line up."""
        expected_prev = GENESIS_HASH
        for i, rec in enumerate(self.records):
            if rec.seq != i or rec.prev_hash != expected_prev:
                return False
            if sha256_hex(canonical_json(rec.tx)) != rec.tx_hash:
                return False
            if rec.record_hash() != sha256_hex(canonical_json(rec._chaining_fields())):
                return False
            expected_prev = rec.record_hash()
        return self._head_hash == expected_prev

    def accepted_count(self) -> int:
        return sum(1 for r in self.records if r.accepted)

    def rejected_count(self) -> int:
        return sum(1 for r in self.records if not r.accepted)
