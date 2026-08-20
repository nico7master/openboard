# Phase 8 Plan: Cardano Anchoring — Protocol Layer

Goal: the deterministic commitment machinery that makes the Open Board
publicly verifiable on Cardano. **Protocol only** — live chain posting
(wallet, network choice, funding, Aiken contract vs metadata vs Paima)
is an open review item for the user, per spec §13.

## Design

- `anchor.py`
  - `tick_commitment(tick, state_hash, ledger_head)` -> hex commitment:
    sha256 over (tick, state_hash, ledger_head) — commits to the full
    world state AND the full ledger prefix in one hash.
  - `merkle_root(commitments)` -> deterministic binary merkle root
    (pairwise sha256; odd level duplicates the last element).
  - `build_anchor(day, commitments, prev_anchor_root)` -> CBOR-safe
    anchoring message: {"day", "merkle_root", "prev_anchor", "alg"} —
    only strings/ints (Cardano metadata constraints; no floats).
  - `verify_anchor(commitments, anchor)` -> bool: recompute the root and
    compare. Anyone with the ledger can verify a posted anchor.
- Anchor chain: each anchor references the previous anchor's root —
  one on-chain anchor per day/epoch commits the entire history before it.

## Boundary (awaits user decisions)

- Which live mechanism: metadata-only, Aiken validator, or Paima.
- Network (preview testnet first), wallet keys, funding.

## Tasks

- [x] anchor.py implementation
- [x] tests/test_phase8.py: commitment determinism, hand-verified merkle
      root, anchor chain linking, tamper detection (any ledger edit breaks
      the root), CBOR-safety (no floats/bools in messages)
- [x] sim.py cleanup (unused imports)
- [x] Full suite green
