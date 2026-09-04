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
    # D18 spiral fix: debt service is capped at repay_bp (default 50%) of
    # the treasury so the coop keeps operating capital — full-treasury
    # seizure made indebted coops unable to ever bid for inputs again.
    assert ev and ev[0]["paid"] == 125
    assert coop["wage_debt"]["c0"] == 400 - 125
    assert coop["treasury"] == 125  # working capital retained
    assert s.balances["c0"] == 50_000 + 125
    assert _supply(s) == supply_before  # pure transfer


def test_wage_debt_repay_leaves_working_capital():
    """Debt service must never consume the whole treasury: an indebted
    coop must retain capital to buy inputs, or it can never earn its way
    out (the observed miners spiral: treasury 0, 2.3M units owed)."""
    s = _world(_params())
    led = Ledger()
    apply_tick(s, led, [Transaction(tick=1, sender="c0", action="FOUND_COOP",
        payload={"coop_id": "bakery", "name": "bakery", "members": ["c0", "c1"]},
        ruleset_version=1)], current_tick=1)
    coop = s.coops["bakery"]
    coop["wage_debt"] = {"c0": 1_000_000}
    coop["treasury"] = 10_000
    ev = _wage_debt_repay_phase(s, 5, s.active_ruleset_params())
    assert coop["treasury"] == 5_000  # 50% retained for inputs/capital
    assert ev[0]["paid"] == 5_000


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


# ---- D16: real-world unequal start (top 1% own 50%)

def _isc_params(**over):
    p = _params(**over)
    p['inequality_seed'] = {'enabled': True, 'top_pct_bp': 100, 'top_share_bp': 5_000}
    return p


def test_inequality_seed_top1_own_half():
    s = _world(_isc_params(), n=100)
    sorted_bals = sorted(s.balances.values(), reverse=True)
    top1 = sorted_bals[:1]  # 1% of 100 citizens = 1 citizen
    rest = sorted_bals[1:]
    assert sum(top1) == 2_100_000_000 * 5_000 // 10_000  # exactly half
    assert all(b == sum(top1) for b in top1)
    assert all(0 < b < sum(top1) for b in rest)
    assert s.surplus_pool == 0  # society starts publicly poor


def test_inequality_seed_supply_conserved():
    s = _world(_isc_params(), n=100)
    total = (sum(s.balances.values()) + int(s.surplus_pool)
             + sum(int(c.get('treasury', 0)) for c in s.coops.values()))
    # exact cap minus rounding dust (< n units)
    assert 2_100_000_000 - 100 <= total <= 2_100_000_000


def test_inequality_seed_default_off():
    s = _world(_params(), n=5)  # no inequality_seed
    bals = set(s.balances.values())
    assert bals == {50_000}  # everyone equal, as D15
