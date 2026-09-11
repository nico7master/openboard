#!/usr/bin/env python
"""cProfile the exact bench workload (drive 13..13+N) regions OFF vs ON.

Usage (via memrun): profile_regions.py off|on [nticks]
"""
import cProfile
import io
import pstats
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'dashboard'))

from server import Run  # noqa: E402
from stage6_scale_gate import drive, scale_world, trim_retention  # noqa: E402

ON = len(sys.argv) > 1 and sys.argv[1] == 'on'
NTICKS = int(sys.argv[2]) if len(sys.argv) > 2 else 5


class VRun(Run):
    def _params(self):
        p = super()._params()
        if ON:
            p['regional_markets'] = {'enabled': True, 'regions': 10}
        return p


run = VRun(seed=42)
pop = scale_world(run, 966)
drive(run, 42, 3, 12)  # settle (untimed, unprofiled)
trim_retention(run)

prof = cProfile.Profile()
prof.enable()
drive(run, 42, 13, 13 + NTICKS)
prof.disable()

for sort in ('tottime', 'cumulative'):
    s = io.StringIO()
    pstats.Stats(prof, stream=s).sort_stats('tottime' if sort=='totime' else sort).print_stats(22)
    lines = s.getvalue().splitlines()
    print(f"=== PROFILE regions={'ON' if ON else 'OFF'} nticks={NTICKS} pop={pop} sort={sort} ===", flush=True)
    print('\n'.join(lines[4:40]), flush=True)
