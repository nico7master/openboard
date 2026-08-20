# Phase 6 Plan: Oversight (D9)

Goal: automated anomaly detection with public flags, an elected Oversight
Council, and votable interventions — spec §6.4.

## Design

- New rule params (votable, D7/D11 pattern): `oversight` {
  hoard_multiplier (default 3), market_power_share_bp (7000),
  free_rider_min_hours (5), council_members: [] }.
  Council membership is a rule param → elections/removals are ordinary
  rule-change votes; no separate election machinery needed.
- End-of-tick detection `_detect_anomalies` (deterministic, public):
  - HOARD: citizen essential inventory > hoard_multiplier × quota
  - MARKET_POWER: one co-op's listed share of a good > share_bp
  - FREE_RIDER: lifetime labor below free_rider_min_hours while holding
    consumption above a minimal threshold
  Flags persist in state.flags and emit OVERSIGHT_FLAG events
  (radical transparency — dashboards read these).
- `INTERVENE` action (council members only): creates a votable proposal
  carrying an intervention payload instead of params:
  - DISSOLVE_HOARD {target, good}: on pass, excess units above the
    threshold move from citizen inventory to state.common_pool (society
    reclaims hoards); BUY_ESSENTIAL draws from common_pool at floor
    before listings.
  - FINE {target, amount}: on pass, credits move to the surplus pool
    (capped by the target's balance; exact conservation).
  - EMERGENCY_TRIAGE {good}: on pass, appends a ruleset version with
    triage_overrides[good] = "emergency" via the normal activation path.
- Settlement: passed interventions execute at window close; all outcomes
  logged as INTERVENTION_EXECUTED events.

## Tasks

- [x] rules.py: oversight param + validation (incl. council member list)
- [x] state.py: flags, common_pool (+ snapshot/clone)
- [x] errors.py: NOT_COUNCIL_MEMBER, INVALID_INTERVENTION
- [x] engine.py: detection, INTERVENE validate/apply, settlement execution,
      BUY_ESSENTIAL common_pool draw
- [x] tests/test_phase6.py: detection matrix, council gating, all three
      interventions, conservation, determinism
- [x] Phases 1–5 green
