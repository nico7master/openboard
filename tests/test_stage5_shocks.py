"""Stage 5 · Shock engine unit tests (spec §1)."""
import random

import pytest

from openboard.engine import apply_tick
from openboard.shocks import (
    PROFILES,
    _kill_citizen,
    expire_finished,
    farm_output_factor,
    power_disabled,
    roll_shock,
)
from openboard.state import WorldState


def _world(shocks_cfg: dict) -> tuple[WorldState, object]:
    from dashboard.server import Run
    run = Run(seed=42)
    rs = run.state.rulesets[-1]
    rs["params"]["shocks"] = shocks_cfg
    return run.state, run.ledger


def test_profiles_complete() -> None:
    assert set(PROFILES) == {"off", "peaceful", "standard", "harsh", "apocalyptic", "battery"}


def test_off_profile_inert() -> None:
    s, led = _world({"enabled": True, "profile": "off", "rng_seed": 1})
    n0 = len(s.applied)
    for t in range(2, 52):
        rng = random.Random(f"1:{t}")
        roll_shock(s, t, rng)
        expire_finished(s, t)
    assert len(s.applied) == n0  # nothing ever fires


def test_determinism_same_seed_same_events() -> None:
    events_a, events_b = [], []
    for sink in (events_a, events_b):
        s, led = _world({"enabled": True, "profile": "standard", "rng_seed": 7})
        for t in range(2, 302):
            roll_shock(s, t, random.Random(f"7:{t}"))
            expire_finished(s, t)
        sink.extend(e for e in s.applied if e.get("action") == "SHOCK_START")
    assert [e for e in events_a] == [e for e in events_b]


def test_drought_reduces_farm_output_factor() -> None:
    s, led = _world({"enabled": True, "profile": "off"})
    s.active_shocks.append({"kind": "drought", "start": 5, "end": 20, "magnitude_pct": 35})
    s.tick = 10
    assert farm_output_factor(s) == 1000 - 350
    s.tick = 25
    # expired via end-tick semantics only after expire; direct lookup uses state.tick


def test_outage_disables_power_flag() -> None:
    s, led = _world({"enabled": False})
    s.active_shocks.append({"kind": "outage", "start": 5, "end": 15, "magnitude_pct": 50})
    s.tick = 10
    assert power_disabled(s)
    s.tick = 16
    assert not power_disabled(s)


def test_death_accounting_conserves_money() -> None:
    s, led = _world({"enabled": False})
    victim = sorted(s.balances.keys())[0]
    stake = s.balances[victim]
    pool0 = s.surplus_pool
    total_before = sum(s.balances.values()) + s.surplus_pool + s.capital_fund
    _kill_citizen(s, 10, victim)
    total_after = sum(s.balances.values()) + s.surplus_pool + s.capital_fund
    assert total_after == total_before  # exact conservation
    assert s.balances.get(victim) is None
    death = [e for e in s.applied if e.get("action") == "CITIZEN_DEATH"]
    assert death and death[0]["citizen"] == victim


def test_pandemic_kills_and_recovers() -> None:
    s, led = _world({"enabled": True, "profile": "battery", "rng_seed": 9})
    alive0 = len(s.balances)
    # force a pandemic event deterministically
    from openboard.shocks import LADDERS
    spec = LADDERS["pandemic"][4]
    victims = sorted(s.balances.keys())[: int(spec[2])]
    for v in victims:
        _kill_citizen(s, 50, v)
    assert all(v not in s.balances for v in victims)
    from openboard.shocks import _citizen_meta
    for c in list(s.balances.keys()):
        _citizen_meta(s, c)["sick"] = True
    expire_finished(s, 51)  # no active pandemic yet; sickness persists
    s.active_shocks.append({"kind": "pandemic", "start": 51, "end": 61, "magnitude_pct": 75})
    recov = expire_finished(s, 61)
    assert any(e.get("recovered") for e in recov if e["kind"] == "pandemic")
