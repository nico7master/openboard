import random, sys
sys.path.insert(0, 'src'); sys.path.insert(0, 'dashboard')
from server import Run

seed = int(sys.argv[1])
run = Run(seed=seed)
checkpoints = {2, 25, 50, 100, 200, 400, 800, 1200, 1600, 2000}
for t in range(2, 2001):
    actions = []
    for name, meta in sorted(run.bots.items()):
        rng = random.Random(f"{seed}:{t}:{name}")
        actions.extend(meta["fn"](name, run.state, run.state.active_ruleset_params(), t, rng))
    run._apply_batch(t, actions)
    run._record_timeline()
    run.state.applied.clear()
    run.batches.clear()
    run._last_events = []
    recs = run.ledger.records
    if len(recs) > 4000:
        del recs[: len(recs) - 1000]
    if t in checkpoints:
        s = run.state
        total = sum(sum((cd.get('wage_debt') or {}).values()) for cd in s.coops.values())
        debtors = sum(1 for cd in s.coops.values() if cd.get('wage_debt'))
        # essentials check to correlate debt with famine
        worst = 0
        for cit, d in s.unmet_needs.items():
            for g, v in d.items():
                worst = max(worst, v)
        print(f'seed {seed} t={t}: wage_debt_total={total:,.0f} debtors={debtors} worst_unmet_streak={worst}', flush=True)
print(f'seed {seed}: DONE', flush=True)
