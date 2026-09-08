# WP4.2 Perf Ladder — Night Session 2026-09-08 (02:00 CEST)

Workload: scaled world pop=966, 10-tick unprofiled wall benchmark
(`scripts/bench_scale.py`, settle 3 ticks, seed 42, double-run every time).
Gate target: **≥5 ticks/s at 1,000 citizens / 300 coops** (shipping month WP4.2).

## Measured ladder (same harness throughout)

| Step | Commit | ticks/s (double-run) | Δ | Replay proof |
|---|---|---|---|---|
| pre-memoization (gate log) | — | 1.95 (profiled context) | — | — |
| + to_dict memoization | 08503a9 | ~2.18 est. | −11% wall | byte-identical head fingerprint |
| + record_hash v2 (chaining fields only) | db608da | 1.02 → 1.10 | **+8%** | 109 tamper/chain tests; content+linkage double check |
| + per-tick dispatch hoist (engine) | 3b1c1c1 | 1.10 → 1.20/1.21 | **+9%** | 425/425 suite + 30-tick fingerprint A/B identical (ab9c0543a2b5e98c) |
| + cached JSONEncoder | d10b572 | 1.24/1.21 | ~+2% | 109 tests + fingerprint identical |

Net tonight vs same-harness start: **1.02 → ~1.22 ticks/s (+20%), zero behavior change.**

## What each change does

1. **record_hash v2** — the chain hash now covers only `{seq, tick, accepted,
   reason, prev_hash, tx_hash}`; tx content stays committed by `tx_hash`
   (computed once from the frozen Transaction). `verify_chain` checks BOTH:
   content (rec.tx → tx_hash) and linkage (chaining fields → record_hash).
   Tamper-evidence preserved: payload tamper breaks content check, tx_hash
   tamper breaks chain check, reordering breaks seq/prev. **v2 hash VALUES
   differ from v1 — landed inside the pre-anchor window on purpose; anchors
   are unaffected (tick_commitment uses last tx_hash).**
2. **Dispatch hoist** — the validator dict (20 lambdas) and apply dict
   (10 entries) were rebuilt per transaction (~18k txs/tick at scale; the
   profile's 107,989 lambda constructions in 6 ticks). Both now built once
   per tick, closed over that tick's state/params; every per-action call
   signature preserved exactly. Also removed a duplicated CRISIS_VOTE key
   (same function twice — no behavior change).
3. **Cached encoder** — module-level `json.JSONEncoder(sort_keys, separators,
   ensure_ascii).encode` instead of `json.dumps` with kwargs (which builds
   an encoder per call): 1.33x on hot shapes.

## Negative result (kept on purpose)

A pure-Python canonical-JSON fast path (exact-type dispatch, hand-built
parts, fuzz-proven byte-identical over 50k random JSON trees) was **slower**
than json.dumps: 1.07 vs 1.20 ticks/s. cPython dispatches kwargs-dumps to
the C encoder; Python string-building loses to C. Reverted; kept the cached-
encoder win instead.

## Updated cost map (profiled shares at HEAD, cProfile for call counts only)

| Block | share (pre-optimization) | now |
|---|---|---|
| Hash chain / JSON | ~35% | reduced (memoization + v2 hashes + cached encoder) |
| Bot cognition (sim.py + personal_needs) | ~30% | ~largest remaining |
| Market clearing sorts | ~25% | partially reduced (fewer dict/lambda builds) |

## Path to the 5 ticks/s gate (honest)

Remaining work is algorithmic, per the scaling doctrine
(`docs/ideas/2026-09-08-scaling-doctrine-hierarchy-of-computation.md`):

1. **Batched bot cognition** (~20–30% est.) — aggregate/vectorize per-tick
   citizen decisions; biggest single remaining block.
2. **Market sort bucketing** (~15–20% est.) — sort per-good bid lists once
   per tick instead of repeated per-bid sorts in clearing loops.
3. **Regional markets** (structural) — shards O(N) global work into
   O(N/M) regions; the guarantee that carries 10⁴+ citizens.

Rule for every step above: same-harness double benchmark + 30-tick
fingerprint A/B + full suite before commit.
