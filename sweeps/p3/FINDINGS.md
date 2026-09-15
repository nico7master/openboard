# Priority 3 Study: Hidden Systems — FINDINGS

**Date:** 2026-09-12 | **Data:** `sweeps/p3/*.json` (15 runs: 5 arms × 3 seeds, 650 ticks, 1000 citizens) | **Scripts:** `scripts/p3_probe.py`, `scripts/p3_analyze.py`

## Setup
- Every arm runs the SAME harsh shock profile (`0.8%/tick`, default `rng_seed=0`). The engine re-seeds the shock RNG per tick (`Random(f"{seed}:{tick}")`), so all arms with the same world seed received **byte-identical disaster sequences** (verified: 6 shocks per seed, first at t=61, counts identical across arms).
- Pairs vs the shared `disaster` arm isolate exactly one hidden system: `disaster_spoil` (+perishability), `disaster_memory` (+demand memory), `disaster_wear` (+durable capital ON — see wear note), `disaster_nowear` (durable capital OFF).
- Healthy (no-shock) control = P2 `skills_off` runs.
- **Base-scenario caveat discovered:** `durable_capital` (wear, durability 20) is enabled by `dashboard/server.py` for EVERY run — including P1/P2 and the `disaster` arm itself. So `disaster_wear` vs `disaster` is wear-ON vs wear-ON; the meaningful comparison is `disaster_nowear` (wear OFF) vs `disaster` (wear ON).
- Money conservation held in all runs (`money_ok=True` everywhere).

## Verdicts

| Question | Verdict |
|---|---|
| **Disasters — do shortages cascade or stop?** | **STOP. The economy absorbs the harsh profile.** Paired against the healthy control, shocks shifted unmet needs within the normal chaotic band (final unmet 261–886 vs control 321–616; production events within ±0.5% of control; Gini unchanged). No cascade, no death spiral, machines stable. **Recovery, not collapse — ship shocks.** |
| **Spoilage — does rot stop hoarding or just cause waste?** | **CATASTROPHIC WASTE — PERMANENT FAMINE.** With shelf lives 2–10 ticks on foods, unmet need pins at ~950–966 of 966 citizens from tick ~55 to the end in ALL 3 seeds — and the famine starts BEFORE most shocks land, so **rot alone causes it**. ~618k units of food rot per run (vegetables 185k, fruit 117k, fish 90k, bread 76k…); final food inventories collapse to near zero; Gini rises ~310 bp. The economy's multi-tick buffer stock is converted to waste and never recovers. **Do NOT ship with short shelf lives; if spoilage ships, use long shelf lives (weeks, not days) or only on prepared foods.** |
| **Panic buying — does shortage memory deepen crises?** | **INERT (by design, in bot worlds).** The feature wires up correctly — shortage memory accumulates (996 entries at smoke scale, all on essentials: bread/water/electricity) — but bots deliberately exclude essentials from the hoard bonus (panic-guard: flat 2× ceiling), and market goods never go chronically short in this economy. Result: byte-identical to the plain-disaster arm in all 3 seeds. **Harmless dead code for bots; may matter with human players or market-good shortages.** |
| **Machine wear — do breakdowns crash production?** | **NO — wear is the affordability keystone, not a threat.** Paired nowear (wear OFF) vs disaster (wear ON) under identical shocks: without wear, machines are consumed 1-per-run instead of amortizing over 20 runs, and the capital chain collapses — production events −23% (−16.7k to −20.7k), final machine stock −23% (~−1,220 units in all 3 seeds), unmet +40/+350/+537, Gini +380 to +490 bp. With wear ON (the default in every run, including all previous studies), replacement demand is only ~5% of gross usage and no breakdown cascade ever fires. **Keep wear ON; it is load-bearing.** |
| **New businesses — do new coops make everyone richer?** | **NEVER HAPPENS in bot worlds.** Zero emergent foundings (tick>2) across all 12 shock runs. The entrepreneur trigger requires a chronic shortage (unmet ≥5 ticks) with ZERO active listings — but under supply shocks farms keep listing at reduced output, so the trigger never fires. The FOUND_COOP flow itself is unit-tested and works. **Design note: if emergent entry is desired, trigger on persistent unmet need OR thin listings (e.g. <N days of stock), not zero listings.** |

## Bonus finding: engine determinism is ironclad
- The P3 `disaster` arm **reproduces P2's `crisis_off` runs byte-identically on all 3 seeds** (same pop/unmet/pool/gini/production/deaths) — separate processes, weeks apart.\- Shock streams aligned across all arms per seed (verified in analyzer output). Same seed → same world, even across code changes that don't touch the tick path. This is exactly what the land-study chaos rule needs: within-seed A/B is trustworthy.

## Caveats
- "Unmet" counts citizens with any unmet essential in the sample tick; bots do not die of unmet needs in 650 ticks, so "famine" here means permanent deprivation, not mortality.
- Shelf lives (2–10) were MY choices from test values, not engine defaults — the engine ships with perishability OFF. The catastrophe verdict is about short shelf lives specifically.
- The wear verdict above corrects an A/B that initially compared wear-ON vs wear-ON (byte-identical, as determinism predicts). The disaster arm remains a valid wear-ON reference for the nowear comparison.
- Zero emergent foundings is a statement about THIS bot economy (supply shocks never zero out listings); it does not test the founding mechanics themselves (covered by `tests/test_entrepreneur.py`).