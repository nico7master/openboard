# Spec — Ledger record_hash v3 (concat encoding)

Status: APPROVED (user, 2026-09-10 "do it") — implements the ledger lever
scoped in the batched-cognition spec's profile verdict.

## Problem (measured, post Patch A/B, cProfile 6 ticks @ 966)

apply_tick = 78% of tick time. Inside it, every ledger record still pays
one canonical_json (~5.3us) + encode for `record_hash` — ~19k records/tick
=> ~100ms/tick of pure serialization for a 6 small-field dict. Micro-bench:
identical 6-field input via length-safe concat = 1.97us (**2.68x**).

Per-tick record BATCHING (one record per tick) was considered and REJECTED:
it contradicts spec §14 (every tx incl. rejections is a permanent record),
breaks per-record consumers (metrics reasons, server preview, per-record
tests) and needs a §14 amendment. v3 keeps per-record semantics.

## Change

`record_hash` hash INPUT: canonical_json(6-field dict) -> deterministic
length-safe concat:

    sha256(f"{seq}|{tick}|{accepted}|{reason}|{prev_hash}|{tx_hash}")

Unambiguity: prev_hash/tx_hash are fixed 64-hex (Ledger-controlled);
reason is a controlled vocabulary (Reason enum, no "|", empty for
accepted); seq/tick are ints. The content commitment (tx_hash =
sha256(canonical_json(tx))) is UNCHANGED - content tamper-evidence and
the sort tiebreak (which uses content_hash) are untouched, so state
evolution cannot change.

verify_chain(): linkage check calls record_hash() (memoized) instead of
re-deriving the formula inline; content check (canonical_json(rec.tx)
vs tx_hash) unchanged.

## What changes / what must not

- CHANGES: record_hash VALUES and head_hash values (allowed - pre-anchor
  window, v2 comment already blesses value changes; no test hardcodes
  64-hex literals; anchor.py consumes only opaque head strings).
- MUST NOT CHANGE: acceptance/rejection outcomes and order (content_hash
  formula untouched), state evolution (FINAL_STATE_HASH), per-record
  API (fields, to_dict), §14 semantics.

## Equivalence protocol

1. Baseline at HEAD: 30-tick 966-citizen run -> FINAL_STATE_HASH +
   OUTCOMES_SHA (multiset of tick/accepted/reason/action/sender over all
   records) + untrimmed short run with verify_chain()==True.
2. After patch: same probe -> FINAL_STATE_HASH and OUTCOMES_SHA must be
   IDENTICAL to baseline; verify_chain True on the untrimmed run.
3. Full suite (425) green via memrun 6 pinned.
4. Pinned bench A/B: expect ~+8-12% from removing ~19k encodes/tick.

## Verification

- fingerprint-style equivalence probe (state evolution, not hash values)
- full suite 425
- bench_scale.py pinned double-run
- verify_chain() round-trip on untrimmed ledger
