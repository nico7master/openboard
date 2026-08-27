"""Stage 5 - Demographics unit tests (spec section 2).

Births every birth_interval_ticks (minted stake, invariant-exact),
childhood (no WORK, scaled consumption), maturation event, and
replay-safety when the ruleset lacks the demographics config.
"""
import random
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "dashboard"))

from openboard.demographics import (  # noqa: E402
    child_need_pct,
    demographics_phase,
    is_child,
)
from openboard.engine import apply_tick  # noqa: E402
from openboard.ledger import Ledger, Transaction  # noqa: E402
from openboard.state import genesis_state  # noqa: E402


DEMOGRAPHICS_CFG = {
    "enabled": True,
    "birth_interval_ticks": 400,
    "adulthood_ticks": 600,
    "child_need_pct": 50,
}


def _params(**over) -> dict:
    cfg = dict(DEMOGRAPHICS_CFG)
    cfg.update(over)
    return {"demographics": cfg}


def _money_total(state) -> int:
    treasuries = sum(c.get("treasury", 0) for c in state.coops.values())
    return (
        sum(state.balances.values())
        + state.surplus_pool
        + state.capital_fund
        + treasuries
    )


def _enable(state, **over) -> dict:
    """Write the demographics config into the live ruleset params so
    apply_tick picks it up (mirrors test_stage5_shocks' _world)."""
    cfg = dict(DEMOGRAPHICS_CFG)
    cfg.update(over)
    state.rulesets[-1]["params"]["demographics"] = cfg
    return cfg


def test_off_config_inert() -> None:
    """Without demographics params the phase is inert (replay-safe)."""
    s = genesis_state({"alice": 500, "bob": 500}, ruleset_params={})
    before = dict(s.balances)
    events = demographics_phase(s, 400, {})
    assert events == []
    assert s.balances == before
    assert "gen2_1" not in s.balances


def test_birth_mints_stake_invariant_exact() -> None:
    """A birth mints the standard stake; the money invariant stays exact."""
    s = genesis_state({"alice": 500, "bob": 500}, ruleset_params={})
    params = _params()
    base = _money_total(s) - s.money_minted  # base = 2 * 500

    events = demographics_phase(s, 400, params)
    assert len(events) == 1
    ev = events[0]
    assert ev["action"] == "CITIZEN_BORN"
    assert ev["citizen"] == "gen2_1"
    assert ev["stake"] == 500

    # minting is booked in money_minted, balance received the stake
    assert s.balances["gen2_1"] == 500
    assert s.money_minted == 500
    assert _money_total(s) == base + s.money_minted - s.money_retired


def test_births_are_periodic_and_ids_ordered() -> None:
    """Births fire every birth_interval_ticks with deterministic ids."""
    s = genesis_state({"alice": 500}, ruleset_params={})
    params = _params(birth_interval_ticks=10)
    born = []
    for t in range(1, 31):
        born.extend(e["citizen"] for e in demographics_phase(s, t, params) if e["action"] == "CITIZEN_BORN")
    assert born == ["gen2_1", "gen2_2", "gen2_3"]


def test_childhood_duration_and_adult_event() -> None:
    """A newborn is a child until adulthood_ticks; CITIZEN_ADULT fires once."""
    s = genesis_state({"alice": 500}, ruleset_params={})
    _enable(s, birth_interval_ticks=10, adulthood_ticks=20)
    params = s.active_ruleset_params()
    adult_events = []
    for t in range(1, 40):
        evs = demographics_phase(s, t, params)
        adult_events.extend(e["citizen"] for e in evs if e["action"] == "CITIZEN_ADULT")
        # born t10 at age 0; child while age <= adulthood (20): t10..t29;
        # crossing tick t30 (age 21) emits CITIZEN_ADULT
        if "gen2_1" in s.balances and t <= 29:
            assert is_child(s, "gen2_1", params), f"t{t}: must be a child (age {s.citizens_meta['gen2_1']['age']})"
        if "gen2_1" in s.balances and t >= 31:
            assert not is_child(s, "gen2_1", params), f"t{t}: should be adult (age {s.citizens_meta['gen2_1']['age']})"
    assert adult_events == ["gen2_1"]  # exactly once


