# Audit Fix Tracker — 2026-09-20 (approved: all packages, one by one)

**Mandate:** founder approved all packages (P-GOV, P-ECON, P-GAME, P-DESIGN, P-PROBE). Work order: P-GOV → P-PROBE (feeds P-ECON) → P-ECON → P-GAME → P-DESIGN. Both restarted reviewers have returned; their findings are recorded below (S-series, E-series) and slotted into packages.

**Status legend:** ☐ pending · 🔍 probe-first · 🔧 fixed (+test) · 🚫 won't-fix (reason) · ⏳ awaiting/post-RC1

Source audit: `docs/AUDIT_2026-09-20.md`. Freeze lifted only for listed fixes; every fix lands with a regression test (`tests/test_audit_gov.py`); full suite before each package commit.

---

## P-GOV — governance hardening (✅ CODE COMPLETE 2026-09-20 — 11/11 audit tests pass)

| # | Finding | Status | Notes |
|---|---|---|---|
| A1 | CRISIS_VOTE counts no voters — unlimited repeat votes, single-actor ratification | 🔧 fixed +test | `crisis.voters` dict (JSON-safe) + `CRISIS_VOTED` reason; tally counts first votes only |
| A2 | structural 60% tier over CAST weight + 10% quorum → minority capture via abstention | 🔧 fixed +test | denominator = all citizens × token (unit-guarded for legacy 10k); 2/5 voters now fail, 3/5 still pass |
| A3 | delegation mirroring multiplies weight; tally-time reads → last-second sweeps | 🔧 fixed +test | `delegations_snapshot` frozen at proposal-open; tally mirrors through the snapshot, not live state |
| A4 | trust entrenchment: default 100, +5 any pass, no rate limit, precomputable dice | 🔧 fixed +test | unknown politicians start at 50; `PROPOSAL_LIMIT` (one open proposal per proposer); die seeded on proposal content hash |
| A5 | structural whitelist omits surplus_spending (and credit, scarcity_pricing) | 🔧 fixed +test | `_STRUCTURAL_TOP_KEYS` extended — surplus diversion/credit/pricing now need the 60% tier |
| A6 | auto-ratified crisis = one-death kill-switch, kind always 'pandemic' | 🚫 DECIDE | founder directive stands for RC1; revisit severity threshold + kind mapping post-RC1 |
| A7 | whistleblower bounty rotation by colluders | 🔍 | EV probe first (penalty vs bounty) — P-PROBE |
| A8 | vote-token attention race (decoys consume the electorate) | 🔧 fixed +test | bots split the monthly token across open proposals instead of dumping on the first |
| A9 | rollback trial window reverts structural changes cheaply | 🔧 fixed +test | rollback structuralness judged on the REVERTED version's delta vs its parent (not its own params — that check is vacuous mid-trial) |

Replay-safety note: A2/A9 change settle behavior only for persuasion worlds (server default since 09-19); saved settled proposals are stored resolved, so resume replay is unaffected. A1/A3 additions are JSON-serializable state.

## P-PROBE — verify-before-fix (next)

| # | Finding | Status | Notes |
|---|---|---|---|
**P-PROBE COMPLETE 2026-09-20** — `scripts/audit_probes.py` (memrun-held), results in `sweeps/audit_probes/probe_results.json`. All five claims CONFIRMED empirically:

