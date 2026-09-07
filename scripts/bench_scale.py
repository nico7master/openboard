#!/usr/bin/env python
"""Unprofiled wall-clock benchmark on the real WP4.2 workload.

No cProfile (its call overhead dominates hash/JSON code and hides real
wins). Measures ticks/s on the scaled world after a settle window.

Usage: python scripts/bench_scale.py [target_pop] [ticks] [seed]
"""
import gc
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "dashboard"))

from server import Run  # noqa: E402
from stage6_scale_gate import drive, scale_world, trim_retention  # noqa: E402

TARGET = int(sys.argv[1]) if len(sys.argv) > 1 else 1000
TICKS = int(sys.argv[2]) if len(sys.argv) > 2 else 10
SEED = int(sys.argv[3]) if len(sys.argv) > 3 else 42


def main():
    run = Run(seed=SEED)
    pop = scale_world(run, TARGET)
    drive(run, SEED, 3, 12)  # settle past founding
    trim_retention(run)
    gc.collect()

    t0 = time.perf_counter()
    drive(run, SEED, 13, 12 + TICKS)
    wall = time.perf_counter() - t0
    print(f"pop={len(run.bots)} ticks={TICKS} wall={wall:.2f}s "
          f"-> {TICKS / wall:.2f} ticks/s (unprofiled)")


if __name__ == "__main__":
    main()