def test_genesis_adults_never_emit_adult_event() -> None:
    """Existing-world citizens are marked adult silently (no event storm)."""
    s = genesis_state({"alice": 500, "bob": 500}, ruleset_params={})
    _enable(s, adulthood_ticks=10)
    params = s.active_ruleset_params()
    events = []
    for t in range(1, 15):
        events.extend(demographics_phase(s, t, params))
    assert not any(
        e.get("action") == "CITIZEN_ADULT" and e.get("citizen") in ("alice", "bob")
        for e in events
    )


def test_child_cannot_work() -> None:
    """WORK by a child is rejected (dignity floor: no child labor)."""
    from openboard.ledger import Ledger, Transaction

    s = genesis_state({"alice": 500}, ruleset_params={})
    _enable(s, birth_interval_ticks=1, adulthood_ticks=100)
    apply_tick(s, Ledger(), [], current_tick=1)  # birth tick -> gen2_1
    # age the child a few ticks (still a child)
    for t in range(2, 6):
        apply_tick(s, Ledger(), [], current_tick=t)

    apply_tick(s, Ledger(), [Transaction(
        tick=s.tick + 1,
        sender="alice",
        action="FOUND_COOP",
        payload={"coop_id": "dig", "name": "dig", "members": ["alice", "gen2_1"]},
        ruleset_version=s.ruleset_version,
    )], current_tick=s.tick + 1)
    tx = Transaction(
        tick=s.tick + 1,
        sender="gen2_1",
        action="WORK",
        payload={"coop_id": "dig", "hours": 8},
        ruleset_version=s.ruleset_version,
    )
    ledger = Ledger()
    apply_tick(s, ledger, [tx], current_tick=s.tick + 1)
    work_results = [
        r for r in ledger.records
        if getattr(r, "accepted", True) is False
    ]
    assert work_results, "child WORK must be rejected"
    # and the balance must be unchanged (no wage minted)
    assert s.balances["gen2_1"] == 500


def test_child_consumption_scaled() -> None:
    """Children consume child_need_pct of each quota (integer, min 1)."""
    s = genesis_state({"alice": 500}, ruleset_params={})
    _enable(s, birth_interval_ticks=10, adulthood_ticks=100)
    s.rulesets[-1]["params"]["needs"] = {"bread": 2}  # explicit quota
    apply_tick(s, Ledger(), [], current_tick=10)  # birth
    assert "gen2_1" in s.balances
    s.citizen_inventory["gen2_1"]["bread"] = 10
    s.citizen_inventory["alice"]["bread"] = 10
    quota = s.active_ruleset_params()["needs"]["bread"]
    before_child = s.citizen_inventory["gen2_1"]["bread"]
    before_adult = s.citizen_inventory["alice"]["bread"]
    apply_tick(s, Ledger(), [], current_tick=11)
    used_child = before_child - s.citizen_inventory["gen2_1"].get("bread", 0)
    used_adult = before_adult - s.citizen_inventory["alice"].get("bread", 0)
    assert used_adult == quota
    assert used_child == max(1, (quota * 50) // 100), (
        f"child used {used_child}, expected scaled {max(1, (quota * 50) // 100)}"
    )


def test_death_respects_children_too() -> None:
    """Shock death accounting treats children identically (spec section 1)."""
    from openboard.shocks import _kill_citizen

    s = genesis_state({"alice": 500}, ruleset_params={})
    _enable(s, birth_interval_ticks=10, adulthood_ticks=100)
    apply_tick(s, Ledger(), [], current_tick=10)  # gen2_1 born
    pool_before = s.surplus_pool
    bal_before = s.balances["gen2_1"]
    _kill_citizen(s, 11, "gen2_1")
    assert "gen2_1" not in s.balances
    assert s.surplus_pool == pool_before + bal_before


def _found_coop(state, coop_id: str, members: list[str]) -> None:
    """Found a minimal coop via the engine (deterministic)."""
    apply_tick(
        state,
        Ledger(),
        [Transaction(
            tick=state.tick + 1,
            sender=members[0],
            action="FOUND_COOP",
            payload={"coop_id": coop_id, "name": coop_id, "members": members},
            ruleset_version=state.ruleset_version,
        )],
    )