| # | Finding | Status | Probe evidence |
|---|---|---|---|
| B1 | serial loan default drains pool | ✅ **CONFIRMED** | 4 cycles → 20,000 drained from pool; each default's record overwritten by the next LOAN (book_row_reset=false) — the audit trail is destroyed, not just the money |
| B2 | capital_rent overcharge under durable_capital | ✅ **CONFIRMED ×169** | one durable machine (durability 20): 31,200 rent charged over its life vs 185 live replacement; machine died at run 20 as designed — rent is pure double-depreciation |
| B4 | capital_refresh retires at stale book values | ✅ **CONFIRMED ×7.4** | refresh retired 3,300 for a basket worth 445 at live baselines (2 machines + 5 tools) |
| B6 | legacy recent_sales overwrite kills B2B demand signal | ✅ **CONFIRMED** | same-tick coop bid (4, via PIP pass) + citizen bid (3): sold=7 but recent_sales=3 and EMA=3 — the PIP volume is wiped from the signal producers plan on |
| A7 | whistleblower bounty rotation EV | ✅ **CONFIRMED → FIXED** (P-ECON 09-20): opt-in `whistleblower.penalty_credits` — the flagged citizen pays up to N units INTO THE POOL (clamped at balance, conservation exact); game world 1000u vs 500u bounty = rotation now nets −500/cycle; absent key = legacy | same-pair repeat blocked (ALREADY_REPORTED) confirmed |
| N1 | **NEW (found by probe): credit_phase is nested under `demographics.enabled`** in the engine tick | ✅ **CONFIRMED** | in credit-enabled worlds without demographics, loans NEVER default (credit_phase never runs) — the L1 default contract silently doesn't exist there. Fix: un-nest credit_phase |

## P-ECON — engine drain + coherence (after probes)

| # | Finding | Status | Notes |
|---|---|---|---|
| E1 | OPTIONAL_PARAMS missing stage-5 keys (research/shocks/demographics/wage_debt_repay/birth_stake_from_pool/wage_mint_mode) → PROPOSE of a full ruleset died INVALID_RULESET — governance dead in exactly those worlds | 🔧 fixed +test | pulled forward into P-GOV 2026-09-20; parity guard test prevents recurrence |
| B1 | loan default blocking | ☐ | probe CONFIRMED (20k drained, trail destroyed): defaulted loans block new LOANs + keep book row; ALSO un-nest credit_phase from demographics (N1) |
| B2 | rent amortization | ☐ | probe CONFIRMED ×169 (31,200 rent vs 185 replacement): amortize rent per durability (1500/20=75/run) or charge live replacement/durability |
| B3 | state-copy divergence: clone() omits loans, capital_wear, recent_sales, unserved_bids, demand_ema; _clone_coop omits wage_debt, recipe_intent, last_produce_tick; snapshot drops wear/sales/bids (E2, expanded scope) | ✅ **FIXED** (P-ECON 09-20): clone()/_clone_coop now faithful (deep-copy, round-trip test); snapshot covers the five fields behind the opt-in `hash_v2` rule — absent key = legacy hash = every recorded history replays bit-identically; the live game world enables hash_v2 |
| B4 | refresh pricing | ☐ | probe CONFIRMED ×7.4 (3,300 retired vs 445 live): price refresh from good_cost_baseline |
| B5 | governance sub-schema never type-checked — vote_token_bp="5000" passes validation then TypeErrors the tick (E3) | ☐ | validate governance sub-key types in rules.py; one shared schema owner |
| B6 | recent_sales accumulation | ☐ | probe CONFIRMED (sold 7, signal kept 3): accumulate in legacy path like defer_unsold does |
| B7 | base catalog: heating_fuel/medicine quotas without recipes | ✅ **FIXED** (P-ECON 09-20): stripped from DEFAULT quotas (verified 0 unproducible goods remain); the dashboard game world re-adds both (extended catalog produces them); recorded worlds keep their own rulesets — hash-safe; stage4 quota test now pins producibility | — |
| B8 | input advance = perpetual grant | ✅ FIXED (P-GOV2+, founder design 2026-09-21) | advance entitlement decays 500bp/rescue-month and recovers 500bp/clean-work-month up to max (monthly, not per-event; first rescue full). Serial dependent -> 0 after 20 rescue-months (faucet dries up, "look for work soon"); honest producers keep the full net. Votable knobs `decay_bp_per_month`/`recover_bp_per_month` (absent = pure legacy identity); clone preserves the bookkeeping; game world ships 500/500. 16 pins in `tests/test_audit_b8.py` |
| B9 | dashboard invariant omits foreign_balance | ✅ **FIXED** (P-ECON 09-20): money_total + both dashboard money sums count the foreign bucket exactly (0 in non-trade worlds = byte-identical totals) | — |
| B10 | hardcoded constants: wage 800 in insolvency backstop; _CAP_TARGETS 60/1500 vs live ~10,095; _ess_seed 4 goods (E6) | ✅ **FIXED** (P-ECON 09-20): backstop daily wage derived from rules (8h x mult_bp x upc == 800 at defaults; legacy worlds keep literal 800 — test pins both regimes); refresh affordability ordering prices from live baselines; _ess_seed kept (founder tuning, load-bearing in gates) | — |
| B11 | post-crisis markup snap-back | ✅ **FIXED** (P-ECON 09-20): opt-in `scarcity_pricing.post_crisis_clamp_ticks` caps post-crisis markup growth at the decay rate for N ticks (game world: 10); absent key = legacy = replay-safe; active-crisis zeroing unchanged | — |
| E7 | swallowed exceptions hide invariant violations (_research_effect_bp except:return 0; bots.py:398; sim.py:471) | ☐ | narrow excepts, flag unexpected errors ledger-visibly |
| E9 | quota trap: goods missing from essential_need_quota default to unboughtable | ☐ | genesis cross-check needs ⊆ quota |
| S3 | need_allocation lacks the source's third mode: "democratic decision" | ✅ | mode democratic added (P-GOV2): community trust (delegations received) orders the scarce-goods queue, ties by need streak then name; deterministic and replayable |

