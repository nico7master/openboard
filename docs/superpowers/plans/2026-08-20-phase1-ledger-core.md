# Implementation Plan — Phase 1: Ledger Core

**Date:** 2026-08-20
**Spec:** `docs/superpowers/specs/2026-08-19-openboard-economy-engine-design.md` (§4.1, §12 Phase 1)
**Gate:** replay fuzz tests green

---

## Goal

The append-only, hash-chained transaction ledger — the "Open Board" — plus deterministic replay and state hashing. This is the foundation every later phase builds on. Zero external dependencies (stdlib only) for maximum determinism and portability.

## Tech Choices

- **Language:** Python 3.13 (agent execution runtime: `/opt/venv/bin/python`)
- **Dependencies:** stdlib only — `hashlib`, `json`, `dataclasses`, `secrets` (seeded). pytest for tests only.
- **Canonical serialization:** JSON with sorted keys, fixed float representation (ints everywhere internally — credits, quantities, timestamps are integer units; no floats in the ledger, ever)

## Repository Layout

```
openboard-economy/
├── src/openboard/
│   ├── __init__.py
│   ├── ledger.py          # Transaction, Ledger, hash chain
│   ├── state.py           # WorldState, canonical serialization, state hash
│   ├── errors.py          # Rejection reason codes (spec §14)
│   └── replay.py          # Replay engine: input log → state hash verification
├── tests/
│   ├── test_ledger.py     # Chain integrity, append-only, rejections logged
│   ├── test_replay.py     # Determinism, fuzzed replay
│   └── test_state.py      # Canonical serialization edge cases
└── pyproject.toml         # Package metadata, pytest config
```

## Tasks

### T1 — Transaction & reason codes
- `errors.py`: rejection reason enum (`UNKNOWN_SENDER`, `INVALID_PAYLOAD`, `RULE_VIOLATION`, ...)
- `ledger.py`: `Transaction` dataclass — `{tick, sender, action, payload, ruleset_version}` (runtime fields only; hash/seq assigned by ledger)
- Verify: unit tests construct/reject transactions

### T2 — Hash chain
- `Ledger.append(tx) → accepted|rejected(reason)`, both outcomes logged (spec §4.1: "failure is transparent, never silent")
- Each accepted record: `seq, prev_hash, tx_hash`; SHA-256 over canonical JSON
- `Ledger.verify_chain() → bool` — full-chain integrity check
- Verify: tamper tests — mutating any record breaks verification; rejected txs appear with reason codes

### T3 — World state & canonical hash
- `state.py`: minimal `WorldState` v0 (tick counter, citizen credit balances map, log of applied actions) — enough to prove the hashing pipeline; economy entities come in Phase 2
- Canonical JSON: sorted keys, no whitespace, integers only → SHA-256 state hash
- Verify: identical states → identical hashes; any mutation → different hash

### T4 — Tick engine (minimal)
- `apply_tick(state, ledger, actions[]) → new_state`: processes one tick's action batch deterministically (fixed action ordering: sort by sender, action type, payload hash — no wall-clock, no randomness unless seeded)
- Accepted/rejected per action; state hash committed after tick
- Verify: same action batch (any input order) → same resulting state hash

### T5 — Replay & determinism fuzz
- `replay.py`: `replay(input_log) → final_state_hash`; compares against recorded hashes per tick
- **Fuzz tests**: seeded pseudo-random action sequences (10k+ actions, 100+ ticks), replay twice → identical; replay after shuffle-equivalent reorder → identical; tamper one input → mismatch detected
- This is the Phase 1 gate

### T6 — Docs & CI hook
- `README` engine section: how to run tests
- Script `scripts/check.sh`: venv python -m pytest -q (single entry point for the gate)

## Definition of Done (Phase 1 gate)

- [ ] All unit tests green
- [ ] Replay fuzz tests green (10k actions, shuffled equivalence, tamper detection)
- [ ] `Ledger.verify_chain()` green on every produced chain
- [ ] Zero floats anywhere in ledger data (enforced by test)
- [ ] No external runtime dependencies

## Out of Scope (later phases)
- Rule-set interpreter (Phase 2), economy entities (Phase 2–4), governance (Phase 5), bots (Phase 7), Cardano adapter (Phase 8)
