# Spec: Proposal Deposit (Election Spam Filter)

**Date:** 2026-09-15
**Status:** SUPERSEDED by 2026-09-15-vote-token.md (founder chose attention-scarcity voting over filing deposits)
**Origin:** Priority 2 study finding + 2026-09-15 rule audit

## Problem

`_apply_propose` (engine.py) accepts unlimited proposals from any citizen:
no deposit, no cooldown, no concurrent-proposal cap. Measured in the
Priority 2 study: ~270 doomed proposals per 650-tick run under open bot
democracy. The ledger survives it; a real game's voting screen will not.

## Evidence

- P2 study: vote_plain arms, all 3 seeds — 270+ proposals filed, near-zero
  passed; every citizen files their own each cycle.
- Code audit 2026-09-15: `_validate_propose` checks sender, payload shape,
  governance enabled, activation window, param validity, constitutional
  guard. No economic cost to propose.

## Design

Add a votable `proposal_deposit` to governance params:

```yaml
governance:
  proposal_deposit: 100   # credits, 0 = off (legacy)
```

Mechanics (all in the propose/resolve paths, integer math):

1. **On PROPOSE:** sender balance must be >= deposit; deduct it at file
   time and hold it on the proposal record (`deposit_held`).
2. **On resolution:**
   - **passed** → full refund to proposer (from held, not minted).
   - **failed** → deposit forfeited to the Society Pool (visible event
     `PROPOSAL_DEPOSIT_FORFEIT`, proposer credited nothing).
   - **withdrawn/cancelled** → full refund (keeps the path open for
     honest re-drafting; a UI withdrawal action may follow later).
3. **Replay safety:** default `proposal_deposit: 0` reproduces legacy
   behavior byte-identically; the baseline ruleset enables 100.
4. **Validation:** deposit must be int >= 0; validate_params already
   guards unknown keys — add `proposal_deposit` to the governance schema.
5. **Determinism:** sorted iteration already used everywhere; no new
   ordering hazards. Conservation: transfer-only (balance <-> pool),
   verified by the existing money invariant in tests.

## Why deposit-forfeit (not cooldown)

- A cooldown punishes *frequency*; bots file ~1 proposal each — the spam
  is distributed, not bursty. A price targets the real cost.
- Forfeit on failure prices reckless proposing; passing still refunds, so
  genuine majority movements are never taxed in net.
- Pool receives forfeits — a tiny deflationary sink consistent with the
  fixed-supply design.

## Tests

1. propose with balance < deposit → PROPOSAL_DEPOSIT_INSUFFICIENT.
2. passed proposal → proposer refunded exactly; pool unchanged.
3. failed proposal → pool credited exactly; proposer out the deposit.
4. deposit 0 (default) → legacy replay byte-identical.
5. money invariant exact across a propose/fail cycle.
6. full suite via memrun.

## Non-goals

- No UI changes in this spec (WebUI voting screen filter is a follow-up).
- No minimum-turnout rules (separate design question).
