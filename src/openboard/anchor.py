"""Cardano anchoring — protocol layer (Phase 8).

Deterministic commitments over the ledger and state, a binary merkle
root, and CBOR-safe anchor messages ready to post on Cardano metadata
(or feed to a Paima/Aiken pipeline later). Posting mechanism itself is
a user review item (spec §13).

Only strings/ints in anchor messages — no floats, no bools — so the
messages map cleanly onto Cardano transaction metadata.
"""

from __future__ import annotations

from typing import Any

from .ledger import canonical_json, sha256_hex

ALG = "openboard-anchor-v1"


def tick_commitment(tick: int, state_hash: str, ledger_head: str) -> str:
    """Commit to one tick: the full world state (state_hash) and the
    entire transaction history prefix (ledger_head = last tx_hash)."""
    if not isinstance(tick, int) or isinstance(tick, bool):
        raise ValueError("tick must be an int")
    payload = {"tick": tick, "state_hash": state_hash, "ledger_head": ledger_head}
    return sha256_hex(canonical_json(payload))


def merkle_root(commitments: list[str]) -> str:
    """Binary merkle root. Pairwise sha256 over concatenated hex strings;
    odd levels duplicate the last element. Empty -> sha256(\"\") for a
    stable, documented empty-root."""
    if not commitments:
        return sha256_hex("")
    level = list(commitments)
    while len(level) > 1:
        if len(level) % 2 == 1:
            level.append(level[-1])
        level = [sha256_hex(level[i] + level[i + 1]) for i in range(0, len(level), 2)]
    return level[0]


def build_anchor(day: int, commitments: list[str], prev_anchor_root: str) -> dict[str, Any]:
    """CBOR-safe anchoring message. One anchor per day/epoch commits the
    entire history before it; each references the previous anchor root,
    forming an on-chain chain that cannot be reordered."""
    if not isinstance(day, int) or isinstance(day, bool):
        raise ValueError("day must be an int")
    root = merkle_root(commitments)
    return {
        "alg": ALG,
        "day": day,
        "merkle_root": root,
        "prev_anchor": prev_anchor_root,
    }


def verify_anchor(commitments: list[str], anchor: dict[str, Any]) -> bool:
    """Recompute the merkle root over the commitments and compare with the
    posted anchor. Anyone holding the ledger can verify a posted anchor."""
    if not isinstance(anchor, dict):
        return False
    if anchor.get("alg") != ALG:
        return False
    expected = merkle_root(commitments)
    return anchor.get("merkle_root") == expected


def anchor_chain(commitment_days: list[list[str]], genesis_root: str = sha256_hex("")) -> list[dict[str, Any]]:
    """Build the full anchor chain: day 1 anchors onto the empty root,
    each later day anchors onto the previous day's merkle root."""
    chain: list[dict[str, Any]] = []
    prev = genesis_root
    for day, commitments in enumerate(commitment_days, start=1):
        anchor = build_anchor(day, commitments, prev)
        chain.append(anchor)
        prev = anchor["merkle_root"]
    return chain


def is_cborsafe(value: Any) -> bool:
    """True if the value maps cleanly to Cardano metadata: ints, strings,
    lists, and dicts with string keys. No floats, no bools, no None."""
    if isinstance(value, bool):
        return False
    if isinstance(value, int) or isinstance(value, str):
        return True
    if isinstance(value, list):
        return all(is_cborsafe(v) for v in value)
    if isinstance(value, dict):
        return all(isinstance(k, str) and is_cborsafe(v) for k, v in value.items())
    return False
