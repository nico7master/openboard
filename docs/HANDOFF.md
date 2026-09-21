# Handoff: OpenBoard Economy Shipping Month Progress

## Session 2026-09-21 — P-GOV2 complete (audit FINAL package)

- S2: "votes cannot be bought" now enforced — votable `vote_buying` rule: transfer<->delegation pairing -> public VOTE_BUYING flag + bought delegation revoked + payer fined into the Society Pool; pay-then-delegate rejected inside the window; absent param = legacy replay-identical. Detector mirrors the proven attached-cache pattern (rebuilt from applied history; never id-keyed).
- S3: the source's third allocation mode "or democratic decision" shipped — need_allocation mode `democratic` orders the scarce-goods queue by community trust (delegations received), ties by need then name.
- Game world ships enforcement ON (fine 2000cr / window 30t, scaled with upc); Civic Board feed shows VOTE_BUYING.
- Verification: 8/8 new pins (tests/test_audit_gov2.py); adjacent batteries 55/55; full suite verdict recorded in the commit message.
- With this, the 2026-09-20 audit is FULLY worked: P-GOV, P-PROBE, P-ECON, P-GAME, P-DESIGN, P-GOV2 all done. Remaining founder DECIDE items: B8 (input advances as grants), D10 (social pressure, post-RC1).

## Session 2026-09-21 — P-DESIGN complete (audit package 5/5) — 589/589

- Shipped D1-D9 + C14: mission banner + fairness win screen, reign scoreboard, plain-language proposals (explain_proposal differ), attack pacing styles + oversight meter, Your Seat header tab, Mercury story hook, advisor observe/suggest dial, quest reward + confirm-dismiss. D3 flip (founder-approved): governance ships ON. S1: research fund ships ON with the founder-verified p4fix config (250bp share, 1B-unit reserve floor). S4/S6/S7 doc fixes.
- Blast radius caught by the suite (the S1 bug-class, live): research buckets missing from money accounting (fixed via B9 precedent everywhere), unlock variants dropped labor_hours/energy (latent crash, fixed), my 2M reserve floor starved the hardcore gate (replaced with the verified 1B config). Details in AUDIT_FIXES.md P-DESIGN section.
- Verification: full suite 589/589 (10:09), 7 new pins (tests/test_audit_design.py), hardcore gate green at 2000 ticks on the shipped research config. Commit b8432b0 + this docs commit.
- Audit remaining: P-GOV2 (S2 vote-buying enforcement, S3 need-allocation third mode), founder DECIDE B8 + D10.

## Session 2026-09-21 — P-GAME complete (audit package 4/5)

- **Fixed the whole C-series game layer**: C1 post-round farming refused (leaderboard records exactly once), C2 per-player attack games (16-game LRU cap), C3 playbook pinned per round, C4 unmet damage = delta over round-start baseline, C5 flag damage capped + real-harm reweight, C6 real money-invariant check with captured baseline, C7 pending actions survive save/restore, C8 autosave failures logged + surfaced via /api/state, C9 atomic leaderboard under lock, C10 account-bound citizens require their X-Auth-Token on /api/action (UI claim/login row; un-bound citizens stay open locally), C11 LLM stop restores the bot twin, C12/C13/C15 UI polish, C16/E8 duplicate gini_bp key removed.
- **Tests**: 12 new pins in `tests/test_audit_game.py`; 2 legacy attack tests updated to the per-player contract; full suite 582/582 (8:41 memrun).
- **Tracker**: `docs/AUDIT_FIXES.md` C-rows updated; C14 quest polish deferred to P-DESIGN by plan.
- **Process lessons**: write the patched file only after ast.parse passes (a broken intermediate once shipped to disk); node --check the edited inline JS block (pytest cannot see UI syntax).
- **Remaining audit work**: P-DESIGN (mission banner, plain-language proposals, governance ON default, C14 quest polish), P-GOV2 (vote-buying enforcement + S-series), founder DECIDE on B8.

## Session 2026-09-19 (early): P2 LLM POLITICIAN SEAT — live, proven, pushed (530/530)

**Directive:** "yes ready for p2" after the P0 adversary seat; founder's
voting questions answered (tally counted never rolled; persuasion dice for
undecided voters; scale-of-change => higher BAR via 60% structural tier;
influence channels: design/argument/trust; vote buying forbidden).

**Shipped (commit `1e69479`):**
- `src/openboard/llm_politician.py`: politician seat — separation of powers
 (PROPOSE/VOTE only), token-mode payload mapping, complete-ruleset digest.
- `scripts/llm_politician_session.py`: record/replay driver with accounting,
 re-queue guard (VOTE-only carryover), mechanical one-proposal-per-month cap,
 reachable quorum (1000bp) for the ~20-voter cast.
