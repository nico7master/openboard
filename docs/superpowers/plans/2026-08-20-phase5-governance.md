# Phase 5 Plan: Governance & Constitution (D10)

Goal: rule changes become a democratic process — proposal → campaign
window → vote → activation — with the two-phase constitution and
asymmetric recovery from the spec §6.

## Design

- New actions:
  - `PROPOSE` `{params, activation_tick}` — opens proposal `pN` with a
    vote window `[tick+1, tick+vote_window_ticks]`. `activation_tick`
    must be after the window closes. Counter-based deterministic IDs.
  - `VOTE` `{proposal_id, choice}` — choice ∈ {"for", "against"}.
    One ballot per citizen per proposal (constitutional core #4).
  - `ROLLBACK` `{target_version}` — proposal that restores the params of
    a prior rule-set version; marked `is_rollback`.
- Settlement at end of each tick: closed proposals are tallied
  deterministically.
  - Quorum: `quorum_bp` of all citizens must have cast (default 50%).
  - Pass: strict majority of cast votes. Tie → fail (status-quo bias).
  - Hardened constitution (`constitution_phase: "hardened"`): ≥ 2/3 of
    cast votes required.
  - Asymmetric recovery: rollback within the trial period of the active
    version passes with simple majority, even hardened.
  - Passed → append a RuleSetDoc activating at `activation_tick` (same
    mechanism as RULE_CHANGE today; version pinning unchanged).
- Bootstrap story (D10 two-phase): `RULE_CHANGE` remains the instant
  mechanism while `governance.enabled` is false (simulations, tuning).
  The last unchecked change enables governance; from then on RULE_CHANGE
  is rejected (GOVERNANCE_LOCKED) and all change flows through votes.
- The five constitutional invariants (ledger integrity, transparency,
  the process itself, one person one vote, cost accounting) are
  structural engine properties — not expressible as rule params, so no
  vote of any size can touch them.
- New rule params (all votable): `governance` {enabled, vote_window_ticks,
  quorum_bp, trial_period_ticks}, `constitution_phase` ("bootstrap"|
  "hardened").

## Tasks

- [x] rules.py: new params + validation (bootstrap values, hardened rules)
- [x] state.py: proposals store, constitution_phase, next_proposal_id;
      serialization + clone + hash coverage
- [x] errors.py: new Reason members
- [x] engine.py: PROPOSE / VOTE / ROLLBACK validators + appliers;
      proposal settlement after market clearing; RULE_CHANGE gating
- [x] tests/test_phase5.py: lifecycle, one-vote enforcement, quorum,
      majority/tie, hardened 2/3, in-trial rollback, RULE_CHANGE lock,
      version pinning, determinism fuzz with governance on
- [x] Gate: constitutional attack campaign — faction pushes self-serving
      rule (blocked by 2/3), double-voting rejected, rollback restores
- [x] Phases 1–4 tests stay green

## Verification

- [x] Full suite green
- [x] Attack campaign green
