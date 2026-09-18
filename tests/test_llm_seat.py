"""LLM seat (P0) offline tests — no network, no live model.

The fake client answers from the digest deterministically, so the whole
record→replay cycle is testable offline. Real Mercury sessions run manually.
"""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from openboard.breaksystem import attack_score, round_verdict  # noqa: E402
from openboard.llm_seat import (  # noqa: E402
    SEAT_ACTIONS,
    SeatSession,
    attacker_digest,
    parse_decision,
    seat_transactions,
)

_spec = importlib.util.spec_from_file_location(
    "dashboard_server_llmseat", ROOT / "dashboard" / "server.py"
)
server = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(server)


def _fake_reply(actions):
    return json.dumps({"reasoning": "test", "actions": actions})


def test_seat_actions_are_engine_supported():
    from openboard.engine import SUPPORTED_ACTIONS

    assert SEAT_ACTIONS <= SUPPORTED_ACTIONS


def test_digest_from_live_governance_world():
    game = server.Run(seed=99, governance=True)
    s = game.state
    who = sorted(s.balances.keys())[0]
    d = attacker_digest(s, who, attack_score(s))
    assert who in d
    assert "WALLET" in d and "GOAL" in d
    assert isinstance(d, str) and 100 < len(d) < 4000


def test_parse_decision_tolerates_fences_and_prose():
    raw = "Sure!\n```json\n" + _fake_reply(
        [{"action": "BUY_ESSENTIAL", "good": "bread", "qty": 2}]
    ) + "\n```"
    d = parse_decision(raw)
    assert d["actions"][0]["good"] == "bread"


def test_parse_decision_rejects_garbage():
    with pytest.raises(Exception):
        parse_decision("no json here at all")


def test_seat_transactions_schema_conformance():
    d = parse_decision(_fake_reply([
        {"action": "BID", "good": "bread", "qty": 3, "max_price": 50},
        {"action": "BUY_ESSENTIAL", "good": "water", "qty": 2},
        {"action": "BUY_LAND", "pid": "P1"},
        {"action": "SELL_LAND", "pid": "P9"},
        {"action": "PROPOSE", "issue": "self_reward"},   # out of contract -> dropped
        {"action": "BID", "good": "oops"},              # malformed -> dropped
    ]))
    txs = seat_transactions(d, tick=7, attacker="c0", version=1)
    actions = [t.action for t in txs]
    assert actions == ["BID", "BUY_ESSENTIAL", "BUY_LAND", "SELL_LAND"]
    assert txs[0].payload == {"good": "bread", "qty": 3, "max_price": 50}
    assert txs[2].payload == {"pid": "P1"}


def test_session_record_replay_roundtrip(tmp_path):
    s = SeatSession()
    d = parse_decision(
        _fake_reply([{"action": "BUY_ESSENTIAL", "good": "bread", "qty": 1}])
    )
    s.record(3, "digest-text", d, 1)
    p = tmp_path / "session.json"
    p.write_text(s.to_json())
    s2 = SeatSession.replay(str(p))
    assert s2.turns == s.turns


def test_full_session_smoke_with_fake_client():
    """Full loop with a greedy fake client: decisions map to transactions, the
    engine accepts/rejects them publicly, the invariant stays intact."""
    game = server.Run(seed=99, governance=True)
    attacker = sorted(game.state.balances.keys())[0]
    version = game.state.ruleset_version

    def fake_client(_digest):
        return _fake_reply([
            {"action": "BUY_ESSENTIAL", "good": "bread", "qty": 5},
            {"action": "BUY_ESSENTIAL", "good": "water", "qty": 5},
        ])

    for _ in range(5):
        s = game.state
        tick = s.tick + 1
        d = parse_decision(fake_client(attacker_digest(s, attacker, attack_score(s))))
        txs = seat_transactions(d, tick, attacker, version)
        for tx in txs:
            game.queue_action(tx.sender, tx.action, tx.payload)
        game.tick()
        assert attack_score(game.state)["invariant_ok"] is True

    verdict = round_verdict(game.state, "llm_adversary", 1)
    assert "outcome" in verdict and "damage" in verdict


def test_quiet_play_does_not_stop_round_early():
    game = server.Run(seed=99, governance=True)
    for _ in range(3):
        game.tick()
    verdict = round_verdict(game.state, "llm_adversary", 1)
    assert verdict["outcome"] == "round_in_progress"
