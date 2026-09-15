# Study: Society in Motion — lever interactions, sequencing, and society trajectories

**Date:** 2026-09-13 · **Status:** approved (user demand, 2026-09-13) · **Author:** Agent Zero

## Motivation (user critique, verbatim)

"We have not learned if we pull lever A then B will be influenced in that way.
Only that it's safe to pull A. I want to know what happens to society!"

The critique is correct on three counts:

1. **Interactions:** prior A/B studies measured each lever against a fixed baseline
   (A on vs off, everything else default). We know little about whether B's effect
   CHANGES when A is already on.
2. **Sequencing:** we never varied the ORDER or TIMING of pulling levers. In a real
   game, players pull levers over time — early research vs late research, emergency
   powers at famine onset vs after the graves.
3. **Society trajectories:** we reported end-state aggregates (final Gini, final
   production, final unmet). We never told the story of a society over time: when
   the famine windows hit, what happened to prices and wages, whether the middle
   class held, whether dividends survived.

Fair correction to the record: partial interaction evidence exists — crisis mode was
-tested DURING identical disaster streams (P2), P4 tested 3 rule combos against
single-lever baselines, `sweeps/unequal_rerun/` is a tax×dividend dose grid, and
`sweeps/atlas/` is an 81-run dose study. Sequencing and society timelines, however,
were never studied. This study closes both gaps.

## What "what happens to society" means (operational metrics)

Every run emits a **society timeline**: per-100-tick snapshots plus final, of:

| Metric | Society question it answers |
|---|---|
| `unmet` (count) + longest unmet streak | Are people going hungry, when, for how long? |
| Wealth shares: top 1% / middle 60% / bottom 20% | Who holds the money — aristocracy or broad class? |
| Bread price index (t=0 = 100) | Can a wage still buy dinner? |
| Real wage (wage / bread price) | Are workers winning or losing? |
| Dividend per person (pool payout flow) | Is the socialist pillar alive? |
| Top-coop money share | Did a firm become a leviathan? |
| Event log: foreclosures, foundings, bankruptcies, crises | What actually happened, in order |

## Part A — Two-lever factorials (does B behave differently under A?)

Standard 2×2 per pair: `{none, A, B, A+B}` × seeds {7, 42, 123} = 12 runs per pair.
Interaction effect per metric = `(AB − A − B + none)`, computed within seed.

Pairs chosen for society stakes:

1. **Spoilage(long) × Disasters** — rot at *shippable* week-scale shelf lives
   (14–30 ticks) alone was survivable in P3-adjacent settings; disasters alone were
   fine. Does the combination (shocks destroying buffer stock INTO a rotting
   pipeline) tip into famine? This is the "which safe rule becomes unsafe together"
   question at its sharpest.
2. **Skills × Research(fixed, floor ON)** — both boost productivity. Do they
   compound (superlinear prosperity), or crowd (both bid for the same labor/machines)?
3. **Wealth tax (800bp) × Land dump** — two anti-rich levers at once: do they
   jointly destroy capital accumulation (production collapse), or is the economy
   robust to double taxation?

(Reused existing evidence, not rerun: **Crisis × Disasters** — P2 ran crisis under
byte-identical shock streams: crisis fed 435–520 more people at ~22% production
cost. That is already a lever-under-lever result.)

## Part B — Sequencing (the SAME levers, different order/timing)

1. **Research early vs late** (floor ON, full stack otherwise): fund from t=50
   (young society invests) vs from t=400 (mature society invests) vs never.
   The atlas verdict "research is a late-game luxury" was measured under the BROKEN
   rule — must be retested under the fix. 3 cells × 3 seeds = 9 runs.
2. **Crisis timing**: emergency powers declared at disaster onset vs 100 ticks late
   (after the shortage bites), identical shocks otherwise. 2 cells × 3 seeds = 6 runs
   (crisis-never baseline = P2 `crisis_off` with the same shock streams).

## Run budget & safety

- 36 (Part A) + 15 (Part B) = **51 runs**, 650 ticks, 1000 citizens each.
- Sequential via `scripts/memrun.sh`, one world at a time, ~4–5 min/run pinned
  ⇒ ~3.5–4 h wall clock. `pgrep` guard before every launch.
- Same conservation + determinism checks as P2–P4 (extended money identity exact;
  shock streams byte-identical per seed across arms).

## Deliverable

`sweeps/society/FINDINGS.md`: for each pair — the interaction decomposition table
(per metric, per seed), plus **plain-language society stories** for each cell
("In the world with rotting food and storms, the bottom 20% lost everything by
tick 300 while the top 1% doubled — the famine window was ticks 180–420...").
Sequencing section answers: does it matter WHEN you pull the lever?

## Success criteria

1. Every cell: conservation exact, shocks identical within seed, no framework impact.
2. Interaction effects reported with within-seed pairing (chaos rule respected).
3. At least one clear interaction or sequencing effect identified in plain language
   — or an honest "no interaction beyond chaos band" verdict per pair.

## Amendment: research.start_tick (Part B sequencing, 2026-09-13)

Part B needs research funding to start at t=50 (early) vs t=400 (late) vs never
on the exact P4 `all_on` config. Engine change (one clause in
`src/openboard/research.py::fund_pool_phase`):

- **Mechanism:** `research.start_tick` (optional int, default 0). While
  `tick < start_tick`, `fund_pool_phase` returns `[]` — no `RESEARCH_FUND`
  event, no pool transfer, no allocation. From `start_tick` on, the share and
  `reserve_floor` arithmetic are byte-identical to the fixed rule. Negatives
  clamp to 0. Nothing is back-filled: a late start simply funds later (the
  pool keeps the un-taxed surplus until then).
- **Replay guarantee:** the key is absent (or 0) in every pre-existing config
  ⇒ `tick < 0` is never true ⇒ the added check is inert and all old worlds
  replay byte-identically. `allocate_fields_phase` and `research_effect_bp`
  are untouched — they only see money that `fund_pool_phase` already moved.
- **Tests:** `tests/test_research.py::test_funding_start_tick_sequencing`
  (inert strictly before start_tick, active exactly at it, composes with
  `reserve_floor`, negatives clamp) and
  `test_funding_start_tick_absent_replays_identically` (absent and 0 both
  reproduce the old amounts exactly).
- **Harness wiring:** `scripts/society_probe.py` arms `research_early`
  (start_tick 50), `research_late` (400), `research_never` (research
  disabled) on the exact `p4_probe.P4Run` all_on config + `reserve_floor`
  1B. `research_never` differs from the P2 `skills_off` control only by the
  P4 trader/land/shock stack, so it is the correct no-research reference for
  this factorial.
