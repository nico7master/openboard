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

## Session 2026-09-11 (late): Lever Atlas campaign + research conservation fix

**Lever Atlas COMPLETE (81/81 runs)**: scripts/atlas_grid.py (harness, 6651a4e),
sweeps/atlas/ (81 JSONs + ATLAS.md playbook, aec8e9c + correction d6869f7).
Grid: L1 interest x L2 scarcity cap x L3 research share (3x3x3) x 3 seeds,
600 ticks, on the proven tax400/div3000 baseline.

**Findings:**
1. ENGINE BUG (fixed b3850a7): allocate_fields_phase destroyed the
   floor-division remainder each tick (-1..-17 credits/tick at 500bp).
   Found because atlas inv_bad flags fired research-ON only. Post-fix diag:
   inv_bad=0. research_funding bucket now ALSO in atlas money_delta.
2. BEHAVIORAL (stands, corrected verdicts in ATLAS.md): research is a
   luxury lever — 0bp: 27/27 WIN; 250bp: 21/27 (200+-tick essential
   starvation on some seeds); 500bp: 0/27. Interest + scarcity cap:
   no effect on win rate (9/27 WIN each level, driven by research=0 rows).
3. Harness lesson banked: money identity in sweep harnesses must cover ALL
   state buckets (research_funding was added late; state.py owns truth).

**Next (in order):**
1. Regional-markets perf fix (root-caused 2026-09-10, b369105): run the
   producer-input-priority pass ONCE city-wide BEFORE regional citizen
   passes (engine.py:1487-1610 pip block vs _clear_markets_regional:1323).
   Then median re-bench (ON was 0.43-0.49 vs OFF 1.77 t/s).
2. Lever B batched cognition (equivalence baseline locked: state 64f53098,
   head 1afc6809, outcomes f887fe3213fff3d0).
3. Rust/pyo3 decision on ledger path (~40% of tick) if still <5 t/s.
4. UX pass, release docs, fresh-clone e2e, tag v1.0.0.

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


### UPDATE 2026-09-10 17:00 CEST - DELIVERY-PATH DIAGNOSIS COMPLETE: AFFORDABILITY GAP

machflow966 probe (500 ticks, banked in sweeps/machflow966_affordability_gap.log):
- t=80-230: power coops issue ZERO machine bids (ok=0 rej=0) while auctions sell
  machines at ~5,500-5,700cr and machine_works stock piles 184 -> 601
- t=280+: first bids appear, but 26/28+ rejected INSUFFICIENT_FUNDS - power coop
  treasuries (~500-32k but consumed by wages/energy) cannot cover ~5,600/machine
- power_stock pinned at 6 machines total across 6 power coops (2/coop); the grid
  oscillates boom-bust on that thin, non-replenishing capital stock

ROOT CHAIN (complete): cloned power coops start with 2 machines (fixed), wear
them (1 per 20 runs per coop), and CANNOT REBUY because the machine price
(~5,600 = amortized labor at scale) exceeds what a small power coop can save
while paying wages+energy. The auction has sellers and demand intent, but the
price floor of a capital good exceeds small-coop affordability -> no flow ->
boom-bust on remaining stock.

NEXT SESSION (fresh context recommended): capital-goods affordability at scale.
Options measured against doctrine + D18/D19: (a) credit union rule (exists,
votable) extended to machine purchases for essential-chain coops; (b) capital
fund / society-funded machine grants to understaffed essential coops (capital_rent
already charges society for machine use - recycle it into replacement grants);
(c) machine-leasing coops (rent per run instead of ownership); (d) price floor
reform for capital goods (amortized-per-run sale units). Measure (b) first -
the capital_rent pool already exists and recycles exactly this value.

Also noted: probe shows elec_unmet=0 for long stretches THEN 387 at t=330 -
the boom-bust is real and matches gate5's t=1975 dip. Fixing affordability
should collapse the oscillation amplitude.


### UPDATE 2026-09-10 17:00 CEST - DELIVERY-PATH DIAGNOSIS COMPLETE: AFFORDABILITY GAP

