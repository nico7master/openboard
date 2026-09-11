#!/usr/bin/env python
"""Avg ledger records/tick at 966 citizens, regions OFF vs ON (PIP fixed).

Settles whether the ON slowdown is economic volume (pip fix lets chains
run -> more trades -> more records -> more hashing; expected & correct)
or wrapper pathology (needs code surgery).

Usage (via memrun): vol_probe.py off|on
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'dashboard'))

from server import Run  # noqa: E402
from stage6_scale_gate import drive, scale_world, trim_retention  # noqa: E402

ON = len(sys.argv) > 1 and sys.argv[1] == 'on'


class VRun(Run):
    def _params(self):
        p = super()._params()
        if ON:
            p['regional_markets'] = {'enabled': True, 'regions': 10}
        return p


run = VRun(seed=42)
pop = scale_world(run, 966)
drive(run, 42, 3, 12)
trim_retention(run)
run.state.applied.clear()
run.batches.clear()
run._last_events = []
run.ledger.records.clear()

counts = []
import random
for t in range(13, 18):
    actions = []
    for name, meta in sorted(run.bots.items()):
        rng = random.Random(f"42:{t}:{name}")
        actions.extend(meta['fn'](name, run.state, run.state.active_ruleset_params(), t, rng))
    n0 = len(run.ledger.records)
    run._apply_batch(t, actions)
    run._record_timeline()
    counts.append(len(run.ledger.records) - n0)
    run.state.applied.clear()
    run.batches.clear()
    run._last_events = []
    if len(run.ledger.records) > 6000:
        del run.ledger.records[:3000]

print(f"RESULT regions={'ON' if ON else 'OFF'} pop={pop} avg_recs_per_tick={sum(counts)/len(counts):.0f} ticks={counts}", flush=True)
