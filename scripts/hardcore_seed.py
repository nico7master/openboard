import random, sys
sys.path.insert(0, 'src'); sys.path.insert(0, 'dashboard')
from server import Run

seed = int(sys.argv[1])
run = Run(seed=seed)
for t in range(2, 2001):
    actions = []
    for name, meta in sorted(run.bots.items()):
        rng = random.Random(f"{seed}:{t}:{name}")
        actions.extend(meta["fn"](name, run.state, run.state.active_ruleset_params(), t, rng))
    if t % 200 == 0:
        import resource
        print(f't={t} rss_mb={resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024}', flush=True)
    run._apply_batch(t, actions)
    run._record_timeline()
    # Memory hygiene: the gate only reads final unmet streaks, but Run
    # accumulates every applied event + tx batch (~3.8k events/tick),
    # which OOM-kills the 10 GB cgroup well before tick 2000
    # (observed: seed RSS 8.2 GB). Prune what the gate never reads.
    run.state.applied.clear()
    run.batches.clear()
    run._last_events = []
s = run.state
ESSENTIALS = {"bread", "water", "electricity", "meals"}
worst_ess, worst_breadth = 0, 0
for t in range(1500, 2001):
    if t % 10: continue
    per_good = {}
    for cit, d in s.unmet_needs.items():
        for g in d:
            per_good[g] = max(per_good.get(g, 0), d[g])
    ess = [v for g, v in per_good.items() if g in ESSENTIALS]
    worst_ess = max(worst_ess, max(ess, default=0))
    brd = [v for g, v in per_good.items() if g not in ESSENTIALS]
    worst_breadth = max(worst_breadth, max(brd, default=0))
print(f"seed {seed}: worst_essential={worst_ess} worst_breadth={worst_breadth} (bound 30)")
print(f"seed {seed}: {'PASS' if worst_ess == 0 and worst_breadth <= 30 else 'FAIL'}")
