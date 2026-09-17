# Spec: Performance Floor ≥5 ticks/s at 1,000 Citizens (WP4.2)

Date: 2026-09-16. Founder directive: "Do performance." UX pass explicitly
deferred until this is done.

## Evidence (measured this session)

| Metric | Value |
|---|---|
| Unprofiled rate, 975 pop, 10 ticks | **1.33 ticks/s** (bench_scale.py, seed 42) |
| WP4.2 gate floor | **≥5 ticks/s** (scaling doctrine, docs/ideas/2026-09-08) |
| Gap | ~3.8× |
| Ledger records per tick | 21,036, of which BUY_ESSENTIAL = **18,349 (87%)** |
| Buys per citizen per tick | mean 18.8 / median 19 (one tx PER GOOD) |
| Profiled cost (9 ticks, cProfile) | content_hash 4.42s, sort_key 4.31s, _validate_buy_essential 1.55s, personal_needs 1.6s |

Root cause: per-transaction fixed cost (sanitize → canonical JSON → sha256 →
sort tuple → validate → ledger record) multiplied by ~21k tx/tick, 87% of
which are one-good essential buys that always travel together.

## Tier 1 — pure caching/hoisting (zero semantic change, replay-safe)

1. **sort_key memoization** (ledger.py): the sort comparator rebuilt the
   tuple (incl. content_hash lookup) per comparison — 191k builds for 21k
   txs. Cache on the frozen tx (same pattern as _content_hash). Identical
   tuple, identical order.
2. **_validate_buy_essential micro-opts** (engine.py): replace
   `set(payload.keys()) != {"good","qty"}` (allocates a set per call,
   165k/tick) with length+membership checks; replace
   `state.effective_triage(good)` (re-resolves active rulesets per call)
   with the identical inline lookup from the `params` already in hand
   (overrides.get(good, goods[good].triage) — same inputs, same result).

## Tier 2 — BUY_ESSENTIAL_BASKET (structural, opt-in, replay-safe)

One transaction per citizen per tick carrying ALL essential buys:
`{"goods": {good: qty, ...}}`.

- **Validation** (engine.py): identical per-good rules as BUY_ESSENTIAL
  (sender exists, good known, triage essential/emergency, qty ≤ quota,
  cumulative funds ≥ Σ floor×qty), applied over `sorted(goods)` for
  determinism. Any bad good rejects the WHOLE basket (atomic — no partial
  baskets; keeps rejection semantics simple and public).
- **Application**: enqueue the same bid dicts the individual actions would
  enqueue, in `sorted(goods)` order (deterministic; per-good clearing
  semantics unchanged — fair-clearing rotation and FCFS operate on the bid
  list exactly as before).
- **Bot side** (bots.py personal_needs): when enabled, essentials are
  emitted as ONE basket tx (market BIDs stay individual). Selection logic
  unchanged (same ceilings, same affordability gate per good).
- **Rollout**: new optional param `basket_buys: {"enabled": bool}`.
  Absent → inert; old saves replay byte-identically (they contain no
  basket txs). New games enable it in server.py._params (governance block
  convention).
- **Ledger shape**: new runs record one basket record per citizen-tick
  instead of ~19 single-good records. This is a deliberate, public,
  hash-chained record of the same economic content — the ledger stays
  append-only and fully transparent. Old-world replay and verify_chain
  are unaffected.

## Expected effect

Tier 1: ~10-15% (sort + validate overhead). Tier 2: tx volume 21k → ~3.7k
per tick (~5.7×) → projected **5-7 ticks/s**. Verified by: bench_scale.py
≥5 t/s at pop ≥1000, hardcore survival gate (3 seeds × 2,000 ticks, basket
enabled), full regression suite green, byte-identical legacy replay test.

## Non-goals (this round)

- No C/Rust kernels (no toolchain in container; installs need approval).
- No regional sharding changes (doctrine §3 — separate workstream).
- No LIST_GOOD batching (not needed to reach the floor; revisit at 10k).

## Lever C sub-step 2 verdict (2026-09-17): plan memo REJECTED, hazard documented

The honest-wages production-plan memo was implemented twice and rejected on evidence:

1. **coop_id-only key diverged** (fingerprint): D18 mobility means one coop can hold
   members with DIFFERENT closure constants (farmer target 450 + baker 420 in the
   same coop after a switch) — the plan is (coop, closure)-constant, not coop-constant.
2. **(coop, closure) key still diverged**: root cause found by surgical diff —
   `state.tick` lags cognition (`apply_tick` sets it), so the shared
   `_decision_cache` spans tick T and T+1 cognition; tick-1 plans (bakers 2h)
   leaked into tick-2 cognition (correct: 1h). 212 applied-event diffs at t=2.
3. **tick-keyed memo was byte-identical** (30-tick per-tick bisect + canonical
   fingerprint `15ca1520...` matched) — but **worthless**: on the real basket-ON
   path it measured 17.47 t/s vs 18.06 t/s without (noise/slightly slower). The
   basket-buys batching already eliminated the dominant cost; the plan block is
   no longer hot.

**Decision:** revert the memo. A hazardous cross-tick caching pattern is not
worth zero gain. The `state.tick`-lags-cognition fact is now documented here and
must be respected by ANY future cache keyed on `_decision_cache` (include the
cognition tick in the key or validate `state.tick` semantics first).

**Floor status: MET without the memo** — real path (basket ON, 966 citizens):
**~18 t/s vs the ≥5 t/s target (3.6× headroom)**; legacy path ~7.6 t/s.