- `tests/test_llm_politician.py`: 10 tests — 60% structural tier (55% fails,
 67% passes), trust loop (-10 fail / +5 pass, capped), no-op guard,
 token-mode schema contract, full fake-client loop.

**ENGINE FIXES (real bugs, live sessions caught them):**
1. `_gov_params` whitelist DROPPED the `persuasion` flag -> the 60% tier and
 the trust loop were silently dead in every world that opted in. Fixed
 (default False = replay-safe).
2. Trust-farming exploit (session 052110): a proposal identical to the
 active ruleset PASSED and farmed +5 trust. New `Reason.NO_OP_PROPOSAL`
 (append-only) rejects no-op proposals.
3. Silent-voice contract (non-token worlds reject ANY extra VOTE key): seat
 mapping is now token-mode aware.

**Live session economics (session 053646, all fixes active):** 95 Mercury
 calls, 396,887 tokens, $0.00, 207.5s wall. Seat filed 4 proposals (mechanical
 monthly cap held), ALL PASSED with real changes (need quota tweak, wage
 multiplier 10000->10500, audit cadence 100->50), trust earned to 100 —
 no farming, no spiral. All 40 bot proposals failed quorum: the founder's
 attention-scarcity token design working as intended (40 simultaneous
 filings cannot be staffed by one-token-per-month voters).
**Replay A/B proof: byte-identical verdict with ZERO model calls**
(6.6s vs 207.5s) — LLM decisions are ledger inputs; determinism intact.

**Verification:** focused 10/10; governance batch 99/99; full suite 530/530
 (7:48, memrun). Pushed to origin (4a6a8a9..1e69479). Artifacts:
 `sweeps/llm_seat/politician_20260919_*.json` (4 sessions incl. the decisive
 053646). Note: `_gov_params` fix has wide blast radius — all governance
 features re-verified.

**Next (P3+ when founder says go):** deals layer spec (post-RC1 per
 recommendation), remaining seats (trader, journalist, entrepreneur, panel),
 then RC1 UX pass. The politician seat is the template: any future seat is
 digest + action mapping + cadence + guards on the proven harness.

## Session 2026-09-16 (morning): FOUNDER DIRECTIVES + SOURCE COMPLETION — pushed, 501/501

**User directives:** "implement all of it the way it is planned" (source
document audit gaps) + governance simplification: bots have no incentive
and are not smart — the SYSTEM proposes and they vote by default; crisis
is auto-balanced; whistleblower stays engine-only; no Cardano yet.

**Engine changes (verified: full suite 501/501 in 16:52):**
- Default-approve voting (politics.py): politicians with no stance on a
  proposal vote FOR it — system rebalancing never stalls on an indifferent
  electorate. CAPTURE GUARD: default approval NEVER applies to
  constitutional matters (voting rules/council/phase via
  _is_constitutional), or one faction proposal would ride rubber stamps
  to the 2/3 bar.
- Crisis auto-balance (crisis.py + rules.py): new `crisis.auto_ratify`
  param — shock-declared crises ratify same-tick with zero citizen votes
  (event carries auto: true). Legacy worlds (no key) replay identically.
  `crisis` registered in OPTIONAL_PARAMS with strict validation.
- Source-document gaps ON by default in live games (server.py governance
  block): whistleblower bounties (500cr reward), automatic audits (every
  100 ticks), need_allocation priority mode. All remain votable.
- **REAL BUG FIXED (wide blast radius):** wealth_tax.threshold was scaled
  x100 TWICE (server _params pre-scale per D21, then genesis_state again)
  -> 5B units -> every whole-document proposal built from a live world's
  active params failed validate_params (100M cap). Live governance games
  could not file ANY proposal with correct params. Removed the genesis
  re-scale (state.py); the D21 comment in rules.py confirms 50M units is
  the intended final value. Politics tests passed only because they
  replaced the tax dict wholesale — invisible until founder-directive
  tests built proposals from real live-world params.
- Capacity audit follow-ups (catalog.py): medicine 3->5/run (the ONE true
  gap at 83.5% coverage in the 966-citizen audit), bread 40->50/run
  (95.7% peak slack on a single chain). Replay-safe: saves serialize
  recipes.
- Founder switching: verified ALREADY LIVE (true-need §3 replication
  block in bots.py — mature+roomy coops release a member to found a
  duplicate when the good is under-capacity). No code needed.

**Commits:** 5 pushed (5c30ed0..d6039db): vote token, source-completion,
founder directives + wealth-tax fix, gap defaults.

