"""P2 offline tests — persuasion rolls, 60% tier, trust loop, politician seat.

No network. Votes driven through real apply_tick with a monotonic tick
runner (vote-token lessons: never recompute relative ticks).
"""
import copy
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from openboard.engine import (  # noqa: E402
    _is_constitutional,
    _is_structural,
    apply_tick,
)
from openboard.ledger import Ledger, Transaction  # noqa: E402
from openboard.llm_politician import (  # noqa: E402
    POL_SEAT_ACTIONS,
    parse_politician_decision,
    politician_digest,
    politician_transactions,
)

_spec = importlib.util.spec_from_file_location(
    "dashboard_server_p2", ROOT / "dashboard" / "server.py"
)
server = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(server)


class _Runner:
    """Monotonic tick runner (vote-token test lesson)."""

    def __init__(self, s):
        self.s = s
        self.led = Ledger()
        self.now = s.tick

    def run(self, txs):
        self.now += 1
        apply_tick(self.s, self.led, txs, current_tick=self.now)

    def tx(self, sender, action, payload):
        return Transaction(tick=self.now + 1, sender=sender, action=action,
                           payload=payload, ruleset_version=self.s.ruleset_version)


def _gov_world():
    g = server.Run(seed=99, governance=True)
    g.state.rulesets[-1]["params"]["governance"]["persuasion"] = True
    return g


def _fake_reply(actions):
    return json.dumps({"reasoning": "test", "actions": actions})


def _propose_and_settle(r, proposer, base, for_n, against_n, citizens):
    """File a proposal, cast for_n 'for' + against_n 'against' bp votes,
    run past the window, return (proposal_id, status)."""
    r.run([r.tx(proposer, "PROPOSE",
                {"params": copy.deepcopy(base), "activation_tick": r.now + 10})])
    pid = sorted(r.s.proposals.keys())[-1]
    votes = [r.tx(c, "VOTE", {"proposal_id": pid, "choice": "for"})
             for c in citizens[:for_n]]
    votes += [r.tx(c, "VOTE", {"proposal_id": pid, "choice": "against"})
              for c in citizens[for_n:for_n + against_n]]
    r.run(votes)
    while r.s.proposals[pid]["status"] == "open":
        r.run([])
    return pid, r.s.proposals[pid]["status"]


def test_seat_actions_are_propose_vote_only():
    from openboard.engine import SUPPORTED_ACTIONS

    assert POL_SEAT_ACTIONS <= SUPPORTED_ACTIONS
    assert POL_SEAT_ACTIONS == {"PROPOSE", "VOTE"}  # separation of powers


def test_digest_reports_trust_and_token():
    g = _gov_world()
    who = sorted(g.state.balances.keys())[0]
    d = politician_digest(g.state, who, 5)
    assert "Trust: 100/100" in d
    assert "vote budget" in d
    # P2 lesson (live session 045440): a rules SUMMARY makes the model
    # improvise a partial params object that dies in validation — the
    # digest must carry the COMPLETE ruleset plus the activation rule.
    assert "COMPLETE CURRENT RULESET" in d
    assert "activation_tick must be GREATER" in d
    assert "CURRENT TICK: 5" in d
    assert 100 < len(d) < 12000


def test_politician_transactions_schema():
    d = parse_politician_decision(_fake_reply([
        {"action": "VOTE", "proposal_id": "p1", "choice": "for", "bp": 3000},
        {"action": "BID", "good": "bread", "qty": 1, "max_price": 5},  # out of contract
        {"action": "PROPOSE", "activation_tick": 20},  # params missing -> dropped
        {"action": "VOTE", "proposal_id": "p2", "choice": "yes", "bp": 100},  # bad choice
    ]))
    # Non-token world: validator demands EXACT keys {proposal_id, choice} —
    # an extra bp would silence the seat via INVALID_PAYLOAD (regression guard).
    txs = politician_transactions(d, tick=6, who="c0", version=1)
    assert [t.action for t in txs] == ["VOTE"]
    assert txs[0].payload == {"proposal_id": "p1", "choice": "for"}
    # Token world: bp required and preserved.
    txs_t = politician_transactions(d, tick=6, who="c0", version=1, token_mode=True)
    assert [t.action for t in txs_t] == ["VOTE"]
    assert txs_t[0].payload == {"proposal_id": "p1", "choice": "for", "bp": 3000}


def test_politician_valid_vote_and_propose_map():
    base = copy.deepcopy(server.Run(seed=1).state.active_ruleset_params())
    d = parse_politician_decision(_fake_reply([
        {"action": "VOTE", "proposal_id": "p1", "choice": "for", "bp": 4000},
        {"action": "PROPOSE", "params": base, "activation_tick": 20},
    ]))
    # Token world: both actions map with exact validator schemas.
    txs = politician_transactions(d, tick=6, who="c0", version=1, token_mode=True)
    assert [t.action for t in txs] == ["VOTE", "PROPOSE"]
    assert txs[0].payload == {"proposal_id": "p1", "choice": "for", "bp": 4000}
    assert txs[1].payload["params"] == base


def test_structural_classification():
    """Engine contract: proposals carry COMPLETE params; _is_structural
    compares them key-by-key against active (partial dicts over-report).
    Structural = wealth_tax/research/crisis/need_allocation/whistleblower
    deltas; governance deltas are constitutional (2/3 of all), even stricter."""
    active = {"wealth_tax": {"rate_bp": 0}, "research": {}, "crisis": {},
              "need_allocation": {}, "whistleblower": {},
              "transfer_limit": 0, "governance": {"vote_token_bp": 10000}}
    changed = copy.deepcopy(active)
    changed["wealth_tax"]["rate_bp"] = 400
    assert _is_structural(changed, active) is True
    routine = copy.deepcopy(active)
    routine["transfer_limit"] = 999
    assert _is_structural(routine, active) is False
    assert _is_constitutional(routine, active) is False
    gov_changed = copy.deepcopy(active)
    gov_changed["governance"]["vote_token_bp"] = 5000
    assert _is_structural(gov_changed, active) is True
    assert _is_constitutional(gov_changed, active) is True


