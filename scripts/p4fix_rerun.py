#!/usr/bin/env python3
"""Verification harness for spec 2026-09-13 (research-funding-fix).

Re-runs the P4 all_on arm with research reserve_floor = 1B units so the
stock-proportional tap can never drain the Society Pool's dividend
reserve. Everything else is byte-identical to the P4 probe: same trader
book, same shock streams, same 650 ticks / 1000 citizens / seeds.

Output: sweeps/p4fix/all_on_floor1B_s{seed}.json (resumable).
ALWAYS launch via scripts/memrun.sh — one seed per process, sequential.

Usage: p4fix_rerun.py SEED
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import p4_probe  # noqa: E402

OUT_DIR = ROOT / "sweeps" / "p4fix"
RESERVE_FLOOR = 1_000_000_000  # units (10M cr) protected dividend reserve


class P4FixRun(p4_probe.P4Run):
    """all_on with a protected research reserve floor (spec Option A)."""

    def _params(self):
        p = super()._params()
        if "research" in p:
            p["research"]["reserve_floor"] = RESERVE_FLOOR
        return p


def main() -> None:
    seed = int(sys.argv[1])
    ticks = 12 if __import__("os").environ.get("SMOKE") == "1" else 650
    res = p4_probe.run(
        "all_on", seed, ticks,
        run_cls=P4FixRun, out_dir=OUT_DIR,
        name=f"all_on_floor1B_s{seed}.json",
    )
    print(json.dumps(res, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
