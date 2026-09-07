#!/usr/bin/env python
"""WP4.2 at-scale profiler: where does a tick go at ~1,000 citizens?

Reuses the gate's own world builder + driver so the numbers describe the
real WP4.2 workload, then profiles a short run under cProfile.

Usage: python scripts/profile_scale.py [target_pop] [ticks] [seed]
"""
import cProfile
import io
import pstats
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "dashboard"))

import time

from server import Run  # noqa: E402
from stage6_scale_gate import drive, scale_world, trim_retention  # noqa: E402

TARGET = int(sys.argv[1]) if len(sys.argv) > 1 else 1000
TICKS = int(sys.argv[2]) if len(sys.argv) > 2 else 6
SEED = int(sys.argv[3]) if len(sys.argv) > 3 else 42


def main():
    run = Run(seed=SEED)
    pop = scale_world(run, TARGET)
    print(f"scaled pop={pop}; settling 10 ticks (post-founding)...", flush=True)
    drive(run, SEED, 3, 12)  # settle past the founding batch
    trim_retention(run)

    t0 = time.perf_counter()
    prof = cProfile.Profile()
    prof.enable()
    drive(run, SEED, 13, 12 + TICKS)
    prof.disable()
    wall = time.perf_counter() - t0
    print(f"profiled {TICKS} ticks at pop={len(run.bots)}: "
          f"{wall:.2f}s -> {TICKS / wall:.2f} ticks/s", flush=True)

    s = io.StringIO()
    ps = pstats.Stats(prof, stream=s)
    ps.strip_dirs().sort_stats("cumtime").print_stats(18)
    for line in s.getvalue().splitlines():
        print(line)


if __name__ == "__main__":
    main()
