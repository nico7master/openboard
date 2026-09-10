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
  **1.02 → 1.34 ticks/s (+31%)** with zero behavior change (6 perf commits):
  - `db608da` record_hash v2 (chaining fields only; content stays committed by
    tx_hash; verify_chain checks both) — +8%; **v2 hash values differ from v1,
    landed inside the pre-anchor window; anchors unaffected (use tx_hash)**
  - `3b1c1c1` per-tick dispatch hoist in apply_tick (was: 20-lambda validator
    dict + 10-entry apply dict rebuilt per tx, ~18k txs/tick) — +9%
  - `d10b572` module-level cached JSONEncoder for canonical_json — ~+2%
  - `e6f1460` skip no-op sort of 0/1-element recipe lists in _apply_work — +6%
  - `98602e2` personal_needs: hoist loop-invariant demand_memory params,
    reuse triage lookup — +2%
  - `f66dfb2` _consume_phase: hoist needs order + demographics import out of
    the per-citizen loop — +2%
- Negative result kept: pure-Python JSON fast path was SLOWER than CPython's
  C encoder (1.07 vs 1.20) — reverted; cached-encoder kept instead.
- Measured attribution CORRECTION: market clearing itself made only 199
  sorted() calls per 6 ticks — sort bucketing there is a dead end; the real
  volume is per-citizen work (sim.py 35,341, _apply_work 12,138).
- Full evidence: `docs/superpowers/logs/2026-09-08-perf-ladder-night.md`.
- Remaining to the ≥5 ticks/s gate (algorithmic, per scaling doctrine):
  **batched bot cognition** (~30% of profile — next lever), then structural
  regional markets.

### Fidelity rung measured (2026-09-08 night, `9f388c9`)
- **Equity transfers across population**: 181-citizen unequal world vs banked
  986-citizen harvest run, same law (tax0400 × div3000), 1500 ticks: top-1
  trajectories near-identical (≤5bp apart after t=100, both end 524bp).
  First measured rung of the billions ladder.
- **Stability is roster-sized**: the default 181-world starves (bread+meals
  unmet for all 181, worst streak 1499, zero listings) while the 986 world
  feeds everyone — `scale_world`'s coop cloning is what repairs it. Coop
  counts per-capita are already adequate at 181, so the gap is per-coop
  labor/chain depth, NOT coop counts — **open thread: diagnose why the 2
  flour_to_bread + 1 meal_service coops produce nothing at 181** (labor
  staffing? upstream flour/energy?). essentials_diag.py / fast_diag.py are
  the tools.
- Cohort-K world proven denomination-only (delta=0 vs 1:1) — surrogate
  claims need reduced AGENTS with proportionally REBUILT rosters.
- Evidence: `sweeps/fidelity_181_verdict.json`, probes
  `scripts/cohort_fidelity.py` + `scripts/fidelity_181.py`.

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


## Session Snapshot 2026-09-08 ~15:45 CEST (mid-day)

### Landed this session (after the overnight summary above)
- fix(sim) b31b47e: int-cast BID_FOR_COOP qtys (3rd float-poisoning occurrence) - food chain alive at 181
- docs 050beeb: refreshed fidelity verdict - equity AND stability transfer 181<->986
- perf 288a98a: bid bucketing per good (byte-identical, ~neutral at 966)
- fix(engine) 8e64665: VWAP-branch durable division - THE float source (4th occurrence).
  Trap-probe: zero float baseline writes; post-t6 state fully int (was 6 baselines,
  181/181 balances, 4 treasuries, pool all floats). Full suite 425 passed after fix.
- perf(bots) a07495b: triage-override hoist in personal_needs (byte-identical vs HEAD)
- gate diagnostics add85e5: worst_streak now prints tick, citizens, per-good histogram

### OPEN: 966-citizen gate FAILS on stability with the float fix IN
- Run 1 (pre-float-fix): FAIL worst_streak=379, inv_bad=0, wall 1697s, rss 1327MB
- Run 2 (float fix in, diagnostics added): FAILING WORSE - streak 248@t250, 498@t500
  (pre-fix was 157@250, 118@500). Hypothesis REJECTED that float bug alone caused it.
- The float fix changed economics: clean integer floors now bind differently; buyers
  who previously over-paid float floors now pay exact int floors; something starves
  at scale. WAIT for final worst_streak_detail in /tmp/scale_gate_floatfix.log.
- 181-world under same policy is PERFECT (streak 13, 0 unmet, equity 519bp).
  => scale-specific starvation: coop-cloning (scale_world) + D18 mobility +
  producer_input_priority interplay suspected. Needs the offender detail + a
  fast_diag-style probe at 966 with per-good unmet tracking.

### Next steps (priority order)
1. Read /tmp/scale_gate_floatfix.log final worst_streak_detail -> identify starving
   goods/citizens at 966.
2. Probe: 300-tick 966-world run with per-good unmet tracking + BID/BUY_ESSENTIAL
   reject reasons (INVALID_QTY vs INSUFFICIENT_FUNDS vs NOTHING_LISTED).
