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
