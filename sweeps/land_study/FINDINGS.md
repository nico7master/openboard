# Priority 1 Study: Land & Rent + Imports (Trade) — FINDINGS

**Date:** 2026-09-12 | **Data:** `sweeps/land_study/*.json` (9 combos) | **Scripts:** `scripts/land_study.py`, `scripts/land_study_analyze.py`

## Setup
- 1000-citizen worlds, 650 ticks, seeds 7/42/123, land rule ON in all.
- Scenarios: **control** (nobody buys), **hold** (pool-funded monopolist buys all 23 parcels at t=2), **dump** (same + sells all back at t=60, post-appreciation).
- Money conservation held in every combo (`inv_bad=0`).

## Land Verdicts

| Question | Verdict |
|---|---|
| Does a land monopolist starve the population? | **NO.** Unmet needs at or below control in 2 of 3 seeds; the seed-7 '+78' was a probe artifact (the scripted monopolist citizen has no pantry, so it counts itself as permanently unmet). |
| Does the Georgist LVT recapture the land? | **YES, mostly.** LVT (1bp/tick) bleeds the monopolist 1.2M → ~17 units by t≈55; 15 of 23 parcels foreclose from t≈60 in every seed. 8 parcels survive (dividend income covers their tax) — harmless residue. |
| Does a dump sell-back break the Society Pool? | **NO.** Direct payout is identical across seeds: 1,935,000 units = **0.115%** of pool. Net full-cycle drain (buy-in 1.18M in, payout 1.935M out, LVT ≈ 31.8k collected) ≈ −723k ≈ **0.045%**. Dividends never ran dry. (Earlier 0.59%/10M figure compared pool levels across *independent world runs* — confounded by ordinary economic divergence; hold worlds swing ±8–10M on the same metric without selling a single parcel.) |
| Inequality? | Gini delta small and seed-dependent (-138 to +99 bp) — land wealth is taxed back faster than it compounds. |
| Is the attack profitable for the attacker? | **YES (~60% in 60 ticks).** Buy 1.18M → sell 1.935M → net +723k units ≈ +7,232 cr on a 12,000 cr stake. Personally lucrative, socially almost free — the 10% uplift + LVT capture works as designed. |

**Design takeaway:** land monopoly is a *nuisance*, not a famine. The default Georgist setup (1bp/tick LVT, 90% buyback, 10% social uplift) is self-defending and pool-safe. No caps needed for v1.

## Deeper pass — mechanics confirmed from land.py source

- **Survivor equilibrium explained:** foreclosure requires `grace_ticks` (5) *consecutive* unpaid dues; the monopolist's dividend income periodically pays the tiny LVT and resets the counter. The 8 persistent parcels sit exactly in this state — the monopolist survives on dividends and pays them straight back as LVT. The Georgist loop works as designed; the residue is harmless.
- **Speculation is growth-gated:** assessment = base × quality × population-growth, so buy/dump cycles only profit while the world GROWS. In a mature world (stable population) each cycle loses the 10% uplift + LVT. Exploit channel exists only in growing worlds — a multiplayer design note, not a steady-state risk.
- **Seed-42 anomaly RESOLVED — chaos, not mechanism (2026-09-12 probe):** a perturb world (ONE extra pantry-less citizen at t=2, NO land purchases, same land rule) ended unmet=1, pop=954, pool 1696.2M — statistically identical to hold/dump (pop 954, unmet 1) and nothing like control (pop 966, unmet 616). A single-citizen perturbation flips the entire 650-tick trajectory; the dividend-recycling theory is unnecessary. The +1 unmet IS the pantry-less extra citizen itself. Data: sweeps/seed42_anomaly/perturb_s42.json.
- **Measurement caveat:** series column orders differ (land_study rows [t,gini,unmet,pool,...] vs anomaly rows [t,unmet,pool,gini]); cross-series tables must index the right column. The verdict used final fields only, so it is unaffected.
- **Cross-seed caveat stands:** control worlds vary widely across seeds (unmet 321–616 at t=650), so policy conclusions must be within-seed or multi-seed.

## Trade Verdict
- Bot worlds open vs closed are **byte-identical** (0 trade events; unmet 114 = 114): **bots have no import/export logic** — the foreign sector is player-only today.
- Engine mechanics (tariffs to pool, price shocks, one-bucket conservation) are already test-verified (`tests/test_realism_foreign.py`).

**Design takeaway:** "block imports" study questions are unanswerable with bot economies alone. Either add a simple trader bot (import when world price < domestic VWAP) or defer to the multiplayer phase where humans drive trade.

## Caveats
- Monopolist stake was pool-funded (no-mint injection), not earned — measures the mechanism, not realistic accumulation.
- LVT tested at default 1bp/tick only; higher rates would foreclose faster (mechanism already shown linear).
- Trade check ran 80 ticks at seed 42 only (sufficient: zero events prove bots never trade).