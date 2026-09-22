"""Audit 2026-09-20 P-GOV regression tests (A1-A5, A8, A9, E1).

Capture fixes: minority capture via abstention (A2), delegation mirroring
+ last-second sweeps (A3), trust entrenchment + farming (A4), structural
whitelist gaps (A5), decoy token drain (A8), cheap structural rollback
(A9), and stage-5 ruleset validation (E1)."""
import copy
import random
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from openboard import crisis as C
from openboard.engine import (
    _is_structural,
    apply_tick,
    expand_weighted_ballots,
)
from openboard.ledger import Ledger, Transaction
from openboard.rules import (
    DEFAULT_RULESET_PARAMS,
    OPTIONAL_PARAMS,
    REQUIRED_PARAMS,
)
from openboard.state import genesis_state


class _Runner:
    """Monotonic tick driver (apply_tick ADVANCES state.tick)."""

    def __init__(self, s, led):
        self.s, self.led = s, led
        self.now = s.tick

    def run(self, txs):
        self.now += 1
        apply_tick(self.s, self.led, txs, current_tick=self.now)

    def tx(self, sender, action, payload):
        return Transaction(tick=self.now + 1, sender=sender, action=action,
                           payload=payload, ruleset_version=self.s.ruleset_version)

    def propose(self, sender, params=None):
        base = copy.deepcopy(self.s.active_ruleset_params())
        if params is not None:
            base = params
        else:
            base["transfer_limit"] = (base.get("transfer_limit") or 0) + 1
        self.run([self.tx(sender, "PROPOSE",
                          {"params": base, "activation_tick": self.now + 10})])
        return sorted(self.s.proposals.keys())[-1]

    def vote(self, sender, pid, choice, bp=None):
        payload = {"proposal_id": pid, "choice": choice}
        if bp is not None:
            payload["bp"] = bp
        self.run([self.tx(sender, "VOTE", payload)])

    def close(self, n=4):
        for _ in range(n):
            self.run([])


def _params(**gov_over):
    p = copy.deepcopy(DEFAULT_RULESET_PARAMS)
    p["triage_overrides"] = {}
    gov = {
        "enabled": True,
        "vote_window_ticks": 3,
        "quorum_bp": 1_000,  # founder default: reachable 10%
        "trial_period_ticks": 10,
        "vote_token_bp": 10_000,
        "vote_cycle_ticks": 30,
        "persuasion": True,
    }
    gov.update(gov_over)
    p["governance"] = gov
    return p


def _world(params, n=5):
    return genesis_state({f"c{i}": 10_000 for i in range(n)},
                         ruleset_params=params)


# ---------------------------------------------------------------- E1

def test_e1_param_whitelist_parity_guard():
    """Every top-level params key the engine reads must be votable —
    otherwise PROPOSE of the complete active ruleset (the politician
    seat's standard move) dies INVALID_RULESET in stage-5 worlds."""
    root = Path(__file__).resolve().parents[1] / "src" / "openboard"
    known = set(REQUIRED_PARAMS) | set(OPTIONAL_PARAMS)
    missing = set()
    for f in root.glob("*.py"):
        t = f.read_text()
        missing |= set(re.findall(r'params\.get\("([a-z_]+)"', t))
        missing |= set(re.findall(r'params\["([a-z_]+)"\]', t))
    assert missing <= known, (
        f"engine reads params absent from every whitelist: {sorted(missing - known)}")


def test_e1_stage5_keys_votable():
    for key in ("research", "shocks", "demographics", "wage_debt_repay",
                "birth_stake_from_pool", "wage_mint_mode"):
        assert key in OPTIONAL_PARAMS


# ---------------------------------------------------------------- A1

def test_a1_crisis_vote_one_per_citizen():
    r = _Runner(_world(_params()), Ledger())
    C.declare_crisis(r.s, r.now, "famine", "vote")
    assert r.s.crisis["active"]
    r.run([r.tx("c0", "CRISIS_VOTE", {"in_favor": True})])
    assert r.s.crisis["votes_for"] == 1
    # repeat vote: rejected, not counted (was: unlimited repeat votes)
    r.run([r.tx("c0", "CRISIS_VOTE", {"in_favor": True})])
    assert r.s.crisis["votes_for"] == 1
    r.run([r.tx("c1", "CRISIS_VOTE", {"in_favor": False})])
    assert r.s.crisis["votes_against"] == 1
    assert r.s.crisis["voters"] == {"c0": True, "c1": False}
    recs = [x for x in r.led.records
            if x.tx.get("sender") == "c0"
            and x.tx.get("action") == "CRISIS_VOTE" and not x.accepted]
    assert recs and recs[-1].reason == "CRISIS_VOTED"


