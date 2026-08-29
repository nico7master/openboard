"""B2: Break the System — playbooks map to proven attack archetypes;
the score exposes flags/Gini/damage; the invariant holds under every
playbook (the system's defense is the opponent)."""
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "dashboard"))

from openboard.breaksystem import PLAYBOOKS, attack_score, attack_tick, invariants_ok
from openboard.engine import apply_tick
from openboard.ledger import Ledger


def _gov_run():
    from server import Run
    return Run(seed=99, governance=True)


def test_playbooks_registered():
    assert set(PLAYBOOKS) == {"hoarder", "wash_trade", "faction", "wage_mint"}


def test_unknown_playbook_is_noop():
    r = _gov_run()
    txs = attack_tick(r.state, "worker_a", 2, "nonexistent", random.Random(1))
    assert txs == []


def _gov_run():
    from server import Run
    return Run(seed=99, governance=True)


def test_hoarder_run_generates_and_scores():
    r = _gov_run()
    s, led = r.state, r.ledger
    for t in range(2, 12):
        txs = attack_tick(s, "worker_a", t, "hoarder", random.Random(t))
        apply_tick(s, led, txs, current_tick=t)
    score = attack_score(s)
    assert score["invariant_ok"] is True
    assert score["tick"] == 11
    assert isinstance(score["gini_bp"], int)


def test_wage_mint_cannot_break_invariant():
    r = _gov_run()
    s, led = r.state, r.ledger
    for t in range(2, 12):
        txs = attack_tick(s, "worker_a", t, "wage_mint", random.Random(t))
        apply_tick(s, led, txs, current_tick=t)
    score = attack_score(s)
    assert score["invariant_ok"] is True


def test_faction_run_live_democracy():
    r = _gov_run()
    s, led = r.state, r.ledger
    for t in range(2, 8):
        txs = attack_tick(s, "worker_a", t, "faction", random.Random(t))
        apply_tick(s, led, txs, current_tick=t)
    assert invariants_ok(s) is None
    assert attack_score(s)["tick"] == 7
