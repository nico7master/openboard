"""D15: fixed money supply — 21,000,000 credits, divisible to 0.01.
Core promise: sum(balances) + surplus_pool == cap FOREVER. No minting,
ever. Wage shortfalls become coop debt repaid from sales; birth stakes
are society's transfer."""
import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from openboard.demographics import demographics_phase
from openboard.engine import _apply_work, _wage_debt_repay_phase, apply_tick
from openboard.ledger import Ledger, Transaction
from openboard.rules import DEFAULT_RULESET_PARAMS, validate_params
from openboard.state import genesis_state

CAP = {"enabled": True, "total": 2_100_000_000, "units_per_credit": 100}


def _params(**over):
    p = copy.deepcopy(DEFAULT_RULESET_PARAMS)
    p["money_cap"] = dict(CAP)
    p["demographics"] = {"enabled": True, "birth_interval_ticks": 2,
                         "adulthood_ticks": 600}
    p.update(over)
    return p


def _world(p, n=3):
    return genesis_state({f"c{i}": 500 for i in range(n)}, ruleset_params=p)


def _supply(s):
    # The TRUE conservation law: citizen balances + the society pool +
    # every coop treasury. Coop treasuries hold real money (from sales)
    # and must count, or transfers in/out of them look like mint/burn.
    return (sum(s.balances.values()) + int(s.surplus_pool)
            + sum(int(c.get("treasury", 0)) for c in s.coops.values()))


def test_cap_validation_accepts_and_rejects():
    p = copy.deepcopy(DEFAULT_RULESET_PARAMS)
    p["money_cap"] = {"enabled": True}
    assert validate_params(p) is None
    p["money_cap"] = {"enabled": "yes"}
    assert validate_params(p) is not None
    p["money_cap"] = {"enabled": True, "total": -5}
    assert validate_params(p) is not None


def test_genesis_places_full_cap():
    s = _world(_params())
    assert _supply(s) == 2_100_000_000
    # citizens hold 500 credits x 100 units each
    assert s.balances["c0"] == 50_000
    # the rest is the Society Pool
    assert s.surplus_pool == 2_100_000_000 - 3 * 50_000
    # divisibility: baselines are in units now (x100)
    assert all(isinstance(v, int) for v in s.good_cost_baseline.values())


def test_wages_never_mint_in_fixed_mode():
    s = _world(_params())
    led = Ledger()
    apply_tick(s, led, [Transaction(tick=1, sender="c0", action="FOUND_COOP",
        payload={"coop_id": "bakery", "name": "bakery", "members": ["c0", "c1"]},
        ruleset_version=1)], current_tick=1)
    supply_before = _supply(s)
    minted_before = s.money_minted
    coop = s.coops["bakery"]
    coop["treasury"] = 0  # can't pay
    tx = Transaction(tick=2, sender="c0", action="WORK",
                     payload={"coop_id": "bakery", "hours": 8}, ruleset_version=1)
    ev = _apply_work(s, tx, s.active_ruleset_params())
    assert _supply(s) == supply_before          # supply unchanged
    assert s.money_minted == minted_before      # NOTHING minted, ever
    # shortfall is visible debt (wage = 8h x 10_000bp = 8 credits = 800 units)
    assert coop["wage_debt"]["c0"] == 800 - coop.get("treasury", 0)


def test_wage_debt_repaid_from_sales():
    s = _world(_params())
    led = Ledger()
    apply_tick(s, led, [Transaction(tick=1, sender="c0", action="FOUND_COOP",
        payload={"coop_id": "bakery", "name": "bakery", "members": ["c0", "c1"]},
        ruleset_version=1)], current_tick=1)
    coop = s.coops["bakery"]
    coop["wage_debt"] = {"c0": 400}
    # a real day's sales: buyers' credits move INTO the coop treasury
    # (transfer from the society pool, as the input-advance would)
    state_pool_before = s.surplus_pool
    coop["treasury"] = 250
    s.surplus_pool = state_pool_before - 250
    supply_before = _supply(s)
    ev = _wage_debt_repay_phase(s, 5, s.active_ruleset_params())
    assert ev and ev[0]["paid"] == 250
    assert coop["wage_debt"]["c0"] == 150
    assert s.balances["c0"] == 50_000 + 250
    assert _supply(s) == supply_before  # pure transfer


def test_birth_stake_pool_only_never_mints():
    p = _params(demographics={"enabled": True, "birth_interval_ticks": 2,
                              "adulthood_ticks": 600})
    s = _world(p)
    s.surplus_pool = 1_000  # enough for a 50_000-unit stake? No — pool-only
    supply_before = _supply(s)
    minted_before = s.money_minted
    ev = demographics_phase(s, 2, p)
    born = [e for e in ev if e.get("action") == "CITIZEN_BORN"]
    assert born
    assert s.money_minted == minted_before   # NEVER mints in fixed mode
    assert _supply(s) == supply_before       # invariant holds


def test_pool_funds_whole_stake_when_rich():
    p = _params(demographics={"enabled": True, "birth_interval_ticks": 2,
                              "adulthood_ticks": 600})
    s = _world(p)
    s.surplus_pool = 100_000
    ev = demographics_phase(s, 2, p)
    born = [e for e in ev if e.get("action") == "CITIZEN_BORN"][0]
    assert s.balances[born["citizen"]] == 50_000  # full 500cr stake
    assert s.money_minted == 0
