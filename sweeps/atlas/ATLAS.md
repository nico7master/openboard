# Lever Atlas Playbook

runs=81 baseline=tax400/div3000

verdicts: {'WIN': 27, 'broken': 54}

## L1 interest
-     0: n=27 WIN= 9 mean_top1=559bp worst_ess=345
-   300: n=27 WIN= 9 mean_top1=559bp worst_ess=345
-   600: n=27 WIN= 9 mean_top1=559bp worst_ess=345

## L2 scarcity cap
-     0: n=27 WIN= 9 mean_top1=559bp worst_ess=301
-  1250: n=27 WIN= 9 mean_top1=559bp worst_ess=306
-  2500: n=27 WIN= 9 mean_top1=559bp worst_ess=345

## L3 research share
-     0: n=27 WIN=27 mean_top1=548bp worst_ess=7
-   250: n=27 WIN= 0 mean_top1=563bp worst_ess=205
-   500: n=27 WIN= 0 mean_top1=565bp worst_ess=345

best single run: rate=0 markup=2500 research=0 seed=123 top1=547bp verdict=WIN

## Post-Fix Correction (2026-09-11, commit b3850a7)

The 81 run JSONs above carry `inv_bad` computed with a STALE money identity
(research_funding bucket uncounted) — run pre-fix. Verdicts in the raw JSONs
are therefore partly an accounting artifact, NOT engine truth.

Two real findings survived scrutiny:

1. **Engine bug (fixed in b3850a7):** allocate_fields_phase destroyed the
   floor-division remainder every tick (measured -1..-17 credits/tick at
   research=500bp). Post-fix diag: inv_bad=0 (sweeps/atlas/diag_i0000_m0000_r0500_s42.json).
2. **Behavioral (stands):** research share diverts surplus from dividends
   and starves essentials. Corrected verdicts (ess<=30 & top1<1500bp,
   identity-independent fields):

| research_share_bp | corrected WIN | worst_ess |
|---|---|---|
| 0 | 27/27 | 7 |
| 250 | 21/27 | 205 |
| 500 | 0/27 | 345 |

Game-design read: research is a LUXURY lever — only safe once essentials
are over-provisioned; at 250bp some seeds still hit 200+-tick starvation.
