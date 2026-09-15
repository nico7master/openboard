# Priority 4 Findings — Combinations (Land+Trade, Disaster+Trade, Everything-ON)

**Date:** 2026-09-13 · **Probe:** `scripts/p4_probe.py` · **Analyzer:** `scripts/p4_analyze.py`
**Data:** `sweeps/p4/*.json` (12 runs, 650 ticks, 1000 citizens, seeds 7/42/123, memrun'd)

## Setup

Bots have zero trade logic (P1), so every arm embeds **5 scripted, fully-fed trader
citizens** (pool-funded via recorded `add_citizen`, 3M units each, no mint). The trader
book each tick: BUY_ESSENTIAL (self-feed), IMPORT grain at world 200 vs domestic 300,
and a staggered cycle: BID bread at 2× baseline (outbids citizens), then EXPORT pantry
bread above a 10-unit reserve at world 400 (700 during the drought-aligned shock at t=533).

Pairs against existing corners (same seed, same shock streams):
`trade_only↔p2/skills_off`, `land_trade↔land_study/dump`, `disaster_trade↔p3/disaster`,
`all_on↔disaster_trade`. all_on = shocks + land + traders + skills + realistic spoilage
(7–60 tick shelf lives) + research 250bp.

## Conservation (all 12 runs PASS)

`money_delta + Δforeign_balance + Δresearch_funding == 0` exactly in every run.
Note for future probes: `stage6.money_delta` covers neither the foreign bucket nor the
research bucket — both must be added when those systems are on.

## Verdicts

| Question | Verdict | Evidence |
|---|---|---|
| **Land + Trade: do local farmers die out?** | **No — systems compose cleanly.** | Production 73.8–75.4k (≈ dump baseline). LVT 31,798 units, all 23 parcels foreclosed back to society in every seed; the dump payout (1.935M) and trader extraction are independent, additive drains. |
| **Disaster + Trade: safety net or drain?** | **Neither — a wash in bot worlds.** | Drought-window unmet: 951 vs 906 (s7), 811 vs 966 (s42), 871 vs 916 (s123). Traders exported 3.7–4.2k bread (~0.4% of stock) at famine prices — a real but small drain. No safety net exists because bots cannot import food; only scripted traders can. |
| **Everything ON: does the model hold together?** | **NO — pool dies at t≈180, but the killer is ONE known lever.** | see below |

## The all_on collapse: research share is a stock-proportional pump

`research.fund_pool_phase` takes `surplus_pool × research_share_bp // 10_000` **every
tick**. At 250bp that is 2.5%/tick of the *stock* — a compounding drain with a ~28-tick
half-life. In all 3 seeds the 2.07B Society Pool hit <1M by **t=180** and ended at ≤20
units; **1.83B** sits (conserved, verified) in `research_funding` as permanent
"know-how". With the dividend channel dead: gini **+5,200bp** (≈7,850–8,140), production
**−17%** (60.9–61.6k vs 73.2–76.7k), unmet worse in 2/3 seeds.

This confirms and sharpens the atlas finding (corrected WINs: 0bp 27/27, 250bp 21/27,
500bp 0/27): **research is not just a luxury lever — any stock-proportional share is
structurally fatal on long horizons.** Fix direction: fund research from surplus *flow*
(per-tick surplus income, capped) or a fixed budget, never a % of pool stock. Not fixed
here — engine untouched in this study.

## Trade-only extraction math (for game balance)

5 traders × 3M bankroll over 650 ticks: imported 32,550 grain (tariff take **413,250**
units into the pool), exported 3,695–4,170 bread for **1.67M** credits, net pool drain
**−0.67% to −1.37%** vs control. Gini +147/+81/−59 bp (noise-level). A ~1% pool leak per
650 ticks per 5 traders is tolerable; it scales with trader capital and count.

## Anomalies

- **land_trade_s42 gini 4,352** (siblings ≈2,700–2,800): one late-founded bakery coop
  (`baker_x1`) concentrated **16% of all citizen money** across its 12 members (~4.81M
  each) by t=650. Not land-related (all parcels society-owned). Mechanism undiagnosed —
  candidates: wage/distribution interplay in that seed. Targeted probe if coop-level
  concentration matters for the game.
- Deterministic repro: `PYTHONHASHSEED`-free engine reproduced the exact trajectory on
  rerun (`/tmp/p4_s42_top.log`).

## Caveats

- Traders are scripted ideal arbitrageurs (no transport cost, no failure); real players
  would extract less. The 1%/650-tick figure is an **upper bound per 15M trader bankroll**.
- The disaster+trade import channel (food INTO the economy) is untestable with bots;
  needs the multiplayer layer or a trader-bot that dumps imports into BUY-priced listings.
- all_on used research 250bp (contract-test default); 0bp would isolate the rest of the
  stack — likely stable, but not separately run here.

## Design takeaways

1. **Compose with confidence:** land, trade, skills, spoilage, disasters coexist without
   interference — no hidden cross-system breakage found.
2. **Fix research funding before any "full realism" preset ships.**
3. Player-facing trade needs *limits or tariffs as tuning knobs* — extraction is real,
   mild at 5 traders, and linear in trader capital.
4. Money-identity tooling must include foreign + research buckets (probe pattern above).
