import random, sys
sys.path.insert(0, "src"); sys.path.insert(0, "dashboard")
from server import Run

seed = int(sys.argv[1]) if len(sys.argv) > 1 else 42
run = Run(seed=seed)
ESSENTIALS = {"bread", "water", "electricity", "meals"}
# track per-good unmet max over time (prune events like the gate)
from collections import defaultdict
per_good_peak = defaultdict(int)
first_bad, last_bad = {}, {}
for t in range(2, 2001):
    actions = []
    for name, meta in sorted(run.bots.items()):
        rng = random.Random(f"{seed}:{t}:{name}")
        actions.extend(meta["fn"](name, run.state, run.state.active_ruleset_params(), t, rng))
    run._apply_batch(t, actions)
    if t >= 1500 and t % 10 == 0:
        for cit, d in run.state.unmet_needs.items():
            for g, streak in d.items():
                if streak > per_good_peak[g]:
                    per_good_peak[g] = streak
                    first_bad[g] = t
    run.state.applied.clear()
    run.batches.clear()
    run._last_events = []
    _recs = run.ledger.records
    if len(_recs) > 4000:
        del _recs[: len(_recs) - 1000]
for g, v in sorted(per_good_peak.items(), key=lambda kv: -kv[1]):
    tag = "ESSENTIAL" if g in ESSENTIALS else "breadth"
    if v >= (1 if g in ESSENTIALS else 30):
        print(f"{g}: peak_streak={v} ({tag}) at ~t{first_bad.get(g)}")
