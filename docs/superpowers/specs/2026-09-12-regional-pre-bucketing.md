# Regional Listing Pre-Bucketing (WP4.2 Lever E) — DECLINED

## Original idea

Pre-bucket listings by region once per tick so each regional clearing pass skips global listing scans.

## Verdict: DECLINED — violates the approved L6 contract

1. **Listings are city-wide by contract** (regional-markets bundle spec, 2026-09-11): coops are producers with full visibility; only BIDS are region-partitioned. Bucketing listings into regions would hide supply across regions and break the deferred-unsold semantics (later regions must see remaining supply).
2. **The per-pass projection cannot be cached across passes**: sales in region r's pass mutate entry `qty` in place, and later regions must observe those mutations. Rebuilding the filtered projection per pass IS the correctness mechanism (engine.py:1364–1385, L6 perf fix 2026-09-12, which already cut 56M `min()` calls per 5 ticks to parity with OFF).
3. **Remaining per-pass cost is bounded**: the projection allocates over `want_goods x live entries` only; the post-fix cProfile shows ON per-call clearing time equal to OFF (0.090s vs 0.092s).

## What remains measurable

The only cheap, contract-safe knob is the **region count** R: wrapper fixed cost scales ~linearly in R (R passes × per-pass sort/alloc). Sweep R=4/6/10 at 966 citizens quantifies the curve and decides whether regions-ON can be made perf-competitive by tuning alone. Evidence: `/tmp/bench_r4.log`, `/tmp/bench_r6.log` (pinned 2-core memrun). Structural fixes (pre-partitioned clearing state, Rust/pyo3 kernels) still require their own spec + fingerprint gate.