**Watch item CLOSED (2026-09-16, capacity_966_audit rerun s42, 949 pop,
150 ticks):** medicine capacity 26.4 -> 44.0 units/tick (coverage 83.5%
-> 139.1%), bread 4,053 -> 5,067 (95.7% -> 119.7%). Audit verdict: ZERO
under-capacity goods economy-wide, kcal group 1,606% (famine impossible),
D18 wage-debt book 19.2M / 68 coops / zero assumption events. Evidence:
sweeps/society/capacity_966_s42{,_before_bumps}.json. Remaining open
item: politics bots still file ~270 doomed proposals/run (they die
unnoticed now that votes are scarce); UI-side proposal surfacing is the
natural next pass.

## Session 2026-09-15 (afternoon/evening): TRUE-NEED BALANCE — gate PASSED (3 seeds x 2000 ticks)

**User directive:** "balance everything out as it should be" — replace the
physiologically absurd need basket (~81,000 kcal/citizen/tick, ~35x real
food, 12 forced foods) with a real calorie budget.

**Engine changes (verified: hardcore gate 1 passed 645s; suite 476/476):**
- kcal needs model (rules.py + engine.py + bots.py): foods form ONE
  substitution group; hunger closes on TOTAL kcal (~2,900/tick),
  compensating pass to 2x preference caps; group reports one streak key
  "food". Absent kcal_needs -> legacy per-good semantics (replay-safe).
- GRAIN = the STAPLE (1 unit = 3,400 kcal). Without a citizen-accessible
  staple the food group NEVER closed (gate breadth 2000/2000).
- Catalog batch rescale (catalog.py) to city scale: coal 24->600,
  electricity 300->1200, wind 100->1000, grain 100->800, fabric 6->36,
  clothing 8->48, childcare/healthcare 96, education 48, meals/flour/bread
  2x, water 240, livestock 150x3. Services/needs cycled (needs_cycle).
- max_coop_members 20->50 (had no documented rationale; engine fallback
  said 12); founder cast scales with population (stage6).
- Entrepreneur/founder trigger: durable under-capacity test (demand_ema vs
  pop x quota) replaces dribble-listing blindness (bots.py).
- **CRITICAL INVARIANT:** a specialist's `buys` dict OVERRIDES the
  recipe-native bid loop -> must mirror the recipe's per-run consumable
  inputs. 7 stale dicts (pre-rescale) caused PERMANENT BID SUPPRESSION:
  power_plant dead 301/300 ticks with coal frozen at 16 (< 48 needed),
  need computed to 0 -> no electricity -> no water -> no meals (streak
  1,975/2,000). Synced all 7 (server.py). Code comment documents it.
- Research funding: optional reserve_floor + start-tick (earlier fix,
  included); research_effect_bp cap 2500 -> 5000 (+50% dial).

**Gate ladder:** worst_essential 1975 -> 2 -> 0; breadth 2000 -> 153 ->
36 -> 10 -> PASS. Fix rounds: staple, batch rescale, buys-dict sync,
transport/heating/water/wind margins, fabric->clothing rescale.

**Watch item CLOSED:** wage debt is a startup float (peak 6.4M @t400)
that plateaus 4.3-5.7M through t=2000 — not a spiral
(scripts/wage_debt_trend.py, sweeps/true_need/PROGRESS.md).

**Working state:** gate + suite green, no stray processes, work landed as
one comprehensive commit (this one). Artifacts: sweeps/true_need/,
docs/superpowers/specs/2026-09-15-true-need-balance.md.



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

## Session 2026-09-12 01:25: regions-ON wrapper pathology FIXED (0.14 -> 0.74 t/s, 5.3x)

Evidence chain (all scripts committed):
- vol_probe.py: records/tick OFF=18544 vs ON=18283 -> NOT economic volume.
- profile_regions.py BEFORE: _clear_markets ON 60 calls (10 regions x 6 ticks),
  56M min() calls, 14.6s tottime vs OFF 0.55s. AFTER fix: per-call 0.090s ON
  vs 0.092s OFF (equal); residual ON gap is call-count arithmetic (60 vs 6)
  = the approved L6 regional semantic itself, NOT a pathology.
- Fix (3f0922b): regional listing projection keeps qty>0 entries only
  (listings accumulate qty==0 dead entries; essential pass rescans them per
  buyer x R regions). Entry dicts stay shared; empty filtered lists keep the
  good key (event streams unchanged); legacy OFF path untouched.
- Bench (3 reps, pinned): ON 0.737/0.737/0.737 t/s (vs OFF 1.74).
- Verification: 11/11 regions+clearance, full suite 465 passed (604s).
- REJECTED en route: city-wide-clear-then-regional hybrid (broke L6
  semantics: partial bids re-served, 4 winners vs 3); reverted.

Next perf levers: Lever B batched cognition (~28% of tick, helps both
paths); optionally revisit default region count (R=10 at 933 pop).

## Session 2026-09-12 14:2x: Lever C sub-step 1 landed (7f76cad) - _run_cost per-(tick,coop) cache