# ---------------------------------------------------------------- A2

def test_a2_structural_needs_all_citizen_weight():
    """2 of 5 citizens vote for a structural change = 100% of cast weight
    but 40% of the electorate. Cast-weight math passed this; the
    all-citizen denominator must reject it."""
    r = _Runner(_world(_params()), Ledger())
    newp = copy.deepcopy(r.s.active_ruleset_params())
    newp["wealth_tax"] = {"threshold": 1_000_000, "rate_bp": 500}
    pid = r.propose("c0", params=newp)
    r.vote("c0", pid, "for", 10_000)
    r.vote("c1", pid, "for", 10_000)
    r.close()
    assert r.s.proposals[pid]["status"] == "failed"


def test_a2_structural_passes_with_real_majority():
    """Control: 3 of 5 citizens (60% of ALL weight) still passes."""
    r = _Runner(_world(_params()), Ledger())
    newp = copy.deepcopy(r.s.active_ruleset_params())
    newp["wealth_tax"] = {"threshold": 1_000_000, "rate_bp": 500}
    pid = r.propose("c0", params=newp)
    for who in ("c0", "c1", "c2"):
        r.vote(who, pid, "for", 10_000)
    r.close()
    assert r.s.proposals[pid]["status"] == "passed"


# ---------------------------------------------------------------- A3

def test_a3_delegation_snapshot_freezes_mirror_weight():
    """A delegation made AFTER a proposal opened must not mirror into it
    (last-second sweep attack). Direct unit check + settle integration."""
    r = _Runner(_world(_params(), n=3), Ledger())
    ballots = {"c0": {"choice": "for", "bp": 10_000}}
    r.s.delegations["c1"] = "c0"  # live graph has the follower
    live = expand_weighted_ballots(r.s, ballots, 10_000)
    assert live["c1"]["choice"] == "for"  # mirrors live
    frozen = expand_weighted_ballots(r.s, ballots, 10_000, delegations={})
    assert "c1" not in frozen  # open-time snapshot: follower abstains

    # integration: post-open delegation must not flip the outcome
    r2 = _Runner(_world(_params(), n=3), Ledger())
    pid = r2.propose("c2")  # non-structural; snapshot taken (no delegations)
    r2.s.delegations["c1"] = "c0"  # delegate AFTER open
    r2.vote("c0", pid, "for", 10_000)
    r2.vote("c2", pid, "against", 10_000)
    r2.close()
    # snapshot: 10,000 for vs 10,000 against -> tie fails (live mirror
    # would have passed 20,000 vs 10,000)
    assert r2.s.proposals[pid]["status"] == "failed"


# ---------------------------------------------------------------- A4

def test_a4_rate_limit_one_open_proposal():
    r = _Runner(_world(_params()), Ledger())
    base = r.s.active_ruleset_params()
    p1 = copy.deepcopy(base)
    p1["transfer_limit"] = (base.get("transfer_limit") or 0) + 1
    p2 = copy.deepcopy(base)
    p2["transfer_limit"] = (base.get("transfer_limit") or 0) + 2
    r.run([r.tx("c0", "PROPOSE", {"params": p1, "activation_tick": r.now + 10})])
    r.run([r.tx("c0", "PROPOSE", {"params": p2, "activation_tick": r.now + 10})])
    recs = [x for x in r.led.records
            if x.tx.get("action") == "PROPOSE" and not x.accepted]
    assert recs and recs[-1].reason == "PROPOSAL_LIMIT"


def test_a4_unknown_politician_starts_at_50():
    """Failed proposal drops a fresh author to 40 (50 default), not 90."""
    r = _Runner(_world(_params()), Ledger())
    newp = copy.deepcopy(r.s.active_ruleset_params())
    newp["wealth_tax"] = {"threshold": 1_000_000, "rate_bp": 500}
    pid = r.propose("c3", params=newp)
    r.vote("c0", pid, "against", 10_000)
    r.vote("c1", pid, "against", 10_000)
    r.close()
    assert r.s.proposals[pid]["status"] == "failed"
    assert r.s.politician_trust["c3"] == 40