machflow966 probe (500 ticks, banked in sweeps/machflow966_affordability_gap.log):
- t=80-230: power coops issue ZERO machine bids (ok=0, rej=0) while auctions
  sell machines at ~5,500-5,700cr and machine_works stock piles 184 -> 601
- t=280+: first bids appear but 26/28 rejected INSUFFICIENT_FUNDS - power coop
  treasuries (drained by wages+energy) cannot cover ~5,600/machine
- power_stock pinned at 6 machines total across 6 coops (2/coop, never
  replenished); the grid oscillates boom-bust on this thin stock

ROOT CHAIN (complete): cloned power coops start with 2 machines each, wear
them (1 per 20 runs per coop), and CANNOT REBUY because the machine price
(~5,600 = amortized labor at scale) exceeds what a small power coop can save
while paying wages+energy. The market has supply AND demand intent, but the
affordability gap means NO FLOW -> boom-bust on the remaining stock.

NEXT SESSION (structural fix, measure first): capital-goods affordability at
scale. Options measured against doctrine + D18/D19: (a) credit union rule
(exists, votable) extended to machine purchases for essential-chain coops;
(b) society-funded machine replacement grants from the capital_rent pool
(the pool already charges society for machine use and recycles exactly this
value - measure its balance first); (c) machine-leasing coops (rent per run
instead of ownership); (d) price-floor reform for capital goods (amortized
per-run sale units instead of lump-sum ownership). Option (b) is the
doctrichest fit: capital_rent already exists and already recycles society-paid
machine costs.

Also: the boom-bust oscillation (elec_unmet 0->0->0->0->0->387) means the
replacement flow just needs to EXCEED the wear rate to stabilize the grid -
a small targeted fix (not a redesign) should close the gate.

Performance state: ~1.3 ticks/s at 966 (gate needs 5) - batched-cognition
spec + regional markets (doctrine sect 3) remain the ladder. Gate evidence
ladder 953 -> 96 -> 156 -> 53 -> 73 banked in sweeps/ with logs.


### UPDATE 2026-09-10 19:20 CEST - WP4.2 STABILITY GATE: PASS

gate_refresh2 (HEAD+2 fixes): GATE: PASS - inv_bad=0, worst_streak=48 (<=50),
wall=1082s, rss=937MB, pop=966, 2000 ticks. Worst detail: t=1118, 465 citizens
water (mid-run dip, recovered by t=2000: streak=2).

The complete fix chain (ladder 953 -> 96 -> 156 -> 53 -> 73 -> 48 -> PASS):
1. 8e64665 float-poisoning repair (VWAP durable division int-native)
2. 9a7d5da clones inherit CAPITAL_BOOTSTRAP
3. full base-inventory inheritance (stage6_scale_gate.py)
4. ramp-sized launch pantry 60/40/40
5. THE DESIGNED LOOP ENABLED: capital_refresh ON in scale_world
   (interval 10, tools 2, machines 2/coop) - society charges capital_rent
   per machine-use into capital_fund and recycles it into replacement
   stock ('public capital, private use'). Probe-verified: power machines
   6 -> 150, elec_unmet 0 at t=400.
6. (this commit) retirement accounting fix: _capital_refresh_phase must
   record money_retired += cost ALWAYS - the money_cap skip left the fund
   deduction unaccounted (money_delta -127,500 at first refresh). At 181
   the rule ships OFF so the bug never fired before.

Performance (2026-09-10 evening, pinned 2-core nice-19 harness - CPU
holdback now mandatory via memrun, commit 1938be3): ladder 1.46 -> 1.52
-> 1.51 -> 1.74 ticks/s at 966 via Patch A 3d4253d (per-tick
coop-membership map + params hoists), Patch B 3e06b66 (per-tick listing
aggregate caches), and ledger record_hash v3 (concat encoding, spec
2026-09-10-ledger-record-hash-v3). A+B proven byte-identical by
30-tick fingerprint A/B (96d0e0fa91804b61 / SEQ_SHA f732931b9f938ef1),
both 425-green. v3 proven STATE-EQUIVALENT (hash VALUES change by
design, pre-anchor window): FINAL_STATE_HASH + outcomes multiset
identical over 30 ticks / 509,843 records, verify_chain True, 425
green; micro-bench 2.68x on the record-hash input. Post-patch
profile: apply_tick 78% of tick (ledger hash chain ~19k records/tick x2
canonical_json + clearing sorts 53k calls); cognition done (~16%).
Next levers are STRUCTURAL and need their own reviewed specs: regional
markets (doctrine sect 3) and ledger record batching (merkle per tick,
pre-anchor window). Full-suite pinned cap is 6 GiB (RLIMIT_AS, not
RSS - 2 GiB dies mid-import). The stability half of WP4.2 is DONE.