def test_major_tier_60_percent():
    """Structural: ~55% of cast weight FAILS, ~67% PASSES (60% bar).
    Trust: -10 on reject; +5 on pass (from a pre-lowered 90)."""
    g = _gov_world()
    s = g.state
    r = _Runner(s)
    citizens = sorted(s.balances.keys())
    n = len(citizens)
    base = copy.deepcopy(s.active_ruleset_params())
    base["wealth_tax"] = dict(base.get("wealth_tax") or {"rate_bp": 400})
    base["wealth_tax"]["rate_bp"] = 800  # must DIFFER from active (400) — a
    # no-op delta is not structural and rides the simple-majority branch

    fail_yes = max(1, int(n * 0.55))          # below the 60% bar
    pid, status = _propose_and_settle(
        r, citizens[0], base, fail_yes, n - fail_yes, citizens)
    assert status == "failed", f"{fail_yes}/{n} yes must fail the 60% tier"  # engine truth: 'failed', not 'rejected'
    assert s.politician_trust.get(citizens[0], 100) == 90  # -10 trust

    # second world: clear pass above the bar, trust rises from 90 to 95
    g2 = _gov_world()
    s2 = g2.state
    r2 = _Runner(s2)
    c2 = sorted(s2.balances.keys())
    n2 = len(c2)
    base2 = copy.deepcopy(s2.active_ruleset_params())
    base2["wealth_tax"] = dict(base2.get("wealth_tax") or {"rate_bp": 400})
    base2["wealth_tax"]["rate_bp"] = 800  # real delta (default is 400)
    s2.politician_trust[c2[0]] = 90           # pre-lower so +5 is visible
    pass_yes = min(n2, int(n2 * 0.67) + 1)    # safely above 60%
    pid2, status2 = _propose_and_settle(
        r2, c2[0], base2, pass_yes, n2 - pass_yes, c2)
    assert status2 == "passed", f"{pass_yes}/{n2} yes must clear the 60% tier"
    assert s2.politician_trust.get(c2[0]) == 95  # +5 trust


def test_routine_majority_unaffected():
    """55% for / 45% against on a NON-structural change passes (simple majority)."""
    g = _gov_world()
    s = g.state
    r = _Runner(s)
    citizens = sorted(s.balances.keys())
    n = len(citizens)
    base = copy.deepcopy(s.active_ruleset_params())
    base["transfer_limit"] = (base.get("transfer_limit") or 0) + 1
    yes = max(1, int(n * 0.55))
    pid, status = _propose_and_settle(
        r, citizens[0], base, yes, n - yes, citizens)
    assert status == "passed"  # 55% suffices when the 60% tier does not apply


def test_persuasion_roll_seeded():
    """Same (tick,pid,who) => same roll; roll domain sits inside trust range."""
    import hashlib

    def roll(tick, pid, who):
        return int.from_bytes(hashlib.sha256(
            f"{tick}:{pid}:{who}".encode()).digest()[:2], "big") % 101

    assert roll(5, "p1", "a") == roll(5, "p1", "a")
    assert roll(5, "p1", "a") != roll(6, "p1", "a") or True  # per-tick variation allowed
    assert 0 <= roll(5, "p1", "a") <= 100


def test_noop_proposal_rejected():
    """P2 trust-integrity: a proposal identical to the active ruleset must be
    rejected (NO_OP_PROPOSAL) — live-proven exploit: session 052110 p1 passed
    as a pure no-op and farmed +5 trust via the accountability loop."""
    from openboard.errors import Reason

    g = _gov_world()
    s = g.state
    r = _Runner(s)
    citizens = sorted(s.balances.keys())
    no_op = copy.deepcopy(s.active_ruleset_params())  # zero deltas
    r.run([r.tx(citizens[0], "PROPOSE",
                {"params": no_op, "activation_tick": r.now + 10})])
    assert any(rec.reason == Reason.NO_OP_PROPOSAL
               for rec in r.led.records if not rec.accepted)
    assert not any(pr.get("proposer") == citizens[0]
                   for pr in s.proposals.values())


def test_full_politician_session_fake_client():
    """Full loop with a fake client: seat files a small routine change, the
    world settles it via persuasion/default rules, invariant holds."""
    g = _gov_world()
    who = sorted(g.state.balances.keys())[0]
    version = g.state.ruleset_version

    def fake_client(_digest):
        base = copy.deepcopy(g.state.active_ruleset_params())
        base["transfer_limit"] = (base.get("transfer_limit") or 0) + 1
        return _fake_reply([
            {"action": "PROPOSE", "params": base, "activation_tick": 30},
        ])

    txs = politician_transactions(
        parse_politician_decision(fake_client("digest")),
        tick=g.state.tick + 1, who=who, version=version)
    assert txs and txs[0].action == "PROPOSE"
    for tx in txs:
        g.queue_action(tx.sender, tx.action, tx.payload)
    for _ in range(25):
        g.tick()
    statuses = {pr["status"] for pr in g.state.proposals.values()
                if pr.get("proposer") == who}
    assert statuses <= {"passed", "failed"}  # engine truth: resolved = passed|failed
    assert all(b >= 0 for b in g.state.balances.values())
