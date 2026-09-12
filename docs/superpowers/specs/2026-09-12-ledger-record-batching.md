# Ledger Record Batching (WP4.2 Lever D)

## Problem

Profile at 966 citizens: 19k records/tick → `canonical_json` + hashing dominates (~40% of tick). This is structural, not cognitive.

## Solution

Batch actions into a single `Record` per tick with a Merkle tree of transactions inside it.
- 1 canonical_json + hash per tick (vs 19k).
- Transaction content_hash + Merkle proofs per tx.
- Verification: Replay Merkle proofs + hash chain.

## Gate

Must land before anchor format freeze (pre-release window). Requires:
1. Fingerprint A/B (state/outcomes byte-identical).
2. Full suite pass.
3. Merkle verification unit tests.

## Implementation Plan

1. Modify `ledger.py` to accept `actions[]` batch + compute `tx_hash_merkle`.
2. Update `apply_tick` to batch all `out` txs into one ledger record.
3. Update replay logic to verify Merkle proofs.
4. Benchmark: expect ≥2× ledger speedup.

## Risk

- Spec §14 (every tx is a permanent record) satisfied via Merkle proofs.
- If proofs fail, fallback to 1:1 tx records (no breaking change).
