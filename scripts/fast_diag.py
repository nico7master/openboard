#!/usr/bin/env python3
"""Fast diagnostic: 300 ticks with live invariant alarms.

Purpose (user request 2026-09-06): catch emergent bugs in SECONDS, not the
2-10 min a 2,000-tick gate takes. Every bug class found by long gates showed
an early signature (bid rejections, debt growth, dead producers, unmet
streaks). This rig watches those signals live and reports WHERE they are.

Usage: python scripts/fast_diag.py [seed] [ticks]
"""
import random, sys
from collections import defaultdict
sys.path.insert(0, 'src'); sys.path.insert(0, 'dashboard')
from server import Run

seed = int(sys.argv[1]) if len(sys.argv) > 1 else 42
ticks = int(sys.argv[2]) if len(sys.argv) > 2 else 300
run = Run(seed=seed)

ESSENTIALS = {'bread', 'water', 'electricity', 'meals'}
rej_reasons = defaultdict(int)
debt_hist = []
prod_last = {}   # coop -> last PRODUCE tick
unmet_streaks = defaultdict(lambda: defaultdict(int))  # cit -> good -> streak

print(f'fast_diag: seed={seed} ticks={ticks}')
for t in range(2, ticks + 2):
    actions = []
    for name, meta in sorted(run.bots.items()):
        rng = random.Random(f'{seed}:{t}:{name}')
        actions.extend(meta['fn'](name, run.state, run.state.active_ruleset_params(), t, rng))
    run._apply_batch(t, actions)
    for r in run.ledger.records:
        if not r.accepted and r.reason:
            rej_reasons[r.reason] += 1
        if r.accepted and r.tx and r.tx.get('action') == 'PRODUCE':
            pay = r.tx.get('payload') or {}
            prod_last[pay.get('coop_id')] = t
    # debt trajectory
    tot_debt = 0
    for cd in run.state.coops.values():
        wd = cd.get('wage_debt')
        tot_debt += sum(wd.values()) if isinstance(wd, dict) else (wd or 0)
    debt_hist.append(tot_debt)
    # unmet streaks (essentials only)
    for c, d in run.state.unmet_needs.items():
        for g, v in d.items():
            if g in ESSENTIALS and v >= 1:
                unmet_streaks[c][g] = max(unmet_streaks[c][g], v)
    run.state.applied.clear(); run.batches.clear()
    recs = run.ledger.records
    if len(recs) > 4000: del recs[: len(recs) - 1000]

s = run.state
print(f'--- ALARMS after {ticks} ticks ---')
# 1. rejection storm
storm = {k: v for k, v in sorted(rej_reasons.items(), key=lambda x: -x[1])[:5]}
if storm:
    print(f'REJECTIONS (top 5): {dict(storm)}')
    big = [k for k, v in rej_reasons.items() if v > 50]
    if big:
        print(f'  !! STORM: {big} — inspect these BEFORE the gate fails')
# 2. debt trajectory: growing every check?
if len(debt_hist) >= 3:
    growth = debt_hist[-1] - debt_hist[len(debt_hist)//2]
    print(f'WAGE DEBT: start-mid growth {growth:+.0f} (last {debt_hist[-1]:,.0f})')
    if debt_hist[-1] > 200_000:
        print('  !! debt spiral forming — check wage draw vs revenue')
# 3. dead essential producers
for cid, cd in sorted(s.coops.items()):
    rid = cd.get('recipe_intent') or cd.get('trade') or ''
    rec = s.recipes.get(rid) or {}
    outs = set(rec.get('outputs') or {})
    if outs & ESSENTIALS:
        last = prod_last.get(cid, 0)
        if t - last > 50:
            print(f'  !! DEAD essential producer {cid} ({rid}): no PRODUCE for {t - last} ticks')
# 4. unmet essentials
worst = {}
for c, gs in unmet_streaks.items():
    for g, v in gs.items():
        worst[g] = max(worst.get(g, 0), v)
print(f'UNMET essentials worst streaks: {dict(worst) or "none"}')
if any(v > 5 for v in worst.values()):
    print('  !! streaks growing — trace the worst good early while it is cheap to do so')
print('--- done (seconds, not minutes)')
