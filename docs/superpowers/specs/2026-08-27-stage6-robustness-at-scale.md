# Stage 6 — Robustness at Scale (spec)

Date: 2026-08-27 · Status: APPROVED (user) · Roadmap ref: 2026-08-22-world-takeover-roadmap.md §6

## Goal
Chart the **stability region** of the OpenBoard economy at the scale the game and
real world will actually run: **1,000 citizens**. Success criteria:
1. 1k-citizen science runs complete in budget (≤2 h wall-clock for 2,000 ticks, ≤8 GB RAM, solo).
2. Game fast-forward sustains ≥5 ticks/sec at 1k citizens (auto-flow time-lapse; user speeds up/slows down/intervenes).
3. A coarse parameter sweep at 1k citizens produces a stability map (green/yellow/red per knob combo), browsable in the dashboard God View.
4. Fine sweeps zoom into the collapse cliffs identified by the coarse map.
5. Determinism is never sacrificed: same seed → byte-identical ledger, at any optimization level.

## Design decisions (user-approved)
- **D6.1 Scale first** (A): the stability region is charted at 1k citizens; a 160-citizen chart would be a rough draft.
- **D6.2 Two-tier performance budget** (C): science batch target + game watchable-speed target. The game is a **time machine** — the world auto-flows, the player controls playback speed and intervenes on alerts; not per-citizen control.
- **D6.3 Staged sweeps** (C): coarse map first (wide & shallow), then fine passes around the map's edges (cliffs).
- **D6.4 Cohort scaling in scope** (B): the strategic goal is country/world scale ("one country implements it, then the world adopts via public ledger receipts"). Full-fidelity 8B simulation is impossible; the aggregation ladder is: full fidelity (1k) → weighted cohorts (1k agents × K real people) → regional hierarchy → statistical emulator → **the real deployment IS the simulation** (no world sim needed; adoption scales by trust in the verifiable ledger). Rungs 3-4 (regional hierarchy, emulator) are planned as a later stage (user-approved).

## Work packages

### WP1 — Performance floor (before any science)
- Profile a 1k-citizen run: identify per-tick hotspots (expected: O(n²) auction scans, per-tick state copies, per-citizen unmet recomputes).
- Optimize only where the profile says; **every optimization must pass**: existing 289-test suite + byte-identical replay of a fixed 500-tick reference run.
- Budget guard: a perf test asserts 1k×500-tick completes under the science budget on the reference machine; skipped if env flag absent.

### WP2 — Scale gate
- `stage6_scale_gate.py`: 1,000 citizens × 2,000 ticks × 3 seeds, endowments ON (genesis-scaled), solo run.
- Criteria: money invariant exact every tick; essentials streak ≤ 50 ticks post-genesis (matching the Stage 5 battery bound); wall-clock ≤2 h; peak RSS ≤8 GB.

### WP3 — Coarse sweep (the map)
- Knobs (votable rules, coarse grid ×3 values): wealth_tax rate_bp, labor_pool_cap, surplus share-out %, capital backstop interval, birth interval.
- 3^5 = 243 combos × 3 seeds × 500 ticks at 1k citizens. Batched overnight; resumable state file (`sweeps/state.json`), one result JSON per combo.
- Per-combo verdict: stable / degraded / collapsed (essentials streak, Gini, invariant, pop survival).
- Sequential execution (32 GB RAM, solo discipline); ETA documented before launch.

### WP4 — Cliff zoom (fine passes)
- Pick the 2 axes with the sharpest stability→collapse transition on the map; 7–10 values each × 5 seeds × 1,500 ticks.
- Output: cliff coordinates + failure-mode classification (which flag fires first at collapse).

### WP5 — Dashboard stability heat-card
- New God View tab: parameter grid, green/yellow/red cells; click a cell → summary of that run (charts of key metrics); full replay via existing loader.
- Data source: `sweeps/*.json` (server reads the directory).

### WP6 — Shock × scale interaction
- Battery (peaceful→apocalyptic) at 1k citizens × 2 seeds. Question: does 'fatal' still hold at scale? Report honestly like Stage 5's battery.

### WP7 — Cohort scaling (world-path bridge)
- Each simulated agent optionally carries `cohort_k` (representing K real people); weights flow through needs, labor, consumption, surplus, and Gini as weighted quantities; money invariant checked on weighted totals.
- Verification: 1,000 agents × K=100 (=100,000 "people") × 500 ticks × 2 seeds — stable essentials, exact weighted invariant, within science budget. Compare K=1 vs K=100 dynamics on one seed for divergence accounting (expected: identical per-agent decisions, scaled flows).

## Non-goals
- No multiplayer/network code (Stage 7+).
- No regional hierarchy or statistical emulator (rungs 3-4) — planned as a later stage per D6.4.
- No new economic rules; Stage 6 measures the rule space, doesn't extend it.
- No chain anchoring (Stage 7).

## Risks & mitigations
- **OOM at 1k citizens**: solo runs only; RSS logged per 100 ticks; runs checkpoint every 250 ticks (crash-resume without losing hours).
- **Sweep wall-clock blowup**: if per-run cost × 243 combos × 3 seeds exceeds a week, reduce to the top-3 knobs first (per priority order documented) and mark the rest backlog.
- **Determinism drift from optimization**: byte-identical replay test is the tripwire; any diff = revert the optimization.

## Verification
- WP1: suite + replay byte-check + perf assertion.
- WP2: scale gate PASS printed + committed log.
- WP3/4: sweeps/ JSONs + dashboard heat-card rendering correct (smoke test).
- WP6: battery report committed next to the scale gate log.
- All plans ticked; roadmap doc updated with the charted region summary.
