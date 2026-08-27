# Stage 5 Implementation Plan

Spec: `docs/superpowers/specs/2026-08-26-stage5-shocks-growth-research.md` · Commit: bac06ab

## Order (blocking fix first)

### 0 · Ratchet root cause + regression test (BLOCKING)
- [x] Ledger-truth probe: who sells machines, who wins auctions, do miners' bids ever fill (probe23)
- [x] Fix root cause in engine/sim per evidence
- [x] Regression test: miner re-acquires machines after fallback within ≤50 ticks, 3 seeds
- [x] Full suite green before proceeding

### 1 · Shock engine (`src/openboard/shocks.py` + rules)
- [ ] Rule block: `shocks = {enabled, profile, rng_seed}`; profiles off/peaceful/standard/harsh/apocalyptic/battery
- [ ] Seeded PRNG event roller, deterministic & replay-safe; SHOCK_START/SHOCK_END ledger events
- [ ] Effects: drought (farm output %), outage (electricity disabled), spoilage (food stock %), machine-failure wave, pandemic (labor reduction → death at severe tier), demand shift
- [ ] Death accounting: balance→surplus pool, inventory→common pool, membership end, CITIZEN_DEATH event; dignity floor (never market-death)
- [ ] Unit tests: PRNG determinism, each effect, death accounting

### 2 · Demographics
- [ ] Births every `birth_interval_ticks` (default 400): new citizen ₡500 minted, CITIZEN_BORN event
- [x] Childhood: consume scaled needs, no WORK until `adulthood_ticks` (default 600); CITIZEN_ADULT event
- [ ] Integration with shock deaths (population drift both ways)
- [x] Tests: birth minting invariant-exact, maturation, drift

### 3 · Research system
- [x] Innovation pool: votable `research_share_bp` of surplus per tick
- [x] Allocation algorithm module (`research.py`): pure function, transparent signals (disease prevalence, unmet-need indices, demand gaps, capacity vs population), publishes proposal + reasoning
- [x] Delegative vote cycle: direct 100-point splits / delegation / abstain-default; revocable delegation; aggregation with cycle detection (→abstain)
- [ ] Within-field split between centers/proposals (same mechanism)
- [x] Funding → research progress → recipe unlock (improved variants, ≤20%/tier); centers led by replaceable people; chronic stall triggers leadership vote
- [ ] Algorithm edit as ordinary PROPOSE/VOTE item; temporary overrides auto-expire
- [x] Tests: signal tracking, delegation aggregation + cycles, algorithm-edit flow, unlock bounds

### 4 · Crisis override
- [x] Declare/end crisis via citizen vote; severe shocks auto-declare subject to ratification ≤100 ticks
- [x] During crisis: priorities suspended, fair-clearing need distribution, emergency research redirection
- [x] CRISIS_START/CRISIS_END events; replay-safe
- [x] Tests: lifecycle, suspension effects, equalization

### 5 · Gate script (`scripts/stage5_gate.py`)
- [ ] Criterion 1: ratchet closed ≤50 ticks, all seeds
- [ ] Criterion 2: escalating battery ×≥2 seeds — honest breaking-tier report; below break: essentials recover ≤100 ticks post-shock; invariant exact; replay byte-exact
- [ ] Criterion 3: peaceful population growth absorbed; pandemic deaths absorbed; children mature
- [ ] Criterion 4: research budgets track injected signals; delegation changes outcomes; algorithm edit takes effect
- [ ] Criterion 5: crisis suspends priorities visibly and ends cleanly
- [ ] Criterion 6: full suite green; old saves replay byte-identical

## Verification
- Every mechanism unit-tested before integration; gate is the final judge
- All new behavior rule-gated (`shocks.enabled`, `demographics.enabled`, `research.enabled`, `crisis.enabled`) so old saves replay byte-identically
- Commit after each numbered section passes its tests
