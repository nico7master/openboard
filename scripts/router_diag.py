import random, sys
sys.path.insert(0, 'src'); sys.path.insert(0, 'dashboard')
from server import Run
from collections import defaultdict

seed = 42
run = Run(seed=seed)
joins = defaultdict(int); leaves = defaultdict(int)
join_fail = defaultdict(int); leave_fail = defaultdict(int)
memb_hist = {}
for t in range(2, 2001):
    actions = []
    for name, meta in sorted(run.bots.items()):
        rng = random.Random(f"{seed}:{t}:{name}")
        actions.extend(meta['fn'](name, run.state, run.state.active_ruleset_params(), t, rng))
    run._apply_batch(t, actions)
    if t >= 1400:
        for e in run.state.applied:
            a = e.get('action')
            pl = e.get('payload') or {}
            if a == 'JOIN_COOP':
                res = str(e.get('result'))
                if res in ('None', 'OK'):
                    joins[pl.get('coop_id', '?')] += 1
                else:
                    join_fail[f"{pl.get('coop_id','?')}:{res}"] += 1
            elif a == 'LEAVE_COOP':
                res = str(e.get('result'))
                if res in ('None', 'OK'):
                    leaves[pl.get('coop_id', '?')] += 1
                else:
                    leave_fail[f"{pl.get('coop_id','?')}:{res}"] += 1
        if t % 100 == 0:
            s = run.state
            memb_hist[t] = {cid: len(c.get('members') or []) for cid, c in s.coops.items()
                            if cid in ('bakers', 'city_bakers', 'millers', 'farmers', 'miners', 'power_plant', 'livestock_co')}
    run.state.applied.clear(); run.batches.clear(); run._last_events = []
print('JOIN outcomes t1400+:', dict(joins))
print('JOIN failures:', dict(join_fail))
print('LEAVE outcomes:', dict(leaves))
print('LEAVE failures:', dict(leave_fail))
print('membership history:')
for t, m in memb_hist.items():
    print(f'  t{t}: {m}')