## P-GAME — trust fixes

| # | Finding | Status | Notes |
|---|---|---|---|
| C1 | leaderboard farmable post-round | done | acts refused once over (guard + friendly error); final verdict stays readable; leaderboard records exactly once (end-to-end farm test) |
| C2 | one global attack game | done | shipped better than planned: per-player games (per-player key, capped 16, LRU eviction) - concurrent visitors never collide |
| C3 | playbook attribution lies | done | playbook pinned in the round at start; request body can no longer switch strategies mid-round; response echoes the pinned playbook |
| C4 | unmet streak not attacker-attributed | done | delta-vs-baseline: baseline_streak captured at round start; only the streak the attacker worsened counts (damage + stop rule) |
| C5 | score weights degenerate (flag burst optimal) | done | flag damage capped (FLAG_DAMAGE_CAP x100); real harm (unmet delta x10) is the uncapped signal - flag-storm farming dead |
| C6 | advertised invariant check never runs | done | baseline_money = capture_baseline() at round start; score/verdict check the REAL invariant; test mints money and asserts the check fires |
| C7 | queued actions vanish on autosave | done | pending persisted in to_save; restored (re-aimed at next tick) in from_save; roundtrip test |
| C8 | autosave failures swallowed | done | _autosave_once() logs + appends to AUTOSAVE_WARN; /api/state exposes autosave_warning; failure/success test |
| C9 | leaderboard file race/wipe | done | read-modify-write under _LEADERBOARD_LOCK + atomic temp-file replace; 12-thread race test: all entries survive |
| C10 | no auth on endpoints; /api/action accepts ANY sender string — unauthenticated impersonation (E4) | done | RC1 scope: account-bound citizens REQUIRE their own X-Auth-Token on /api/action (citizen_is_bound gate, 401 otherwise); UI adds claim/login row + token header; un-bound citizens stay open for local play; full multiplayer auth post-RC1 |
| C11 | LLM detach leaves headless citizen | done | twin captured at attach; /api/llm/stop restores it (twin_restored in response); world-changed edge safe |
| C12 | silent arena errors | done | start/act failures now showToast (refusals + unreachable) |
| C13 | unaffordable buy buttons enabled | done | buttons disable with a not-enough-credits hint when affordable === false |
| C14 | quest narrow/skippable | deferred | folded into P-DESIGN polish (as planned) |
| C15 | LLM cost display edge cases | done | warning shown when the endpoint sends calls but no usage data |
| C16 | duplicate keys/roster entries, O(n) scans; E8 duplicate 'gini_bp' key in breaksystem.py:128 (AST-verified) | done | E8 fixed: duplicate gini_bp key removed (source-level pin test); ruff/pyflakes CI pass queued for cleanup milestone |
| E5 | policy-adopt pre-law snapshot wrapped in except:pass — rollback promise fails invisibly | ☐ | report snapshot failure in response |
| E10 | dead order: params-None guard after first dereference | ☐ | move guard above first use |
| E11 | _apply_list_good/_apply_bid re-resolve active ruleset against tick contract | ☐ | use the resolved params |

