# Human-First Dashboard Redesign — 3-Tab Game
Date: 2026-09-02. Approved by user (plan answer: "yes do that!").

## Problem
1. Policy Lab experiment: 200-tick twin run executes synchronously inside the HTTP request (measured ~4.5 min locally). Through the tunnel, the gateway times out and returns an empty body -> browser shows "Unexpected end of JSON input".
2. Dashboard is organized by engine internals (Engineer, goods tables) instead of the three questions a player actually asks.

## Design: 3 questions, 3 screens

### 1. The World (home, replaces At a Glance)
- Hero: needs-met-over-time chart + inequality chart, full width, big verdict word: THRIVING / STRAINED / CRISIS, color-coded.
- Living Map below as the interactive centerpiece (kept as-is).
- Single alert strip: shows ONLY active problems ("electricity short 6 days"); silent when healthy. Replaces the 6-card story stack.
- Money/Gini/ledger number strip removed; values remain in hover tooltips.

### 2. The Lab (the game)
- Policy knobs as big cards with big option buttons (unchanged data, new presentation).
- ASYNC experiments: POST /api/policy/experiment/start {knob_id, option_id, ticks?} -> {job_id}; a background thread runs fork_experiment; GET /api/policy/experiment/result?job_id= -> {status: running|done|error, result?, error?}. Jobs dict with lock; ticks default 100 for responsiveness.
- UI: button -> "Running two worlds..." progress state with poll loop -> verdict; in-session experiment history ("Your reign: N tried, M adopted").
- Adopt stays synchronous (fast, ledger write).

### 3. The Chronicle
- GET /api/chronicle -> server-derived story feed from state.applied + ruleset_version changes: day-numbered plain sentences ("Day 12 — The electricity crisis began.", "Day 15 — Wealth tax raised.", "Day 20 — Inequality fell.").
- Client renders as a scrollable feed, newest on top.

## Deleted / demoted
- Engineer tab: DELETED. Needs-met + inequality charts move to The World hero. Everything else survives only as hover tooltips.
- World (goods tables) tab: DELETED (Living Map tells the story visually).
- My Seat: demoted to a bottom link "Play as a citizen ->".
- Autoplay: three word buttons Slow / Normal / Fast + big pause; raw seconds slider removed.
- First-visit dismissible 3-step tour: Watch -> Change a rule -> See the outcome.

## Non-goals
- No engine changes, no new frameworks, old worlds unaffected (server-side read-only additions).

## Verification
- Tests: async experiment start/poll/complete, knobs, adopt, chronicle endpoint, verdict words.
- Full suite green; visual verification via screenshots of all 3 tabs; experiment verified end-to-end through the tunnel path (poll loop, no long request).
