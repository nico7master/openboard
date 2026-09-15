# 2026-09-14 Entrepreneur Trigger Fix

## Goal
Unblock zero-founding flaw caused by broken trigger semantics (market always has *some* listing, so founding never fires).

## Current Semantics (Broken)
`covered` = {good | listing qty > 0}
Founder triggers on: `unmet_streak >= 5 AND good not in covered`

Result: a single unit listed on a market with 900 unfilled bids still blocks founding forever.

## Proposed Semantics (Surgical Fix)
`covered` = {good | listing qty > 0 AND unserved_bids[good] == 0}

Founder triggers on: `unmet_streak >= 5 AND good not in covered`

`unserved_bids` is an engine-maintained state field (window-independent, window-independent). If significant demand is unfilled, a listing doesn't mask the shortage.

## Changes Required

| File | Line | Change |
|---|---|---|
| `src/openboard/bots.py` | `covered` set (line 652) | Add `and state.unserved_bids.get(g, 0) == 0` to condition |
| `tests/test_entrepreneur.py` | `test_covered_good_ignored` | Update assertion to assert founding (unserved demand > 0) |

## Success Criteria
- Founding fires when capacity gap exists (listings exist but unserved_bids > 0).
- Founding still suppressed if demand is truly met.
- Tests pass.
- No other system behaviors change (uses existing engine field).

## Risk
Low: purely bot-logic change; engine state unchanged. Replay-safe for saves that didn't record founder history (founder state is not persisted).