- WP4.2 transformation 1 (per-coop decision templates), first sub-step:
  the D18 equity-injection _run_cost is coop-constant within a tick
  (reads only the coop recipe + static baselines); now computed once per
  (tick, coop) via _decision_cache in bots.py, reused by every member.
  Per-citizen part (_bal, _inj, TRANSFER append) untouched.
- En route failure (honest): a scripted rewrite of the honest-wages
  block dropped the _hw gate/_rests guard/WORK append -> 3 suite fails
  (hardcore survival, phase7 100-tick, ratchet 50-tick). Reverted to
  c77154f, artifact script deleted. Lesson applied: surgical patches
  only, never whole-block rewrites.
- Proof: fingerprint A/B byte-identical (records=1000,
  state=2177a714265097bf, outcomes=6cc27474dd2ac5b2 = HEAD witness);
  full suite 465 passed (625s).
- Bench (966 pop, 3 reps, pinned): OFF median 1.71 t/s (1.59/1.71/1.72)
  - within noise of the 1.57-1.74 pre-C band; the win scales with
  members-per-coop, not at 966.
- Next: cognition caching rungs are DONE (A/B 09-10, C1 tonight). Fresh
  cProfile at 966 on this HEAD queued to size the two structural levers
  from the 09-10 verdict: ledger record batching (needs own spec - hard
  gate, pre-anchor window) vs clearing sorts.

## Session 2026-09-12 14:5x: Lever D (ledger batching) investigated and DECLINED pre-anchor

- Fresh 966-profile (scripts/profile_scale.py 966 6 42): content_hash chain 2.42s cumtime (~27% of 9.09s wall), record_hash linkage 0.69s (~8%), sorted 2.44s OVERLAPS content_hash (first-time hashing inside sort_key - do not double-count).
- First implementation attempt (buffer accept + tick flush_batch with per-tx Merkle) was broken by construction: deleted reject() (6 engine call sites), NameError in the individual-records comprehension, batch record fails verify_chain content check, collapses per-tx reason codes (S14). Reverted; ledger smoke OK after (accept/reject/verify_chain).
- Honest re-read: tx_hash = sha256(canonical_json(tx)) IS the S14 content commitment - irreducible in Python. True batchable ceiling is the ~8% linkage share, not 2x. A structural record-stream change can never pass the fingerprint A/B gate anyway (it changes the hashed stream itself).
- Verdict banked: docs/superpowers/specs/2026-09-12-ledger-record-batching.md = DECLINED pre-anchor. Post-release option: parallel/Rust content_hash (preserves per-tx commitment). Also: to_dict/content_hash memoization already works under frozen=True via object.__setattr__; unfreezing is NOT needed and would break dataclass hashability.
- Benches at 7f76cad (3 reps, pinned 2-core): OFF median 1.71 t/s (1.59/1.71/1.72), ON median 0.74 t/s (0.737/0.740/0.740). Lever C helps dense-coop workloads, neutral at 966; the ON residual gap is the approved 10x-pass regional semantic itself.
- Python-side ladder closed: 1.74 peak / 1.71 current OFF. Path to >=5: pre-partitioned regional clearing, Rust/pyo3 hashing+clearing kernels, or reduced region count - each needs its own spec (hard gate).

## Session 2026-09-12 16:0x: Lever E (listing pre-bucketing) DECLINED + region-count sweep evidence

- Lever E as drafted (bucket listings by region per tick) violates the L6 contract: listings are city-wide (coops = producers, full visibility), and the per-pass projection CANNOT be cached across passes because sales in region r mutate entry qty in place - later regions must see that. Rebuilding the projection per pass IS the correctness mechanism. Verdict + evidence: docs/superpowers/specs/2026-09-12-regional-pre-bucketing.md
- Region-count sweep at 966 (pinned 2-core memrun, 3 reps each): R=4 median 0.70 t/s (0.692/0.696/0.698), R=10 median 0.74 t/s (0.737/0.740/0.740). Flat within noise: fewer regions = more buyers per pass = bigger per-pass sorts; fixed wrapper cost is not the dominant term. Region-count tuning will NOT close the ON-vs-OFF gap (1.71 OFF).
- Conclusion banked: the remaining ON cost is per-pass clearing work that persists across R. Honest path to >=5 t/s stays structural: pre-partitioned clearing state (own spec + fingerprint gate) or Rust/pyo3 kernels for hashing+clearing. Python ladder: closed at 1.71-1.74 OFF / 0.70-0.74 ON.

## Session 2026-09-15 22:xx: Source-model completion (3 gaps closed, founder-approved)