Realism contracts (2026-09-11, spec 2026-09-11-policy-realism-contracts.md,
user-approved target: every policy lever must reproduce its real-world
EFFECT - direction/mechanism/magnitude/flip - gate-enforced by tests):
- L1 interest on loans LANDED 15b3e4c: rate_bp_annual (default 0 = old
  worlds replay identical), simple declining-balance interest (1 tick =
  1 day) to the surplus pool, crisis origination locks 0% (solidarity
  credit), charge-off freezes accrual at due_tick, REPAY now settles only
  when FULL owed (principal + interest) is paid. 5 contract tests in
  tests/test_realism_loans.py; full suite 430 green.
- L2 scarcity pricing LANDED 430fb1e: engine-set premium (scarcity_signal
  bp of floor) from economy-wide unmet bid volume - NOT seller-set;
  tick-scoped listings re-justify it every tick; essentials pass clamps
  to floor (need-first); crisis forces signal 0 (anti-gouging); rule off
  = byte-identical. Optional param scarcity_pricing {enabled, max_markup_bp
  2500, step_bp 500, decay_bp 250}, strict validation. 8 contract tests in
  tests/test_realism_scarcity.py; full suite 438 green. Both pushes
  verified on origin/master.
- Lessons for next contract levers: (1) listings are TICK-SCOPED - assert
  prices via direct _apply_list_good, flows via full apply_tick; (2) list
  + bids must be ONE apply_tick batch; (3) ledger suppresses DUPLICATE
  payloads per tick (silent reject) - vary max_price per tick; (4) check
  affordability validator (price x qty vs balance) in test worlds.
