import random, sys
sys.path.insert(0, 'src'); sys.path.insert(0, 'dashboard')
from server import Run
from collections import defaultdict

seed = 42
run = Run(seed=seed)
WATCH = ('electricity', 'coal', 'machines')
# late-window capture
W1, W2 = range(1770, 1801), range(1940, 2001)
prod = defaultdict(int); clear = defaultdict(int); bidfail = defaultdict(int)
coops = {}
for t in range(2, 2001):
    actions = []
    for name, meta in sorted(run.bots.items()):
        rng = random.Random(f"{seed}:{t}:{name}")
        actions.extend(meta['fn'](name, run.state, run.state.active_ruleset_params(), t, rng))
    run._apply_batch(t, actions)
    if t in W1 or t in W2:
        for e in run.state.applied:
            a = e.get('action')
            if a == 'PRODUCE':
                for g, q in (e.get('outputs') or {}).items():
                    if g in WATCH: prod[g] += q
                coops[e.get('coop_id')] = e.get('coop_id')
            elif a in ('MARKET_CLEAR_ESSENTIAL', 'MARKET_CLEAR'):
                g = e.get('good')
                if g in WATCH: clear[g] += e.get('qty', 0)
            elif a == 'BID' and e.get('result') not in (None, 'OK', 'CLEARED'):
                g = (e.get('payload') or {}).get('good')
                if g in WATCH: bidfail[g] += 1
        if t in (1790, 1800, 1990, 2000):
            s = run.state
            print(f'--- t{t} ---')
            for cid, c in sorted(s.coops.items()):
                inv = c.get('inventory') or {}
                if any(inv.get(g, 0) for g in WATCH) or cid in ('power_plant', 'machine_works', 'coal_mine'):
                    print(f'{cid}: members={len(c.get("members", []))} treasury={c.get("treasury", 0)} '
                          f'coal={inv.get("coal", 0)} elec={inv.get("electricity", 0)} machines={inv.get("machines", 0)} '
                          f'wear={ (s.capital_wear.get(cid) or {}).get("machines", 0) } '
                          f'last_prod={s.tick - c.get("last_produce_tick", 0) if c.get("last_produce_tick") else "-"} deps={c.get("wage_debt", 0)}')
            print('WATCH window totals: prod=%s clear=%s bidfail=%s' % (dict(prod), dict(clear), dict(bidfail)))
            prod.clear(); clear.clear(); bidfail.clear()
    run.state.applied.clear(); run.batches.clear(); run._last_events = []
