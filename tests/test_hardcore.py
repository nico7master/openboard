"""Hard Core A4: 2,000-tick long-run survival gate.

The 500-tick circular-flow gate could not see the t~800 freeze (capital
depletion -> utility cascade). This gate runs 3 seeds x 2,000 ticks and
requires the economy to stay alive the whole way.
"""
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "dashboard"))

from server import Run  # noqa: E402
from openboard.metrics import gini  # noqa: E402


class TestLongRunSurvival:
    """2026-09-02: each seed now runs in its OWN subprocess (scripts/
    hardcore_seed.py) — accumulating 3 seeds of state in one process hit
    the container's 10 GB cgroup limit and was OOM-killed repeatedly
    (oom_kill 19 in memory.events). Same assertions, one process per
    seed, memory freed between runs."""

    def test_long_run_survival_gate(self):
        import subprocess
        root = Path(__file__).resolve().parents[1]
        for seed in (42, 7, 123):
            r = subprocess.run(
                ["/opt/venv/bin/python", str(root / "scripts" / "hardcore_seed.py"), str(seed)],
                capture_output=True, text=True, timeout=3_600,
            )
            out = r.stdout.strip().splitlines()
            verdict = [ln for ln in out if "PASS" in ln or "FAIL" in ln]
            assert r.returncode == 0 and verdict and "PASS" in verdict[-1], (
                f"seed {seed}: gate subprocess failed\n" + "\n".join(out[-8:]) + r.stderr[-800:]
            )
