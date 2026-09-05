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
    # D20 diagnosis: a pathological transaction payload explodes _sanitize
    # (MemoryError, zero cgroup OOM-kills => single huge allocation). Name
    # the offender before it kills the run.
    try:
        run._apply_batch(t, actions)
    except MemoryError:
        import sys as _sys
        biggest = sorted(actions, key=lambda a: len(repr(getattr(a, 'payload', {}))), reverse=True)[:3]
        for a in biggest:
            print(f'BIG tx: action={a.action!r} sender={a.sender!r} payload_len={len(repr(a.payload))}', flush=True)
            print(f'  head={repr(a.payload)[:2000]}', flush=True)
        _sys.stdout.flush()
        raise
    run._record_timeline()
    # Memory hygiene: the gate only reads final unmet streaks, but Run
    # accumulates every applied event + tx batch (~3.8k events/tick),
    # which OOM-kills the 10 GB cgroup well before tick 2000
    # (observed: seed RSS 8.2 GB). Prune what the gate never reads.
    run.state.applied.clear()
    run.batches.clear()
    run._last_events = []
    # D20: the LEDGER itself was never pruned — every record of all 2000
    # ticks stays resident (~2 MB/tick growth: 497 MB at t200 -> 3.87 GB
    # at t1800 -> MemoryError in _apply_batch serialization; the trap
    # proved payloads are tiny, so it is cumulative, not one big tx).
    # Harness-only: keep the last 1000 records for same-tick readers;
    # head_hash lives on the Ledger, chain integrity untouched. Engine
    # code is NOT changed by this.
    _recs = run.ledger.records
    if len(_recs) > 4000:
        del _recs[: len(_recs) - 1000]
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
