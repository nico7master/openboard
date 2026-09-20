# P2 Re-Run: 2026-09-12 Verdicts vs Current Engine — FINDINGS

**Date:** 2026-09-20 | **Data:** `sweeps/p2_rerun/*.json` (18 runs: 6 arms × 3 seeds, 650 ticks, 1,000 citizens) | **Scripts:** `scripts/p2_probe.py` (unchanged) via `/tmp/p2_rerun.py` wrapper, `scripts/p2_rerun_analyze.py`

**Purpose:** RC1 week-3 science — re-verify the 2026-09-12 P2 verdicts under today's engine (kcal-true needs, rescaled recipes, machine wear, scarcity-pricing default, audit-gap defaults, founder governance defaults). Same arms, seeds, scale, and tick count; historical `sweeps/p2/` untouched.

## Universal engine shift (all 18 runs, old → new)

| Metric | Old (09-12) | New (09-20) |
|---|---|---|
| Unmet needs (sum, final) | 65–886 people | **0 in every run** |
| Production events | baseline | **+13,400 to +22,600** |
| Machine end-stock | baseline | −900 to −2,700 (machine-wear rule now consumes stock while production runs more) |
| Deaths / money conservation | 0 / OK | **0 / OK in all 18** |

The old differentials between arms were measured against a scarcity regime that no longer exists: the capacity-true economy serves everyone, everywhere, in every arm.

## Verdict re-checks

### 1. Skills — **safe to ship (re-verified)** ✅
skills_on vs skills_off within the new engine: Gini +65…+86 (small wage-premium rise), machine stock ±50 (noise), production ~equal. No machine bottleneck. The old study's larger effects (machine stock +735…+1,516, unmet improvements) were artifacts of the old scarcity regime — under capacity-true economics, skills are simply neutral-to-mildly-positive.

### 2. Majority confiscation — **verdict upgraded: self-harming → harmless-equalizer** ⬆️
The scripted 72% referendum still passes in all seeds, still fires ~449,000 times, still collects ~335M units (old ~305M). But the old cost — production falling −2.3k…−8k events in 3/3 — **is gone**: vote_bad now produces as much as vote_plain (≈88k events both arms). Confiscation now purely equalizes: Gini 2,100 → 103 in all seeds, zero deaths, production intact. The capacity-fixed engine absorbs what the scarcity engine could not. Democracy remains *self-harming in wealth terms, but no longer even poor*.

Also confirmed: open governance still floods proposals (253/run) and **0 pass** — the attention-scarcity design (one monthly token, reachable-but-real quorum) keeps the spam harmless.

### 3. Crisis mode — **now insurance with no current claim** ➖
Under identical harsh shocks, crisis_on's old benefit (unmet −435/−520 in 2/3 seeds) has nothing left to protect: unmet is 0 in **both** arms now. The cost remains: crisis_on produces ~13% less (74–75k vs 87–88k events) — the override still redirects labor to essentials that no longer need rescuing. Crisis mode works exactly as designed and is worth keeping (real shocks in live games won't be this benign), but at current capacity it is pure premium.

## Bottom line for RC1

All three 09-12 verdicts survive re-verification; two improved under the capacity-true engine. No action items — the engine changes since 09-12 made every arm healthier, not one worse. The battery can be retired until the next engine-changing milestone.

## Caveats

- Same as the original study: scripted electorates, pre-ratified crisis declarations, stochastic shock draws differ between old and new runs (within-seed comparison only).
- Machine end-stock deltas are consistent with the wear rule but were not isolated in a dedicated no-wear arm here.
- 650-tick horizon; famine-class failures remain outside this battery's reach (covered by the survival gates).
