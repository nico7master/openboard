# Implementation Plan — Phase 2: Rules-as-Data + Entities

**Date:** 2026-08-20
**Spec:** `docs/superpowers/specs/2026-08-19-openboard-economy-engine-design.md` (§4.2, §4.3, §12 Phase 2)
**Gate:** version pinning tests green + all Phase 1 tests still green

---

## Goal

The D7 machinery: rule-sets as versioned data on the ledger, rule changes as transactions, and version pinning — every transaction executes under the rule version historically active at its tick, and replay applies exactly those versions. Plus the economic entities as state: the goods catalog (39 goods with triage flags per D8), starter recipes (data only — execution is Phase 3), and worker cooperatives (found/join; production is Phase 3).

## Design Decisions

- **RuleSet = complete document**: each version carries the full parameter set (git-commit style snapshots, no partial merges). Required keys: `transfer_limit`, `max_coop_members`, `min_coop_members`, `triage_overrides`.
- **Activation model**: `RULE_CHANGE` payload `{params, activation_tick}` with `activation_tick > tx.tick` (strictly future — no retroactive changes, determinism preserved). Genesis version 1 activates at tick 0. If two versions activate at the same tick, the higher version number wins (versions assigned in deterministic processing order).
- **Explicit pinning**: every transaction declares `ruleset_version`; the engine rejects a mismatch with the tick's active version (`RULESET_MISMATCH`). Replay cannot silently shift which rules a tx ran under.
- **Triage via rules (D8)**: effective triage = `triage_overrides.get(good, goods[good].triage)` — triage flags become votable through the generic rule-change mechanism from day one.
- **Founding-era rule changes**: in Phase 2 any citizen may submit rule changes directly (bootstrap phase per D10); the voting machinery itself arrives in Phase 5 and will gate this action.
- **One citizen, one co-op** for v1 (join requires leaving none implicitly; a `LEAVE_COOP` action is deferred — founding-era simplicity, revisitable as a votable rule later).
- **Spec fix**: §13.1 header said 32 goods; the table lists 39. Correcting the spec to 39.

## New Reason Codes

`RULESET_MISMATCH`, `INVALID_RULESET`, `ACTIVATION_IN_PAST`, `COOP_EXISTS`, `NOT_A_MEMBER`, `ALREADY_IN_COOP`, `COOP_NOT_FOUND`, `COOP_FULL`, `COOP_TOO_SMALL`

## Tasks

### P2-T1 — `rules.py`
- `RuleSetDoc {version, params, activated_at, change_tx_hash}`; `DEFAULT_RULESET_PARAMS`
- `validate_params(params, known_goods) -> Reason | None` — schema: all required keys, ints ≥ 0, `triage_overrides` maps existing goods → valid triage values
- `active_version(rulesets, tick) -> int` — latest activated_at ≤ tick; ties → higher version

### P2-T2 — `catalog.py`
- 39 goods: id → {category, triage, unit}; essentials per spec (all food, housing, water, healthcare, electricity, heating); medicine + transport = market with emergency escalation; rest market
- ~20 starter recipes: {inputs: {good: qty}, labor_hours, energy, outputs: {good: qty}} — integer quantities only; recipes reference existing goods only (test-enforced)

### P2-T3 — `state.py` extension
- State grows: `labor_hours`, `goods`, `recipes`, `coops`, `rulesets` (full version history), `ruleset_version` (active at current tick)
- `genesis_state(citizens, goods=None, recipes=None, ruleset_params=None)` — None → catalog defaults; backward compatible with Phase 1 signature
- Snapshot + state hash cover all new sections (same hashing contract)

### P2-T4 — `engine.py` actions
- Tick flow: compute active ruleset version for the tick **before** processing; stamp state
- `TRANSFER` — now consults `transfer_limit` (0 = unlimited)
- `RULE_CHANGE` — validate schema + strictly-future activation; accept → new version recorded in state with provenance tx hash
- `FOUND_COOP` {coop_id, name, members[]} — sender must be member; all members citizens and co-op-free; size within [min, max] rule params
- `JOIN_COOP` {coop_id} — sender co-op-free, coop exists, not full

### P2-T5 — Version pinning tests (THE gate)
- transfer_limit change activating at tick N: same 500-credit transfer accepted tick N−1, rejected tick N — and replay reproduces both
- Declared `ruleset_version` mismatch → `RULESET_MISMATCH`
- Activation in past → rejected; activation in future → rejected until active
- Two versions, same activation tick → deterministic winner, replay-stable
- Triage override (medicine market → emergency) via rule change — effective triage queryable, replay-stable

### P2-T6 — Entity & catalog tests
- FOUND_COOP/JOIN_COOP happy paths + every rejection reason
- Catalog integrity: 39 goods, valid triage values, recipes reference known goods, all quantities positive integers
- Co-op size limits enforced from rule params (changing the param changes the behavior — rules demonstrably drive entities)

### P2-T7 — Fuzz gate extension
- Mixed-action fuzz: TRANSFER + RULE_CHANGE + FOUND_COOP + JOIN_COOP, seeded
- Determinism, shuffle equivalence, replay match, tamper detection — all with dynamic rules in the history
- Credit conservation still holds (rule/coop actions never mint credits)

## Definition of Done (Phase 2 gate)

- [ ] Version pinning battery green (P2-T5)
- [ ] All Phase 1 tests still green
- [ ] Mixed fuzz with dynamic rules green
- [ ] Catalog integrity tests green
- [ ] No floats in any chain/state data (test-enforced)

## Out of Scope (later phases)
- Production execution of recipes (Phase 3), markets/auctions (Phase 4), voting on rule changes (Phase 5), oversight (Phase 6), bots (Phase 7), Cardano (Phase 8)
