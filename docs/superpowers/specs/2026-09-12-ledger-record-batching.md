# Ledger Record Batching (WP4.2 Lever D) — REVISED

## Problem (Original)

Profile at 966 citizens: 19k records/tick → `canonical_json` + hashing dominates (~40% of tick). This is structural, not cognitive.

## Updated Verdict: DECLINED (Structural Ceiling)

**Content hashing cannot be removed.** Per Spec §14, every outcome (including rejections) must have a permanent content commitment (`tx_hash = sha256(canonical_json(tx))`). Measured: **2.42s cumtime over the 6-tick profile ≈ 27% of the 9.09s wall (≈0.4s/tick)** at 966 citizens — irreducible in Python, only parallelizable or Rust-portable.

**Linkage hashing is the true batchable ceiling.** `record_hash` (linkage chain) is **0.69s over 6 ticks (~8% of wall)**. A tick-level Merkle root on the *linkage fields* would save ~8% at best — not the 2x the first draft claimed.

**Overlap note:** `sorted`/`sort_key` show 2.44s cumtime, but that INCLUDES first-time `content_hash` computations (hashing runs inside `sort_key` for the tiebreak). Do not double-count; the pure sort overhead is small.

**Risk:** Any structural change to the record stream (batching, different hashes, per-tick vs per-tx records) breaks the fingerprint A/B proof gate. Without that gate, replay security claims are void.

## Recommendation

1.  **Mark as "On Hold"** until release gate is complete. The ~8% gain is not worth the fingerprint risk pre-v1.0.
2.  **Post-release path:** If Rust is considered, optimize the *hashing loop* itself (parallel `content_hash`), not the ledger structure. This preserves per-tx commitment but reduces wall time.

## Proof Reference

- Profile: `scripts/profile_scale.py 966 6 42` — seed 42, 933 settled pop, 6 ticks, 9.23s wall (9.086s profiled). Captured at tree `fbcff56`; `61a160b` and later are docs-only commits, so the code state is identical to the 465-green `7f76cad`:
  - `content_hash` chain: 2.42s cumtime (~27%)
  - `record_hash` linkage: 0.69s cumtime (~8%)
  - `sorted` 2.44s cumtime — overlaps `content_hash`, not additive
  - → ~0.65 t/s at 966 citizens
