# Priority 2 Study: Skills, Voting, Crisis Mode — FINDINGS

**Date:** 2026-09-12 | **Data:** `sweeps/p2/*.json` (18 runs: 6 arms × 3 seeds, 650 ticks, 1000 citizens) | **Scripts:** `scripts/p2_probe.py`, `scripts/p2_analyze.py`

## Setup
- Within-seed A/B pairs per the chaos rule (FINDINGS.md in `sweeps/land_study/`): single extra citizens flip whole trajectories, so only same-seed comparisons count.
- `skills_on`: +5%/level output, +3%/level wage, 100h/level, cap 5.
- `vote_bad`: 70%-of-population referendum for a 50%/tick wealth tax above 500 cr, governance quorum 50%.
- `crisis_on/off`: identical harsh shock profile (0.8%/tick); crisis arm force-declares pre-ratified emergencies at t=100/300/500 (max 100 ticks each).
- Money conservation held in all 18 runs.

## Verdicts

| Question | Verdict |
|---|---|
| **Skills — does training create a machine bottleneck?** | **NO.** Machine stock ends HIGHER in all 3 seeds (+735/+1347/+1516). Food security improves in 3/3 (unmet −306/−145/−82). Production-event count falls in 2/3 because +5%/level means fewer runs for the same output — efficiency, not decline. Small Gini rise (+63/+173/+982) from the wage premium. **Skills are safe to ship.** |
| **Voting — can a majority vote to kill its own economy?** | **YES, they will vote for it — and it doesn't kill anyone.** 703/1000 citizens approved the confiscatory tax in all seeds. It fired ~420,000 times, collecting ~305M units (≈18% of the money cap), production fell in 3/3 (−2.3k to −8k events), Gini collapsed ~2,400bp: a poorer but more equal economy. Deaths stayed 0 and unmet improved in 2/3 — dividends keep flowing even after savings are confiscated. **Democracy is self-harming but not fatal.** |
| **Crisis — does the emergency override protect the food supply?** | **YES.** With identical shocks, the crisis arm cut unmet needs by 435/520 people in seeds 7/42 (seed 123 +93). Cost: ~22% fewer production events in 3/3 (−15.6k/−17.0k/−16.3k) — the override visibly redirects labor from luxury chains to essentials. 300 crisis ticks total, ratified, zero deaths, money conserved. **The emergency lever works as intended and is worth its production cost.** |

## Bonus finding: proposal spam
Under open governance, bots propose ~270 rule changes per run, nearly all failing with ~20 votes (the yes-voters from p1 keep proposing). The ledger absorbs it, but a real game UI would drown. **Design gate needed:** proposal deposit or cooldown per citizen.

## Caveats
- `vote_bad` electorates are scripted (72% yes); real players may vote differently — but the mechanism (majority confiscation → poorer-but-stable) is what the test proves.
- Crisis declarations were pre-ratified (`source="vote"`), skipping the in-crisis ratification vote path; that path remains covered by `tests/test_crisis.py` only.
- Shock hits are stochastic; harsh-profile pairs share seeds but not identical shock draws — the 2/3-vs-1/3 splits on unmet should be read as directional, not exact.
- Bots do not die of unmet needs within 650 ticks at these scales, so "deaths" is not a discriminating metric in this study.
