#!/usr/bin/env python
"""P2 re-run under the current engine (RC1 week-3 science, 2026-09-20).

Runs the ORIGINAL p2_probe arms against today's engine (kcal basket,
rescaled recipes, machine wear, scarcity-pricing default, audit-gap
defaults) so the 2026-09-12 verdicts are re-verified, not assumed.

Writes to sweeps/p2_rerun/ — the historical sweeps/p2/ stays untouched.
One combo per process, resumable, ALWAYS via scripts/memrun.sh.

Usage: p2_rerun.py ARM SEED TICKS
"""
import json
import sys
from pathlib import Path

ROOT = Path("/a0/usr/projects/openboard-economy")
sys.path.insert(0, str(ROOT / "scripts"))

import p2_probe  # noqa: E402

# redirect BEFORE any run() call — the resumable check must never see the
# historical 2026-09-12 files
p2_probe.OUT_DIR = ROOT / "sweeps" / "p2_rerun"
p2_probe.OUT_DIR.mkdir(parents=True, exist_ok=True)


if __name__ == "__main__":
    arm, seed, ticks = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
    doc = p2_probe.run(arm, seed, ticks)
    out_file = p2_probe.OUT_DIR / f"{arm}_s{seed}.json"
    print(json.dumps({"arm": arm, "seed": seed, "file": str(out_file),
                      "exists": out_file.exists()}))