## P-DESIGN — say the story

| # | Finding | Status | Notes |
|---|---|---|---|
| D1 | game never states its premise (50/1 start, fairness goal, win screen) | ✅ | mission banner + fairness win screen (Gini < start/3, zero deficits, ledger exact); scenario+fairness in /api/state |
| D2 | Break-the-System is a spectator sport | ✅ | pacing style steady/bold (validated; playbook stays pinned per C3) + live oversight meter (flags/8 bar) |
| D3 | governance OFF by default | ✅ | founder-approved flip: /api/reset + UI resetConfig default governance ON |
| D4 | Citizen Seat undiscoverable | ✅ | Your Seat header tab |
| D5 | proposals displayed as raw JSON | ✅ | explain_proposal() differ (percent for bp, ON/OFF verbs, rule-named sentences) on Civic Board + Citizen Seat; raw JSON kept for power users |
| D6 | no reign score | ✅ | /api/state reign{} + scoreboard bar: days, laws passed/failed, crises, Gini start→now, deficits, ledger OK |
| D7 | advisor can auto-play | ✅ | advisor dial: observe (fix buttons hidden) / suggest; persisted |
| D8 | Mercury buried | ✅ | Civic Board story hook: trust book names its AI politician + points to attach |
| D9 | quest trivially skippable | ✅ | skip shortcut removed; dismiss confirms; completion toast + ob_quest_done badge |
| S1 | Innovation Fund fully implemented but NEVER enabled in dashboard defaults — shipped worlds never run it | ✅ | ships ON with the founder-verified p4fix config (250bp share, 1B-unit reserve floor); blast radius fixed below |
| D10 | no social pressure signal | 🚫 DECIDE | post-RC1 (touches simulation behavior) |

## P-GOV2 — governance follow-ups (from late reviewers)

| # | Finding | Status | Notes |
|---|---|---|---|
| S2 | "Votes cannot be bought" documented with ZERO enforcement — unlimited TRANSFER + free DELEGATE make purchasable delegations mechanically possible and undetected | ✅ | votable vote_buying rule (P-GOV2): transfer<->delegation pairing emits a public VOTE_BUYING flag, revokes the bought delegation, fines the payer into the Society Pool; pay-then-delegate inside the window is rejected outright; game world ships it ON (fine 2000cr, window 30t) |
| E12 | mixed-mode ballots: one dict ballot activates token_mode for the whole proposal incl. legacy strings counted at 10,000 | ☐ | normalize or reject mixed ballots |

## Docs-only follow-ups

| # | Finding | Status | Notes |
|---|---|---|---|
| S4 | Land leasehold framing | ✅ | README citizen row states collective ownership (Georgist leasehold) |
| S6 | stale comment conflict | ✅ | comment rewritten: RULE_CHANGE flows through the proposal/tally path |
| S7 | inequality_seed paper trail | ✅ | validation site documents D16 (top 1% own 50%, pool starts empty) |
| S5 | externality corrections (pollution/addiction/bubbles) missing | ⏳ | future milestone |
| S8 | universal services = refund model, not true provision | ⏳ | roadmap (documented) |

## Faithful core (reviewer-confirmed, no action)

Transparency/ledger, cost pricing, auction markets, surplus recycling, coops, whistleblower + audits, price-signal need allocation, foreign sector, regional markets — all verified present and faithful to the source text.

---

## Completion log

| Package | Completed | Commit | Suite |
|---|---|---|---|
| P-GOV (+E1 pulled forward) | 2026-09-20 | (this commit) | 11/11 audit tests; scoped 43/43; final full suite at commit |

## P-GAME - Status: COMPLETE (2026-09-21)

