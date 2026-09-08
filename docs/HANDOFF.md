# Handoff: OpenBoard Economy Shipping Month Progress

## What's Been Completed

### Week 1 (Shipping Month Week 1)
- Completed: Hardcore survival gate passed for the first time in the unequal world (top 1% owns 50% of 21M fixed money supply).
- Essentials 0 (bound 0), breadth 15 (bound 30), identical on all 3 seeds.
- Commit e56ec2c.

### Week 2: Harvest
- Proved 18 winnable policy paths from the 50/50 unequal start (wealth tax and dividend combinations that reduce top-1% share while keeping everyone fed).
- 54/54 grid runs (wealth tax 100–1200bp × dividend share 2000–5000bp × 3 seeds) WIN at 1500 ticks:
  - Private top-1 share fell from 50% to ~524bp on every run (gate: <1500bp).
  - Everyone fed: worst essential streak 11 (bound 30).
  - Money invariant exact every tick.
- Deliverables:
  - `scripts/harvest_rerun.py`: resumable unequal-world policy-grid harness.
  - `scripts/harvest_triage.py`: provisional pre-cap heat-card of the 100 banked sweeps.
  - `docs/superpowers/specs/2026-09-07-week2-harvest-findings.md`.
  - `docs/superpowers/specs/2026-09-07-deflation-policy-study.md` (credit velocity as primary votable knob; demurrage as default-OFF Lab rule).
  - Updated `src/openboard/metrics.py` with `top1_share_bp` (private wealth only) + 8 unit tests; consumer suites verified (36 passed).
  - `sweeps/harvest_triage.md` and `sweeps/harvest_triage.csv`.

### Week 3: Multiplayer, Game, Onboarding
- **3.1 Multi-human seats at scale**: 12-seat 1000-tick soak gate PASS:
  - 12 concurrent human seats (more than the 10 required) via the real claim + queue_action path.
  - 25,504/25,504 human actions accepted (100% throughput, zero rejections).
  - Money invariant exact every tick.
  - Essentials fed (worst streak 20 ≤ 30).
  - Wall time 109s.
  - `scripts/soak_seats.py`.
- **3.2 Break-the-System v2**:
  - Timed rounds (200-tick budget), final verdict (damage = flags×100 + worst_unmet×10), persistent leaderboard (top 20).
  - Playable WebUI panel: new 'Break It' tab with playbook picker, attack controls, live scoreboard, verdict screen, and leaderboard table.
  - 5 new API tests; full test suite 425 passed.
  - `src/openboard/breaksystem.py`, `dashboard/server.py`, `dashboard/static/index.html`, `tests/test_attack_api.py`.
- **3.3 Onboarding quest**:
  - Guided first-session quest: watch → enact → observe → adopt (extends the 3-step tour).
  - Progress banner under header tabs with auto-advance hooks (autoplay start = watch, policy adoption = enact/adopt, Chronicle visit = observe).
  - Persisted in `localStorage` (`ob_quest`).
  - `dashboard/static/index.html`.

### Night session 2026-09-08 (WP4.2 perf ladder, byte-identical throughout)
- Measured ladder at pop=966 (`scripts/bench_scale.py`, unprofiled, double-run):
  1.02 → ~1.22 ticks/s (+20%) with zero behavior change:
  - `db608da` record_hash v2 (chaining fields only; content stays committed by
    tx_hash; verify_chain checks both) — +8%; **v2 hash values differ from v1,
    landed inside the pre-anchor window; anchors unaffected (use tx_hash)**
  - `3b1c1c1` per-tick dispatch hoist in apply_tick (was: 20-lambda validator
    dict + 10-entry apply dict rebuilt per tx, ~18k txs/tick) — +9%
  - `d10b572` module-level cached JSONEncoder for canonical_json — ~+2%
- Negative result kept: pure-Python JSON fast path was SLOWER than CPython's
  C encoder (1.07 vs 1.20) — reverted; cached-encoder kept instead.
- Full evidence: `docs/superpowers/logs/2026-09-08-perf-ladder-night.md`.
- Remaining to the ≥5 ticks/s gate (algorithmic, per scaling doctrine):
  batched bot cognition (~30% of profile), market sort bucketing, regional
  markets (structural).

## What Remains (Week 4)

### 4.1 Cardano preprod anchoring live
- Anchor.py v1.5: metadata transactions on Cardano preprod (rules_hash, engine_version, tick_height).
- Verifier script anyone can run to replay from anchor chain and reproduce state hash.

### 4.2 Performance floor
- Engine must handle 1,000 citizens, 300 coops at ≥5 ticks/sec.
- Scale gate: cohort-scaling (stage6 WP7) wired into the dashboard as the 10k-citizen view.

### 4.3 UX final pass
- Hover-only numbers everywhere, story verdicts on every view, tunnel/URL reliability, empty-state screens.
- Goal: 30 minutes of play without asking "what is this?"

### 4.4 Release gate
- Fresh-clone install → run → play end-to-end.
- README; versioned tag v1.0.0; known-issues doc.
- Fresh-store e2e passes from clean state.

## Standing Rules
- Every work package lands with tests + gate; no "done" without evidence.
- Weekly tag: v0.3 (wk1), v0.4 (wk2), v0.5 (wk3), v1.0-rc (wk4).
- Decision save points capture before every rule change (already automatic).

## Next Steps
The next agent should start with Week 4.1 (Cardano preprod anchoring).

---
*Last updated: 2026-09-08 00:05:00 CEST*
