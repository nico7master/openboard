"""Post-RC1 franchise pin (2026-09-22/23): scale_world extends the political
franchise to cloned citizens.

Before the fix, clones were registered as raw economic bots — at 975
citizens only the 29 base seats could vote against a quorum of 98: the
republic was mathematically dead at scale (0 of 840 proposals passed in
the post-tune soak, seeds 42/7/123) while working at dashboard scale
(29 voters >= quorum 18). The fix round-robins the dashboard's archetype
pattern across clones. These pins assert the contract that matters:
quorum stays REACHABLE at scale, the franchise is governance-gated, and
scaling is deterministic."""
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "dashboard"))

_spec = importlib.util.spec_from_file_location(
    "dashboard_server_fr", ROOT / "dashboard" / "server.py"
)
server = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(server)

from stage6_scale_gate import scale_world  # noqa: E402


def _politician_count(run):
    return sum(
        1 for b in run.bots.values()
        if getattr(b["fn"], "__qualname__", "").startswith("make_politician")
    )


def _quorum_needed(run):
    """Mirror of the engine's ceil-div quorum (engine.py:3493)."""
    gov = run.state.active_ruleset_params()["governance"]
    citizens = len(run.state.balances)
    return -(-citizens * gov.get("quorum_bp", 5_000) // 10_000)


def test_franchise_reaches_quorum_at_scale():
    """The exact soak failure, inverted: after scaling, the electorate must
    be at least as large as the quorum bar — the republic must be able to
    legislate at city scale."""
    run = server.Run(seed=42, governance=True)
    pop = scale_world(run, 500)
    pol = _politician_count(run)
    qn = _quorum_needed(run)
    # Scaling is CHUNK-APPROXIMATE (clone coops cap at 12 members), so the
    # achieved population lands near the target, not exactly on it (the
    # RC1 soak docstring says the same: target 1000 -> pop 975).
    assert 480 <= pop <= 510
    assert pol >= qn, f"republic quorum-walled: {pol} voters < quorum {qn}"


def test_franchise_is_governance_gated():
    """No governance, no political brains — clones stay raw economic bots
    (the gate script's legacy behavior must remain available)."""
    run = server.Run(seed=42, governance=False)
    scale_world(run, 500)
    assert _politician_count(run) == 0


def test_franchise_deterministic():
    """Same seed -> same electorate (the gate's determinism contract)."""
    counts = []
    for _ in range(2):
        run = server.Run(seed=7, governance=True)
        scale_world(run, 400)
        counts.append(_politician_count(run))
    assert counts[0] == counts[1]