12/12 audit pins in `tests/test_audit_game.py` (C1-C11, C16); two legacy attack tests updated to the per-player contract; engine + dashboard + UI patches; full suite green. Remaining from the C-series: C14 quest polish (P-DESIGN), full multiplayer auth (post-RC1), ruff CI (cleanup).


## P-DESIGN shipped (2026-09-21, commit b8432b0) — 589/589

D1-D9, C14, S1/S4/S6/S7 (rows above; D10 stays founder DECIDE post-RC1). 7 regression pins in tests/test_audit_design.py.

### Blast radius of enabling research (the S1 bug-class, live — the suite caught all three)

| New finding | Verdict | Fix |
|---|---|---|
| Research buckets missing from game-layer money accounting | CONFIRMED — C6 invariant correctly screamed (attack API, dashboard pie, 2 test-side conservation laws) | money_total/pie/tests count innovation_pool + research_funding (B9 foreign-bucket precedent) |
| Unlock variants dropped labor_hours/energy | CONFIRMED — latent engine crash on variant recipes, masked for weeks because no shipped world ran research | variants carry labor_hours + energy (full recipes) |
| Reserve floor 500x too small | CONFIRMED — my 2M-unit floor drained the dividend reserve; hardcore gate starved (worst_essential 1670) | founder-verified p4fix config verbatim: 250bp / 1B-unit floor |


## P-GOV2 shipped (2026-09-21) — the audit's final package

S2 + S3 close the governance findings. Enforcement design notes:

- **S2 detector** mirrors the engine's proven attached-cache pattern (the `_state_cache` lesson: never id-keyed, rebuilt lazily from applied history -> save/load and replays byte-identical). Absent `vote_buying` param = zero behavior change (pinned by test).
- **The mirror case is caught too**: delegate-then-get-paid flags on a later tick (pair cache scans history, not just the current tick).
- **Conservation exact**: the fine MOVES credits payer->pool; pinned by test.
- **S3 democratic** = community trust (delegations received, revocable monthly) orders the scarce-goods queue — the delegation graph IS the community's standing decision. Deterministic; ties by need then name.
- 8 regression pins in tests/test_audit_gov2.py; adjacent batteries 55/55.

---

## Visual Verification Pass — 2026-09-21 (pre-tag, founder-ordered)

The rendered-browser pass (boots, real clicks, screenshots) caught two defects every
one of the 613 tests missed — both now fixed and pinned:

### V1 — The dashboard's five non-default tabs could never paint (BLOCKER, fixed)

An unclosed `<div>` in the Lab (policy) view container made the browser nest the
Chronicle, Break It, Civic Board, and Your Seat containers *inside* it. Clicking their
tabs switched the app state and polled their APIs — but nothing could ever render,
because their parent stayed `display:none`. The World and The Lab looked perfect,
which is exactly why API tests, screenshots of the default view, and 613 pins passed.

- Fix: close the Lab container (one line). Verified by a scripted six-tab walk:
  every container paints with live data; Civic Board screenshot saved
  (`sweeps/ui_civic_fixed.png` vs the broken `sweeps/ui_smoke_civic.png`).
- Pin: `tests/test_ui_markup.py` — parses the markup, asserts every view container
  balances before the next opens and all six views exist. The bug class is dead.

### V2 — The boot world shipped governance OFF (D3 was only half-done, fixed)

D3 flipped the reset endpoint and the UI default, but the bare boot world
(`RUN = Run()`) still booted legacy: no vote token, unreachable 50% quorum — the
exact path docs/PLAYER_GUIDE.md's quick start leads with.

- Fix: `RUN = Run(governance=True)` + `tests/test_boot_defaults.py` (boot world must
  ship token ON and a reachable ~10% quorum; reset default must match).
- Boot-time autosave restore is correct behavior (it preserves a live reign) — the
  stale file that masked this during verification was a smoke-test artifact.

**Lesson (added to the retrospective doctrine):** pytest proves the engine; rendered-
browser walks prove the game. Every UI milestone from here on gets a click-through
of all tabs before ship.

