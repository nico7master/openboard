# Spec: Regional Markets + Performance Bundle (WP4.2 close-out)
Date: 2026-09-11. Status: DRAFT for approval (hard gate: no engine
changes before sign-off). Doctrine: 2026-09-08-scaling-doctrine §3.

## 1. Fresh evidence (post-L1..L5 profile, 966 citizens, cProfile)

| Block | Share (of profiled tick) | Notes |
|---|---|---|
| Ledger append path (accept/append/record_hash, 19.2k records/tick) | ~40% | spec §14: every citizen action = permanent record |
| Bot cognition (sim.bot 5.7k + personal_needs 5.8k calls) | ~28% | 2 template families |
| Clearing sorts (53.3k sorted() calls, 8.9k/tick) | ~27% | OVERLAPS ledger bucket: sort_key->content_hash |
| Rest | ~10% | |

Honest gate math: bench 1.74 t/s at 966 (0.575 s/tick); gate >=5 t/s
(<0.2 s/tick) needs **2.9x**. Regional markets alone caps at ~2.0 t/s
(it shards ONLY clearing; record count is unchanged by design).
The gate is reachable only as a BUNDLE: (A) regional markets,
(B) batched cognition, (C) ledger micro-pass; then a Rust/pyo3
decision point if the bundle lands <5.

## 2. Lever A: Regional markets (SEMANTIC - realism contract)

- DIRECTION: real economies are local markets under global law; scarcity
  is regional before it is global (a bread shortage bites one district
  first, then spreads).
- MECHANISM: citizens partitioned into R deterministic regions
  (hash_bucket(citizen_id) with R = clamp(pop/100, 4..16), param
  overrides). _clear_markets runs PER REGION: essential clearing,
  producer-input clearing, and personal-needs fulfillment iterate
  region-local bid/listing partitions. Coops keep city-wide visibility
  (they are the producers; only BUYER-side clearing is sharded).
- MAGNITUDE: sorts scale O(sum r_i log r_i) instead of O(N log N) ->
  at R=10 the sort constant drops ~4-6x; measured target: -10..15%
  wall at 966.
- FLIP: regional scarcity now possible: one region can starve while
  the city average looks fine (the oversight board sees per-region
  streaks - new metric). Determinism: region id is a pure function of
  citizen_id; iteration order stays sorted by (region, citizen).
- CONTRACT TESTS: (1) region assignment deterministic + total;
  (2) money conservation exact with per-region clearing;
  (3) regional scarcity materializes under region-targeted shock;
  (4) equity/stability gates re-run (essentials streak bound, top-1
  ladder unchanged within seed noise on 3 seeds); (5) perf assertion
  at 966: sorts calls/tick drop by >=R/2.
- BYTE-COMPAT: NO (clearing order changes outcomes). This is a
  semantics change like L2: old worlds replay under the OLD code path
  only. migration: none (pre-anchor, pre-release).

## 3. Lever B: Batched cognition (BYTE-IDENTICAL)

Per the 2026-09-10 sketch + landed Patch A/B: hoist per-tick invariants
and apply per-coop/per-need templates in batch (5.7k bot calls ->
per-family batch loops). Target -12..18% wall. Proof: fingerprint
A/B byte-identical (ab9c0543 protocol), suite green.

## 4. Lever C: Ledger micro-pass (BYTE-IDENTICAL)

- _append_record/accept: fewer dict.get passes; reuse the record dict
  for record_hash concat; precomputed reason->byte strings.
- to_dict cache: also reuse the SAME dict instance in LedgerRecord.tx
  (no per-record dict copy) - safe because records are immutable.
- Target -5..8% wall. Proof: same fingerprint protocol.

## 5. Decision point (only if bundle < 5 t/s)

Rust/pyo3 for the ledger append+hash path (the 40%). Est 2-4x on that
path. OUT of scope until the bundle is measured; requires its own spec
(new build dep).

## 6. Acceptance (WP4.2 close-out)

1. All bundle levers landed with their proof protocols.
2. bench_scale at 966: >=5 t/s on the pinned 2-core runner (honest,
   printed).
3. Gates re-passed: hardcore survival (3 seeds), refresh2 stability
   ladder, seat soak; sweeps equity ladder unchanged within noise.
4. HANDOFF + doctrine doc updated with measured numbers.
