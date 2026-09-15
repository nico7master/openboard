# Spec: Monthly Vote Token — Splitable, Delegable, Revocable

**Date:** 2026-09-15
**Status:** DRAFT — awaiting approval
**Supersedes:** 2026-09-15-proposal-deposit.md (spam is solved by scarce attention, not filing fees)
**Builds on:** D5.3 (linear point-splitting, user preference), D8.3 (delegative democracy, revocable, direct-over-delegate)

## Problem

General RULE_CHANGE votes are unlimited and binary: every citizen can vote
for/against every open proposal, every tick. Measured (P2 study): ~270
doomed proposals per run — the voting surface drowns. The research vote
already solved this shape (100 splitable points + delegation); governance
votes never got the same treatment.

## Design (founder-directed, 2026-09-15)

**Each citizen receives 1 vote token per month. It can be split freely
across proposals (0.5/0.5, 0.1/0.9, ...), or entrusted to a trusted
citizen (delegation), revocable at any time.**

### Mechanics (integer math, basis points)

1. **Token grant:** at every `vote_cycle_ticks` boundary (default 30
   ticks = one month, per the needs_cycle convention) each citizen's
   budget resets to `vote_token_bp` (default 10,000 bp = 1.0 token).
   Unspent budget expires at the boundary (no accumulation — a vote is
   a monthly duty, not a hoardable asset).

2. **Split voting:** `VOTE` payload extended to
   `{"proposal_id", "choice", "bp"}` where `0 <= bp <= remaining
   budget`. Multiple votes per month, each spending budget;
   over-allocation → `VOTE_BUDGET_EXCEEDED`. 100 bp = 10% of a vote.

3. **Tally:** proposal weight = sum of allocated bp. Passes when
   for-weight > against-weight among cast weight. Quorum unchanged
   (citizen-count based, votable).

4. **Delegation (trust):** existing `DELEGATE {"to": citizen|null}` —
   assign/revoke, cycle-safe chains (research `aggregate` machinery,
   generalized). A citizen's unspent budget follows their delegate's
   allocations for the month. **Direct votes always win** (D8.3): bp
   you allocate directly are subtracted from what flows to your
   delegate; delegating does not transfer ownership — revoke anytime,
   effective immediately.

5. **Constitutional guard:** tokens are identity-bound and
   **non-transferable** — "votes cannot be bought, weighted, or
   transferred" (source principle #4). Delegation is trust, never
   payment; no compensation for delegating may ever be votable.

6. **Spam effect:** with 10,000 bp/month and multiple open proposals,
   voters concentrate weight on what matters. Doomed proposals starve
   by attention scarcity. No deposit needed; the deposit spec is
   superseded.

### Replay safety

New optional governance keys `vote_token_bp`, `vote_cycle_ticks`.
Absent → legacy binary votes, byte-identical replay. Baseline ruleset
enables the token.

## Known cleanup folded in

`engine.py` defines `_validate_delegate` twice (lines ~175 and ~295);
the second shadows the first. Merge into explicitly-named validators
(`_validate_delegate_politics`, `_validate_delegate_credit`) as part of
this change.

## Tests

1. Budget enforcement: allocations summing >10,000 bp rejected; exact
   5,000/5,000 and 1,000/9,000 splits tally exactly.
2. Monthly reset: budget restored at cycle boundary; unspent expired.
3. Delegation: delegated weight follows delegate's allocations;
   revocation mid-month immediate; direct allocations override.
4. Chain cycle-safety: A→B→A resolves deterministically.
5. Non-transferability: no action can move tokens between citizens.
6. Legacy replay: without the new keys, byte-identical.
7. Full suite via memrun.

## Non-goals

- No token carryover/accumulation (future votable param if wanted).
- No quorum change, no UI work in this spec.
- No per-proposal minimum weight (starvation handles spam).
