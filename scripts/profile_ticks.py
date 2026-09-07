#!/usr/bin/env python
"""WP4.2 profiler: where do the milliseconds of a tick go?

Runs N ticks of the baseline world under cProfile and prints the top
functions by own-time (tottime) and cumulative time (cumtime).
Doctrine (stage6 WP1): optimize ONLY what this proves hot, and every
optimization must keep byte-identical replay.

Usage: python scripts/profile_ticks.py [ticks] [seed] [top_n]
"""
import cProfile
import io
import pstats
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "dashboard"))

from server import Run  # noqa: E402

TICKS = int(sys.argv[1]) if len(sys.argv) > 1 else 20
SEED = int(sys.argv[2]) if len(sys.argv) > 2 else 42
TOP = int(sys.argv[3]) if len(sys.argv) > 3 else 15


def build_actions(run, t):
    actions = []
    params = run.state.active_ruleset_params()  # hoisted: measure hoisted cost
    for name, meta in sorted(run.bots.items()):
        rng = random.Random(f"{SEED}:{t}:{name}")
        actions.extend(meta["fn"](name, run.state, params, t, rng))
    return actions


def main():
    run = Run(seed=SEED)
    # warmup 2 ticks so genesis setup isn't in the profile
    for t in range(2, 4):
        actions = build_actions(run, t)
        run._apply_batch(t, actions)
        run.state.applied.clear()
        run.batches.clear()

    prof = cProfile.Profile()
    prof.enable()
    for t in range(4, 4 + TICKS):
        actions = build_actions(run, t)
        run._apply_batch(t, actions)
        run.state.applied.clear()
        run.batches.clear()
        recs = run.ledger.records
        if len(recs) > 4000:
            del recs[: len(recs) - 1000]
    prof.disable()

    s = io.StringIO()
    ps = pstats.Stats(prof, stream=s)
    ps.strip_dirs().sort_stats("tottime").print_stats(TOP)
    ps.strip_dirs().sort_stats("cumtime").print_stats(TOP)
    out = s.getvalue()
    # keep it readable: only the tables
    for line in out.splitlines():
        print(line)


if __name__ == "__main__":
    main()