- Remaining: L3 research->productivity (research.py has ZERO engine call
  sites today - wire field allocation to output bonuses + variant recipe
  unlocks; user's two-layer voting design in memory), L4 land, L5 foreign
  sector (week-scale, own specs). Perf note: L2 adds one dict update per
  good per tick (negligible); regional-markets perf spec still pending.
- L3 research->productivity LANDED 844ff19 (the deepest gap: research.py
  had funding but ZERO engine effect - a stationary economy):
  * allocate_fields_phase: innovation_pool -> cumulative per-field
    know-how buckets (research_funding), allocation = published
    algorithm's proposal (abstain-default of the two-layer design);
    crisis_field_override redirects 100% to the crisis field
  * research_effect_bp: +250bp output per 10,000cr field know-how,
    capped +2500bp (+25%), composed into _apply_produce's out_mult_bp
    alongside skills (integer-only)
  * variant unlocks: crossing unlock_threshold (default 50k) per field
    unlocks next tier of that field's first alphabetical recipe
    (unlock_variant, -5%/tier inputs, min-1 floor, <=20% cap) - new
    recipes {rid}_v{n} appear in state.recipes (bots can adopt them;
    adoption pressure is future work)
  * state: research_funding/research_unlocked (absent-when-default hash
    compat); money conservation bucket-to-bucket (surplus -> pool ->
    know-how; know-how is an ACCOUNTING bucket, not spendable money)
  * ENGINE FIX: pipeline research hook errors now append a schema-valid
    OVERSIGHT flag (kind+target) - the previous silent-swallow pattern
    violated the 'nothing fails silently' rule; flag schema requires
    target (oversight reads f['target'] on every flag)
  * 7 contract tests in tests/test_realism_research.py; full suite 445
    green. Research param validation block still ABSENT (validate_params
    tolerates unknown keys; add when dashboard exposes research voting).
- Realism backlog remaining: L4 land (fixed location stock, ownable,
  rentable - structural inequality), L5 foreign sector (external
  price-taker market, terms-of-trade shocks) - each needs its own
  reviewed spec (week-scale). Variant ADOPTION by bots is a small
  follow-on (recipe choice already scans state.recipes). Perf: regional
  markets spec still the gate-critical pending item (>=5 ticks/s).
- L4 land market LANDED ec160df (land.py): fixed parcel stock (n>=4,
  quality tiers 12000/10000/8000bp cycled), society-owned at genesis,
  appreciated assessment (base x quality x population growth), BUY_LAND
  pays assessment -> surplus pool, SELL_LAND = 90% bank buyback (10%
  social uplift stays), Georgist LVT (default 1bp/tick ~3.6%/yr; unpaid
  -> grace_ticks -> foreclosure). BUY_LAND/SELL_LAND registered in
  SUPPORTED_ACTIONS; land_market param validation strict. base_land_price
  scales by upc at READ time (no genesis mutation). 7 contract tests
  (test_realism_land.py, run under money_cap like production).
- L5 foreign sector LANDED ed4eb57 (foreign.py): price-taker world
  market (world_prices table + tick-scheduled shocks, no rng),
  IMPORT_GOOD (price x qty + tariff_bp -> pool; buyer pays GROSS),
  EXPORT_GOOD (pays from foreign_balance). foreign_balance is a REAL
  trade balance: may go NEGATIVE (surplus in our favor - the first-
  export deadlock was a real bug my contract test caught: an earlier
  draft forbade negative bucket, making the first export impossible).
  Extended conservation identity: balances + pool + treasuries +
  foreign_balance is constant; test_fixed_supply consumers green.
  7 contract tests (test_realism_foreign.py).
- REALISM ROADMAP COMPLETE: L1 interest 15b3e4c, L2 scarcity 430fb1e,
  L3 research->productivity 844ff19, L4 land ec160df, L5 foreign
  ed4eb57 - 29 contract tests, full suite 459 green, all pushed.
  The economy now grows (TFP), prices signal scarcity, credit has a
  price, land is a fixed appreciating asset with Georgist rent capture,
  and the economy is open to terms-of-trade shocks.
- Test lessons (L4/L5): money_cap genesis IGNORES passed balances
  (stakes 500cr x upc) - derive expectations from actual balances;
  same-tick phases mean a land buyer pays LVT immediately in the buy
  tick; surplus-spend dividends hit ALL citizens every tick (use a
  control citizen to isolate flows); pool_after_buy already contains
  the buy price (uplift = final vs pre-buy, not an addition).
- L6 regional markets LANDED 7217a7c (regions.py): rule-gated
  (regional_markets.enabled, default off = byte-identical legacy path).
  Buyers (citizens AND coop-bids) partitioned into deterministic
  hash-bucket regions (region_of, salted sha256; regions=clamp(pop/100,
  4..16) or explicit). Clearing passes run per region in tick-rotated
  sorted order (region_order - fairness across ticks, pure function).
  Listings stay CITY-WIDE (coops = producers, full visibility).
  Deferred unsold-return: per-region passes skip _return_unsold so
  later regions still see remaining supply; one global sweep + ONE
  global scarcity update close the tick (L2 signal steps once, not
  once per region - contract-tested). recent_sales accumulates across
  regional passes. Strict param validation. 6 contract tests
  (test_realism_regions.py): determinism/totality, rule-off ==
  regions=1 byte-identical, multi-region conservation + deferred
  unsold, scarcity-once, rotation, validation. Full suite 465 green.
  REALISM ROADMAP: L1-L6 COMPLETE (interest, scarcity pricing,
  research->productivity, land, foreign sector, regional markets).
- NEXT SESSION: (1) Levers B+C of the perf bundle (batched cognition +
  ledger micro-pass, byte-identical, fingerprint protocol), (2) bench
  at 966 with regional_markets ON (spec: -10..15% wall, sort count
  contract >=R/2 fewer sorts/tick), (3) Rust/pyo3 decision point if
  bundle < 5 t/s (ledger path is ~40%), (4) gates re-run: hardcore
  3 seeds + refresh2 stability ladder + seat soak with regions ON,
  (5) per-region oversight streak metric for the dashboard.
- L6 PERF EVIDENCE (honest, 2026-09-11, pinned 2-core benches, 933 cit):
  OFF=1.80 t/s; ON(R=10) pre-projection=0.84 t/s; post-listing-projection
  run measured 0.40 t/s (variance across runs is large - single runs NOT
  trustworthy; medians needed). VERDICT: L6 is functionally proven
  (conservation exact, scarcity-once, rule-off byte-identical, 465
  green) but NOT perf-positive yet: the wrapper re-enters _clear_markets
  per region, which re-classifies/re-sorts that region's bids AND still
  walks city-wide tables (common_pool essential pass, cost baselines).
  Projection fix (per-region listing dict over shared entry objects,
  global unsold sweep on full table) kept - logically less work, tests
  green. NEXT SESSION, in order: (1) re-bench 3x/config, take medians;
  (2) real fix = PRE-PARTITIONED per-region state for the clearing
  (essential buyers + auction buckets built once per tick per region,
  not swapped-globals re-entry), plus Lever B batched cognition
  (~28% of tick) which dwarfs the wrapper cost; (3) only then the
  Rust/pyo3 decision on the ~40% ledger path. Do NOT enable
  regional_markets by default until medians show parity-or-better.
- L6 PERF ROOT CAUSE (profile-confirmed 2026-09-11 20:2x, /tmp/prof_on*.log):
  the PRODUCER-INPUT-PRIORITY pass (engine ~1559-1576: want=min(bid,claim)
  x take=min(entry,need) for every coop bid x EVERY city-wide listing
  entry) is quadratic, and the L6 wrapper re-ran it R=10x per tick:
  17,041,770 min() calls in 30 _clear_markets invocations (vs 107k from
  ALL bot cognition). Medians: OFF=1.77, ON=0.43 pre-fix, 0.49 post
  wash-cache fix (helped slightly; structural cost remains).
  NEXT-SESSION FIX (doctrine-aligned, spec-consistent): run the PIP pass
  ONCE city-wide BEFORE the regional citizen passes - coops are producers
  with city-wide visibility per the approved L6 contract; only CITIZEN
  buyer passes are region-sharded. Then re-bench medians: expect ON ~
  OFF minus sort savings. Wash-cache fix landed (lazy shared set via
  stats, byte-identical; region_of memo); 11/11 regional+clearance
  green; full suite re-run REQUIRED before push (was green at 465 pre-
  fix, projection+wash commits need one final suite verdict).

## Session 2026-09-12 (00:50): regions-ON 12x slowdown ROOT-CAUSED (profiles banked)

Evidence (scripts/vol_probe.py + scripts/profile_regions.py, both committed):
- Volume is NOT the cause: avg ledger records/tick OFF=18544 vs ON=18283.
- Profile (5 ticks, 966 citizens): _clear_markets called 60x ON vs 6x OFF
  (10 regions x 6 ticks), with **56M builtins.min calls (7.3s) + 14.6s
  tottime inside _clear_markets** vs OFF's 0.55s. The per-region auction
  price scan is the pathology.
- PIP extraction (4b2bf58) is proven correct and stays (legacy byte-
  identity + 10/11 regional tests green; the 1 failure below is fixed by
  the revert of my speculative patch, re-verified).

ATTEMPTED AND REVERTED: hybrid city-wide-clear-then-regional broke
L6 semantics (test_multi_region_conservation: 4 winners vs 3 - partial
bids re-served in region passes). Per-region clearing IS the spec'd
fairness semantic; do not bypass it.

NEXT SESSION (surgical, fresh context):
1. Read the auction pass inside _clear_markets (engine.py ~1700+); find
   the min() scan over (bids x entries) per good per region.
2. Fix INSIDE the regional semantic: precompute per-good sorted bid
   lists ONCE per tick (shared across regions via stats dict, like
   wash_seen), and/or per-region listing index built once (not R x
   projection scans). Goal: ON median >= 1.4 t/s (vs OFF 1.74).
3. Re-bench 3 reps each; re-run tests/test_realism_regions.py (all 11
   must pass); full suite; then Lever B batched cognition.