3. Fix the starvation mechanism, re-gate. THE GATE IS THE BLOCKER for WP4.2.
4. Batched cognition (spec drafted, sub-steps 1-2 in progress) - perf lever, after gate.
5. Anchor verifier (scripts/verify_anchor_chain.py) - independent of gate, defer.

### Working state
- HEAD a07495b, worktree clean, all 425 tests green, no stale processes.
- bench at 966: ~1.23-1.31 ticks/s (needs >=5 for gate; structural work pending).


### UPDATE 2026-09-08 18:25 CEST - 966 gate collapse ROOT-CAUSED + fixed
- Incident: two A0 backend freezes caused by my bare probes; brief + memrun.sh
  committed (4f3e4b9); project instructions hardened (never bare, one world
  process, per-tick applied.clear, wait-then-relaunch). ALL probes now via memrun.
- Gate FAIL root cause: scale_world clones coops with treasury+pantry but NO
  capital -> cloned power coops spawned 0 machines (base has 2) -> grid trickle
  -> total electricity collapse t=955 (966/966 unmet; water 650, bread 68).
- FIX 9a7d5da: clones inherit CAPITAL_BOOTSTRAP goods of their base coop
  (verified: power_plant_x1/x2 spawn machines=2; 16 capital injections).
- Official gate re-running via memrun (/tmp/scale_gate_bootstrap.log).
  PASS criterion unchanged: inv_bad=0, worst_streak<=50, wall<=7200s, rss<=8192MB.


### UPDATE 2026-09-10 16:30 CEST - WP4.2 stability ladder: 953 -> 73, residual = machine chain

Gate verdict ladder (all via memrun, solo, seed 42, 2000 ticks, 966 citizens):
| Run | Fix | worst_streak | Failure detail |
|---|---|---|---|
| 1 (pre-float-fix) | - | 379 | no diagnostics |
| 2 (float fix 8e64665) | int VWAP division | 96 @t141 | electricity 436 + bread (founding) |
| 3 (+capital bootstrap 9a7d5da) | clones get machines | 156 @t489 | water 854 + elec 479 (mid-ramp) |
| 4 (+full base inventory) | clones inherit base working stock | 53 @t100 | bread, 6 citizens (ramp edge) |
| 5 (+ramp pantry 60/40/40) | launch reserve | 73 @t1975 | ELECTRICITY 566 (late stochastic dip) |

Steady state is PROVEN clean in runs 4-5 (checkpoint streaks 0-26 through t=2000;
inv_bad=0 always; wall ~1100s; rss ~1GB). The residual failure mode: the scaled
electricity grid (6 power coops, 42 members, 2 machines each, durability 20) sits
AT capacity; stochastic transients (machine wear refresh + coal delivery jitter)
tip multi-tick dips of 500+ citizens. Coal piles up unburned (24k) because
production is machine-limited, not fuel-limited.

NEXT (structural, fresh session recommended): machine-chain throughput at scale -
(1) probe machine_works clone production + machine refresh rate vs wear rate;
(2) options: more machine_works cloning weight, higher per-coop machine stock
bootstrap, or D19-style join-into-understaffed-essential-coops mobility.
Per scaling doctrine this is the capital-goods stage throttle; regional markets
(sect 3) is the eventual structural answer.

All five gate logs banked in sweeps/. Discipline held: every run via memrun,
solo, per-tick applied.clear. HEAD 794a2c1 + pantry/inventory patches uncommitted
(check git status).


### UPDATE 2026-09-10 17:00 CEST - machine-chain probe: BOOM-BUST grid confirmed

mach966 probe (died at cap rc=1 — ledger.records grows even with applied.clear;
next probe must call trim_retention per tick too; pre-death data valid, banked in
sweeps/mach966_boom_bust_evidence.log):
- machine chain at 966: THREE coops (machine_works 3 mem, _x1 11 mem, _x2 2 mem)
- electricity unmet OSCILLATES: 465 -> 325 -> 442 -> 433 -> 0 -> 0 -> 444
  (boom-bust cycle, not monotonic decline) - matches gate5 t=1975 stochastic dip
- machine stock piles up 538 -> 4,699 across windows; wear_total stays 184-312
- probe bug to fix next time: mach_prod counted PRODUCE in applied[-20000:] AFTER
  per-tick clearing, so it only saw the last tick (always 0). Count within the
  drive loop per window instead.

NEXT SESSION (priority): structural capital-chain fix at scale. Options measured
against doctrine: (a) scale_world should clone machine_works with MORE weight
(capacity-per-member is the throttle), (b) raise per-coop machine stock bootstrap,
(c) D19 join-only routing into understaffed machine/power coops (genesis all
seated, so only demographic adults or migration can rebalance), (d) votable
max_coop_members raise. Boom-bust damping (inventory smoothing on machine
delivery) may be cheaper than capacity growth - measure first.

Performance state: ~1.3 ticks/s at 966 (gate needs 5) - batched-cognition spec
+ regional markets (doctrine sect 3) remain the ladder. Gate evidence ladder
953 -> 96 -> 156 -> 53 -> 73 banked in sweeps/ with logs.