- Spec: docs/superpowers/specs/2026-09-15-source-completion.md. Packages: (A) scarcity_pricing ON in DEFAULT_RULESET_PARAMS (max_markup 2500bp; essential settlement clamps to floor so no gouging; crisis zeroes signals); (B) REPORT action + whistleblower bounties (first-report-wins per (kind,target), SELF_REPORT rejected, per-tick cap, pool-funded, WHISTLEBLOWER_PAID public event; optional param, default OFF) + AUDIT_REPORT periodic public event (recomputed verify_chain + flag summary + pool/treasury; optional audits param, default OFF); (C) need_allocation param: priority = longest-unmet-first (kcal foods read group key 'food'), lottery = deterministic LCG; crisis forces priority regardless of mode (optional, default OFF).
- Errors.py: +REPORT_DISABLED/FLAG_NOT_FOUND/ALREADY_REPORTED/SELF_REPORT. OPTIONAL_PARAMS += whistleblower/audits/need_allocation, strict schema blocks in rules.py.
- Verification status: 12 new tests + fixed stale default-assuming scarcity test (now tests OFF contract explicitly + asserts default ON) — all pass. Full suite 494/495 with that one stale test (fixed after). Hardcore gate seed 7 PASSED with scarcity ON: worst_essential=0 worst_breadth=9 (bound 30). Seeds 42/123 pending at write time; commit+push after gate ladder completes.
- Dispatch wiring for new actions: SUPPORTED_ACTIONS + validators + appliers (see engine.py REPORT entries) — copy that pattern for future actions.

## Remote sims available (2026-09-17): user's LAN PC — probe first

Heavy parallel study batches (gates, seed sweeps, atlas grids) can run on the founder's
LAN PC over sandboxed SSH: `sims@192.168.178.46`, unprivileged user, no sudo (fence
verified). The PC is OFTEN but NOT ALWAYS on — **always probe reachability first and fall
back to local memrun if unreachable.** Full workflow, sync/run/poll/retrieve commands,
parallelism limits, and the teardown kill-switch: `docs/REMOTE_SIMS.md` (authoritative).
Verified 2026-09-17: 3-seed 2,000-tick gate in parallel = 8.3 min vs 32 min local,
results byte-identical to container runs.

## 2026-09-19/20 — RC1 UX: founder defaults live, Civic Board, watch-me-think (commit c9f73fa, pushed)

**Founder directives shipped end-to-end (9 new tests, full suite 539/539):**

1. **Governance defaults live**: every `Run(governance=True)` world now launches with the founder design — monthly vote token (10k bp / 30-tick cycle), persuasion dice, reachable quorum (10%). Before, live games silently launched without token/persuasion and with an unreachable 50% quorum; only the P2 driver patched them post-hoc. Legacy (`governance=False`) worlds untouched — replay-safe.
2. **Human vote bug fixed (real bug)**: token-mode validation requires exact keys `{proposal_id, choice, bp}` — the seat VOTE affordance (`/api/seat` actions + UI `seatVote`) sent no `bp`, so **every human vote in token worlds was silently INVALID_PAYLOAD**. Both fixed; civic-board split voting is the follow-up.
3. **Civic Board tab** (`🗳️`): proposals with quorum counts, civic event feed (PROPOSAL_SETTLED, OVERSIGHT_FLAG, WHISTLEBLOWER_PAID, AUDIT_REPORT, crisis), politician trust book, token/crisis status. `/api/civic`.
4. **Watch-me-think LLM attach**: `/api/llm/start|stop|status` attach Mercury-2.5 to the politician seat as a daemon. Contract: snapshot digest under `RUN.lock`, call the model OUTSIDE the lock (never stalls the API), queue via the human path; tick-dedup (never re-decide a tick), VOTE-only carryover, one-proposal-per-month cap, malformed-reply tolerance, full token accounting; refuses legacy worlds (its bp votes would be silenced); world reset clears the seat.

**Test fallout handled**: 2 persuasion-tier tests pinned to legacy binary votes in their fixture (they test tier math, not tokens). Two of my new tests initially encoded wrong assumptions (inert default bp in disabled worlds → real contract is GOVERNANCE_DISABLED; no-op proposal rejected → file a real transfer_limit bump).

**Ops note**: container restart mid-session wiped flask/pytest from /opt/venv (reinstalled) and restored the git remote URL in alias form — push needed the explicit authenticated-URL path again. See REMOTE_SIMS.md for the sandbox; same pattern.

**Next**: human split-vote UI on the Civic Board (slider over the 10k bp), then trader/journalist seats off the same template, then the RC1 week-3 science re-run under the new defaults.

## 2026-09-20 — Split voting + the Citizen Seat panel finally exists (commit 02175de, pushed)

