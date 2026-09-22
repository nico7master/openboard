"""Post-RC1 pacing tune (founder-approved 2026-09-22): momentum coalescing.

Probe evidence (sweeps/post_rc1/): 0 of 840 proposals passed in 3x2000-tick
soak seeds. Not quorum (ballots reached 29) — diluted weight: A8's even split
spread each politician's token across ~21 open proposals, so ordinary
proposals never gathered a strict majority of cast weight.

Tune: a politician commits the FULL remaining token to the single
stance-positive proposal with the most for-weight so far (deterministic
lowest-pid tiebreak). Contracts kept: decoys with zero traction get nothing
(A8), determinism (pure function of public state), A2/constitutional tiers
untouched (bot confetti must never flip a constitution).
"""
import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "dashboard_server_mom", Path(__file__).resolve().parents[1] / "dashboard" / "server.py"
)
server = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(server)

from openboard.politics import _momentum_leader  # noqa: E402


def _fresh(seed=42):
    server.RUN = server.Run(seed=seed, governance=True)
    return server.RUN


def _ordinary_fixture(run, pid, ballots):
    """An open proposal carrying the world's OWN active params — genuinely
    ordinary business (structural/constitutional fields untouched)."""
    return (pid, {"params": dict(run.state.active_ruleset_params()),
                  "ballots": ballots})


def test_momentum_leader_prefers_traction_then_pid():
    run = _fresh(seed=5)
    props = [
        _ordinary_fixture(run, "p2", {"x": {"choice": "for", "bp": 5_000}}),
        _ordinary_fixture(run, "p1", {"x": {"choice": "for", "bp": 5_000}}),
        _ordinary_fixture(run, "p3", {"y": {"choice": "against", "bp": 9_000}}),
    ]
    leader = _momentum_leader(props, run.state)
    assert leader == ("p1", 5_000)  # tie on weight -> lowest pid wins


def test_momentum_leader_ignores_zero_traction():
    run = _fresh(seed=5)
    props = [_ordinary_fixture(run, "p1", {"x": {"choice": "against", "bp": 9_000}})]
    assert _momentum_leader(props, run.state) is None


def test_structural_business_never_gets_bot_momentum():
    """The A2 contract inside the tune: a wealth-tax (structural) proposal
    with big traction is NOT a momentum leader — bot weight must never
    coalesce onto tier-gated business."""
    run = _fresh(seed=5)
    params = dict(run.state.active_ruleset_params())
    params["wealth_tax"] = {"threshold": 100, "rate_bp": 2_000}  # structural
    props = [("p9", {"params": params,
                     "ballots": {"x": {"choice": "for", "bp": 30_000}}})]
    assert _momentum_leader(props, run.state) is None


def test_ordinary_proposal_can_pass_in_bot_republic():
    """The exact probe failure, inverted: with coalescing, some ordinary
    proposal gathers a strict majority of cast weight and PASSES."""
    run = _fresh(seed=42)
    passed = failed = 0
    for _ in range(700):
        run.tick()
    for p in run.state.proposals.values():
        if p["status"] == "passed":
            passed += 1
        elif p["status"] in ("failed", "rejected"):
            failed += 1
    assert passed > 0, (passed, failed)  # the republic can legislate again


def test_no_bot_structural_flip():
    """A2 hardening intact: no governance/constitutional change may pass by
    bot votes alone in the tuned republic either."""
    run = _fresh(seed=42)
    for _ in range(700):
        run.tick()
    genesis_gov = run.state.rulesets[0]["params"].get("governance")
    gov_changed = any(
        rs.get("params", {}).get("governance") != genesis_gov
        for rs in run.state.rulesets
    )
    assert not gov_changed