# ---------------------------------------------------------------- A5

def test_a5_structural_whitelist_expanded():
    for key in ("surplus_spending", "credit", "scarcity_pricing"):
        assert _is_structural({key: {"enabled": True}}, {})
    assert not _is_structural({"transfer_limit": 5}, {})


# ---------------------------------------------------------------- A8

def test_a8_momentum_commits_full_token_to_one_proposal():
    """A8 evolved (founder-approved momentum tune, 2026-09-22): the bot no
    longer SPLITS its token evenly across open proposals — even slices
    could not out-weigh strict-majority abstainers (0 of 840 proposals
    passed in the RC1 soak probes). The FULL remaining token goes to the
    single stance-positive ORDINARY proposal with the most for-weight so
    far; with zero traction, the lowest-pid ordinary proposal the voter
    supports gets the cold-start seed. Decoys with zero traction still
    receive nothing, and only ordinary business is reachable."""
    from openboard.politics import make_politician
    from openboard.engine import _is_structural, _is_constitutional
    r = _Runner(_world(_params(persuasion=False)), Ledger())
    base = r.s.active_ruleset_params()
    for d, sender in ((1, "c1"), (2, "c2")):
        np_ = copy.deepcopy(base)
        np_["transfer_limit"] = (base.get("transfer_limit") or 0) + d
        r.run([r.tx(sender, "PROPOSE",
                    {"params": np_, "activation_tick": r.now + 10})])
    bot = make_politician(lambda *a, **k: [], "pragmatist")

    # Cold start (no traction anywhere): the lowest-pid supported ordinary
    # proposal (p1) receives the FULL token — never an even slice.
    txs = bot("c0", r.s, r.s.active_ruleset_params(), r.now, random.Random(0))
    votes = [t for t in txs if t.action == "VOTE"]
    assert len(votes) == 1
    assert votes[0].payload["proposal_id"] == "p1"
    assert votes[0].payload["bp"] == 10_000
    assert not _is_structural(r.s.proposals["p1"]["params"], base)
    assert not _is_constitutional(r.s.proposals["p1"]["params"], base)

    # Traction beats pid order: a for-weight on the HIGHER pid (p2) makes
    # IT the momentum leader — the full token follows the traction.
    r.s.proposals["p2"]["ballots"]["c9"] = {"choice": "for", "bp": 3_000}
    txs = bot("c0", r.s, r.s.active_ruleset_params(), r.now, random.Random(0))
    votes = [t for t in txs if t.action == "VOTE"]
    assert len(votes) == 1
    assert votes[0].payload["proposal_id"] == "p2"
    assert votes[0].payload["bp"] == 10_000


# ---------------------------------------------------------------- A9

def test_a9_structural_rollback_keeps_supermajority():
    """During v2's trial window, reverting a STRUCTURAL v2 change needs the
    structural tier — a bare majority must not cheaply unwind big rules."""
    r = _Runner(_world(_params()), Ledger())
    v1 = copy.deepcopy(r.s.active_ruleset_params())
    v2 = copy.deepcopy(v1)
    v2["wealth_tax"] = {"threshold": 1_000_000, "rate_bp": 500}  # structural
    opened = r.now
    r.s.rulesets.append({"version": 2, "params": v2,
                         "activated_at": opened, "change_tx_hash": "x"})
    r.s.ruleset_version = 2
    # rollback proposal back to v1, inside the trial window
    r.s.proposals["pR"] = {
        "proposal_id": "pR", "proposer": "c0", "params": v1,
        "activation_tick": opened + 10, "opened_tick": opened,
        "closes_tick": opened + 3, "ballots": {}, "status": "open",
        "is_rollback": True, "target_version": 2, "change_tx_hash": "x",
        "delegations_snapshot": {},
    }
    r.vote("c0", "pR", "for", 10_000)   # 2 of 5: simple majority of cast
    r.vote("c1", "pR", "for", 10_000)
    r.close()
    assert r.s.proposals["pR"]["status"] == "failed"