**Split voting shipped (founder's monthly token, end to end):**
- `/api/seat` VOTE affordance mirrors the ACTIVE governance mode: token worlds offer bp = remaining budget (split voting), legacy governance worlds omit bp (validator rejects extra keys), disabled worlds get no affordance at all. `/api/seat` now exposes `vote_token {mode, bp_left, cycle_ticks}`.
- **Citizen Seat panel actually exists now** — the view was a blank page (markup never built; the 'Play as a citizen' tab rendered nothing, which is why the human-vote bug stayed invisible). Built: citizen picker, token gauge with per-vote bp spend (all/half presets), proposal cards with vote buttons, actions list (VOTE deduped), the seatChart canvas the JS expected, ledger event log. Buttons disable at 0 bp.
- LLM daemon reads token mode LIVE per decision (a passed proposal can turn the token off mid-session; hardcoded True would silence the seat).
- New end-to-end split test: 2 votes in one month, budget 10000→6000→0, affordance tracks the remainder, overspend dies VOTE_BUDGET_EXCEEDED with the book untouched. Full suite: **540/540**.

**Next**: trader/journalist seats off the politician template; RC1 week-3 science re-run under the new defaults (scarcity pricing ON now); then week-4 freeze/soak/ship.

## 2026-09-20 — P2 battery re-run under the current engine: all verdicts re-verified, two upgraded (commit this one)

**RC1 week-3 science.** The ORIGINAL p2 battery (6 arms × 3 seeds × 650t × 1,000 citizens) re-run unchanged against today's engine via `scripts/p2_rerun.py` (output-redirect wrapper; historical `sweeps/p2/` untouched), analyzed with `scripts/p2_rerun_analyze.py`. Data + verdicts: `sweeps/p2_rerun/FINDINGS.md`; STUDY_PLAN has the summary table.

- **Skills safe** ✅ re-verified — old effects were scarcity-regime artifacts (now Gini +65…+86, machines ±50 noise, unmet 0 both arms)
- **Confiscation upgraded** ⬆️ — still passes, still fires ~449k times / ~335M units, but the production penalty is GONE (≈88k events both arms); Gini 2,100 → 103, zero deaths. Harmless equalizer now.
- **Crisis mode** ➖ — insurance with no current claim: unmet 0 in BOTH arms; the ~13% production redirect cost remains. Keep the lever for live shocks.
- **Universal shift (all 18):** unmet 65–886 → 0; production +13.4k…+22.6k; machines −0.9k…−2.7k (wear rule); deaths 0; money conserved everywhere.

**Next:** RC1 week-4 — code freeze → overnight soak → full verification → player guide → RC1 tag. (Split-vote UI shipped earlier today; Citizen Seat panel exists.)

## 2026-09-20 — Week-4 freeze gate GREEN: RC1 soak 3/3 + suite 540/540 (commit 16a221b, pushed)

**RC1 soak (`scripts/rc1_soak.py`, data `sweeps/rc1_soak/`):** 3 seeds × 2,000 ticks × 975 citizens with the FULL founder-default stack ON (governance token+persuasion+reachable quorum, whistleblower, audits, need_allocation, scarcity pricing) + capital_refresh. inv_bad=0 across all 6,000 seed-ticks; worst essentials streak 4 (genesis blip, bound 50); deaths 0; pop stable 975; Gini ~180; 56,550 votes + ~590 proposals + 970 audits per seed; RSS ~590MB; ~12 min/seed.

Diagnostics worth keeping: smoke votes=0 was a too-short window (real governance cognition fires from ~t30; 120-tick diag showed 870 votes/546 settlements); the ~600/tick OVERSIGHT_FLAG volume is the oversight economy working (HOARD-dominated bot chatter funding whistleblower rewards), not a violation; bot proposals settle as 'failed' status (counter now buckets passed/rejected/failed).

**Final pre-freeze suite: 540/540** (8:29). Everything needed before the tag is done except the player guide + the tag itself — both await founder go. Freeze is in effect until then: no engine changes without founder approval.

## 2026-09-20 — Testing Retrospective written (docs/TESTING_RETROSPECTIVE.md)

Founder-directed synthesis of the whole testing program: the bug ledger (13 ship-stoppers and what caught them), the science verdict ledger with data paths, the honest LLM-seat assessment, the weak/mistaken tests, process mistakes that birthed the memrun discipline, what the evidence says about the design (core claim survived everything; failures were bugs/mis-scalings, never design flaws), and the 7 binding test standards going forward. READ THIS before designing any new study — it contains the verdict-expiry rule and the full-session doctrine.

## 2026-09-20 — Audit fix package P-GOV: governance hardening (multi-agent audit round 1)

Founder approved all five audit fix packages (P-GOV → P-PROBE → P-ECON → P-GAME → P-DESIGN), worked one by one; every finding documented in `docs/AUDIT_FIXES.md` (single source of truth — S-series = spec-drift reviewer, E-series = code-quality reviewer, both late returns now recorded).

**P-GOV shipped (all with regression tests in `tests/test_audit_gov.py`, 11/11):**
- **A1** crisis votes are one-per-citizen (`CRISIS_VOTED` reason; JSON-safe voter dict on the crisis record) — was: unlimited repeat votes, one actor could ratify any crisis alone.
- **A2** the 60% structural tier now counts against ALL citizen weight, not cast weight (mode-aware: bp in token worlds, counts in legacy) — was: 10% bloc could pass anything via abstention-shrunk denominators. Control test proves a real 60% majority still passes.
- **A3** delegation mirroring reads the **open-time snapshot** (`delegations_snapshot` on the proposal) — last-second delegation sweeps can no longer flip outcomes.
- **A4** trust hardening: unknown politicians start at 50 (not 100); engine-side `PROPOSAL_LIMIT` (one open proposal per proposer); persuasion die seeded on proposal content hash (no reusable roll tables).
- **A5** structural whitelist extended: surplus_spending, credit, scarcity_pricing now need the 60% tier (diverting the whole surplus pool was a simple-majority move).
- **A8** bots split their monthly token across open proposals — first-proposal decoys no longer drain the electorate.
- **A9** structural rollbacks keep the structural tier inside the trial window (judged on the REVERTED version's delta vs its parent — the rollback's own params are vacuous mid-trial).
- **E1 (pulled forward from P-ECON)** OPTIONAL_PARAMS now includes the six stage-5 keys the engine reads (research, shocks, demographics, wage_debt_repay, birth_stake_from_pool, wage_mint_mode) + a parity-guard test — PROPOSE of a complete ruleset (the politician seat's standard move) no longer dies INVALID_RULESET in stage-5 worlds.

**Collateral the suite caught (all fixed):** the A3 replace had also hit the LEGACY `expand_ballots` (NameError `deleg`) — repaired to live state; the A4 trust default invalidated two P2-era test pins (100→50) — updated to the hardened behavior; the split-vote UX test filed two proposals from one citizen — second now files from another citizen (A4 working as designed). LLM politician digest teaches the new rules (one-open cap, 50 start, all-citizen tier).

**Verification:** scoped files 43/43 → full suite (first run) 550/551 with the split-test conflict as the only failure → fixed → final full suite running at commit time. Freeze remains lifted ONLY for tracker-listed fixes.

**Next:** P-PROBE (B1/B2/B4/B6/A7 memrun probes) → P-ECON → P-GAME → P-DESIGN; P-GOV2 (vote-buying enforcement S2, mixed ballots E12) queued after.


## 2026-09-21 — B8 decided and shipped: advance-entitlement decay/recovery (founder design)

Founder redesigned B8 on the spot (better than the proposed lifetime cap): "reduce the grant every month. So that he will need to look for work soon again. Not lifetime but just simple reduction. Let's say 5% a month. And for every month he worked normally the grant recovers again 5% up to Max."

**Shipped exactly that:**
- `capital_backstop.input_advance` gains votable `decay_bp_per_month` / `recover_bp_per_month` (game world: 500/500; validator bounds 0..10_000; absent keys = pure legacy identity, pinned).
- Entitlement is per-coop bookkeeping: each RESCUE month decays once (monthly, not per event — interval 10 rescues 3x/month but decays 1x); each CLEAN month (produced during it, not rescued during it) recovers, capped at 10_000bp; lazy month accounting settles every fully-elapsed month for EVERY coop (healthy coops recover without needing grants).
- Entitlement floor starves serial dependents (0bp after 20 rescue-months -> no grant, pool untouched); honest producers keep the full safety net forever.
- Clone preserves the three bookkeeping fields (wage-debt bug class); grant conservation exact; event carries `entitlement_bp`.

**Verification:** 16/16 pins (`tests/test_audit_b8.py`) — first 3 failures were test bugs (validator returns None on success; missing treasury resets), all fixed, engine untouched by them. Adjacent batteries 59/59. Full suite + soak re-run queued for the RC1 tag gate.

**Also approved this session:** D10 (social pressure) post-RC1 with the flags->trust design sketched; player guide next; RC1 soak re-run on the final engine, then tag.

## 2026-09-21 — RC1 soak re-run on the FINAL engine: 3/3 PASS (freeze gate green)

The v1 soak predates all six audit packages + B8 (verdicts have expiry dates), so it was re-run on the shipped engine. Found and fixed a REAL METER BUG first: `stage6_scale_gate.money_delta` was a stale hand-sum predating the foreign (B9) and research-funding (S1) buckets — every funding tick looked like money vanishing (inv_bad=247/250 at soak start). The meter now delegates to the canonical `breaksystem.money_total`; a 60-tick probe confirmed inv_bad=0 with the fixed meter (engine was exact all along).

**Final-engine soak (3 seeds x 2,000 ticks x 975 citizens, all founder defaults + audit hardening + B8 ON):**

| Seed | inv_bad | worst streak (bound 50) | deaths | republic evidence | wall |
|---|---|---|---|---|---|
| 42 | 0 | 14 | 0 | 840 proposals, 1,187,550 votes, 970 audits | 798s |
| 7 | 0 | 14 | 0 | same profile | 797s |
| 123 | 0 | 14 | 0 | same profile | 815s |

v1 results archived in `sweeps/rc1_soak_v1_pre_audit/`; new verdicts in `sweeps/rc1_soak/`. Player guide shipped at `docs/PLAYER_GUIDE.md` (linked from README follow-up). Full suite 613/613 (commit 9549372 state). **RC1 is tag-ready** — tag awaits the founder's word.

## 2026-09-21 (later) — Pre-tag verification gate: GREEN

- Engine diff since the suite-green commit (9549372): EMPTY (docs/scripts only) — and confirmed anyway by a fresh full suite at HEAD: **613/613** (10:46).
- Final-engine soak: 3/3 PASS (see above). All six audit packages + B8 regression-pinned.
- Memory canon updated: meter-bug-class lesson (canonical money_total, delegate-don't-hand-sum) + B8 shipped design.
- **RC1 is tag-ready.** Tag is the founder's call (repo convention: v0.4/v0.5 exist; suggested: `rc1` or `v1.0-rc1`).

## 2026-09-21 (evening) — Live Mercury session on the FINAL engine: seat verified, republic stricter by design

A recorded 60-tick live session (55 calls, 258k tokens, $0.00, 5 malformed replies survived, invariant OK, wall 161.6s; artifact `sweeps/llm_seat/politician_20260921_164231.json`) plus a byte-identical zero-call replay (determinism holds on the final engine).

**Finding: the seat is fully alive under the audited rules — and the republic is legitimately harder.**
- Transaction level: ZERO rejections. The seat's complete-ruleset proposals validate (E1 parity guard holds on stage-5 params incl. research/shocks/demographics) and every PROPOSE/VOTE was accepted — no silent silencing, no INVALID_RULESET regression.
- Proposal outcomes: 21 filings in-world, 21 failed. Most are BOT spam failing quorum (the documented attention-scarcity pattern: 253 filed / 0 passed in the P2 rerun). The seat's own wealth_tax proposal is STRUCTURAL — the A2 hardening now requires 60% of ALL citizens (179), correctly unpassable in a 60-tick session.
- Trust 50 -> 40: the failed-proposal accountability loop (founder decision) working as designed.
- The pre-audit 4/4 pass rate was measured under the OLD, exploitable cast-weight denominators. Post-audit pass rates are the approved tradeoff: spam-proof, capture-resistant.

**Watch item for gameplay (post-RC1 tuning, not a defect):** if NOTHING ever passes even in long sessions, the republic feels dead. Candidate tune: bots coalesce votes on a few proposals per cycle instead of spreading across all (raise effective support for sensible filings), or lower the structural tier slightly. Tuning is a votable parameter change — do it with the politics battery, not ad hoc.

## 2026-09-21 (final) — Fresh-clone gate: PASS — the repo is self-contained

The suite had only ever run in the working tree. Definitive check: `git clone` to a pristine dir (no egg-info, no saves, no local state — verified none tracked) and run the full battery there: **613/613 (638s)**. Anyone can clone and verify RC1 from scratch. Temp clone removed.

**Release verification is now exhaustive:** working-tree suite 613/613 · fresh-clone suite 613/613 · final-engine soak 3/3 PASS · live Mercury session verified + replayed byte-identical · tracker clean (only approved post-RC1 rows). **RC1 is tag-ready; the tag is the founder's call** (suggested: `v1.0-rc1`).

## 2026-09-21 (close) — Boot smoke: the player guide's first instruction verified

`python dashboard/server.py` boots clean; `GET /` serves the dashboard (200, correct title) and `GET /api/state` answers with live state on :8421; clean shutdown after. The player guide's quick start is verified end to end, not assumed.

**Release verification stack (complete):** suite 613/613 (working tree) · suite 613/613 (fresh clone) · soak 3/3 PASS (final engine) · live Mercury verified + byte-identical replay · boot smoke PASS · tracker clean. **RC1 tag-ready — the tag is the founder's call.**

## 2026-09-21 (visual close) — UI visual verification: PASS

Browser-rendered the live dashboard and verified with vision: all six tabs render (World/Lab/Chronicle/Break It/Civic Board/Your Seat), the Reign scoreboard shows (day 1, Gini 99.22, ledger ✓), quest banner, tick controls, and charts all clean — the P-DESIGN UI is player-ready, not just test-green. Evidence: `sweeps/ui_smoke_dashboard.png`.

**Release verification stack — exhaustive and complete.** RC1 tag-ready; tag is the founder's call.
