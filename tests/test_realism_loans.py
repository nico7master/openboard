"""Realism contract L1 (spec 2026-09-11 Part II, Lever 1): interest on loans.

Real-world effect under contract:
- DIRECTION: positive interest prices time; free credit permits debt levels
  that are unsustainable under any positive price of credit; crisis credit
  goes to 0% (solidarity lending, like real emergency facilities).
- MECHANISM: interest accrues on OUTSTANDING principal (declining balance,
  1 tick = 1 day), flows to the surplus pool (society earns the carry),
  stops at default (charge-off freeze).
- MAGNITUDE: rate_bp_annual is a rule param; realistic default 500bp/yr.
  Integer truncation: tiny principals x small rates floor to 0 credits,
  so tests use 36500bp (=365%/yr) where interest == principal*days//100.
- FLIP: loans originated while a crisis is ACTIVE carry rate 0, locked at
  origination (fixed-rate contract). Default freezes accrual at due_tick.

Backward contract: rate_bp_annual absent or 0 => the owed formula
degenerates to the pre-interest one; old worlds replay untouched.
"""
import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from openboard.crisis import declare_crisis  # noqa: E402
from openboard.engine import apply_tick, credit_phase, loan_owed  # noqa: E402
from openboard.ledger import Ledger, Transaction  # noqa: E402
from openboard.rules import DEFAULT_RULESET_PARAMS, RuleSetDoc  # noqa: E402
from openboard.state import genesis_state  # noqa: E402


def rate_params(rate_bp: int) -> dict:
    p = copy.deepcopy(DEFAULT_RULESET_PARAMS)
    p["triage_overrides"] = {}
    p["credit"] = {"enabled": True, "max_per_citizen": 1_000,
                   "term_ticks": 50, "fee_bp": 0, "rate_bp_annual": rate_bp}
    return p


def _world(params: dict, balances: dict):
    s = genesis_state(balances, ruleset_params=params)
    s.surplus_pool = 10_000
    return s, Ledger()


def _loan(sender, tick, amount, version):
    return Transaction(tick=tick, sender=sender, action="LOAN",
                       payload={"amount": amount}, ruleset_version=version)


def _repay(sender, tick, amount, version):
    return Transaction(tick=tick, sender=sender, action="REPAY",
                       payload={"amount": amount}, ruleset_version=version)


def test_loan_charges_interest_and_goes_to_pool():
    """L1 mechanism: owed grows with time on outstanding principal; every
    repaid credit returns to the pool (money conservation exact)."""
    s, led = _world(rate_params(36_500), {"c1": 100})
    apply_tick(s, led, [_loan("c1", 1, 300, s.ruleset_version)], current_tick=1)
    loan = s.loans["c1"]
    assert loan["rate_bp_annual"] == 36_500  # locked at origination
    assert loan_owed(loan, 1) == 300  # day 0: principal only
    assert loan_owed(loan, 11) == 330  # 10 days: +30 = 300*10//100
    # engine waterfall is principal-FIRST (fees/interest paid last)
    s.balances["c1"] += 500  # honest earnings arrive from elsewhere
    apply_tick(s, led, [_repay("c1", 11, 165, s.ruleset_version)], current_tick=11)
    assert s.loans["c1"]["repaid_principal"] == 165  # all of pay -> principal
    assert s.loans["c1"]["repaid_fees"] == 0
    assert loan_owed(s.loans["c1"], 21) == 162  # left 135 + interest 27 (1%/day)
    # conservation: pool issued 300; 165 returned; nothing minted. Total
    # stock = endowment 100 + pool 10,000 + the 500 wages injected above.
    assert sum(s.balances.values()) + s.surplus_pool == 100 + 10_000 + 500


def test_free_credit_permits_unsustainable_debt():
    """L1 direction: the SAME income stream and principal-only amortization
    that exactly clears a free-credit loan at term leaves an unpaid interest
    tail under priced credit -> default. Free credit hides carrying cost."""
    def run(rate_bp: int):
        s, led = _world(rate_params(rate_bp), {"c1": 100})
        apply_tick(s, led, [_loan("c1", 1, 300, s.ruleset_version)], current_tick=1)
        for t in range(6, 52, 5):  # pays 30/tick, earns 30/tick: both worlds
            s.balances["c1"] += 30  # wages
            if "c1" in s.loans:
                apply_tick(s, led, [_repay("c1", t, 30, s.ruleset_version)],
                           current_tick=t)
        credit_phase(s, 52, s.active_ruleset_params())  # term ends at 51
        return s

    free = run(0)
    priced = run(36_500)
    assert "c1" not in free.loans  # principal-only schedule clears at term
    # priced: t=51 owed was 45 (30 principal + 15 interest) but pay 30 ->
    # interest tail unpaid -> loan open past due -> default.
    assert priced.loans["c1"]["defaulted"] is True
    assert priced.loans["c1"]["repaid_principal"] == 300  # principal was paid


def test_crisis_zeroes_rates():
    """L1 flip: loans originated during an ACTIVE crisis carry 0% locked;
    after the crisis ends, new loans are priced again."""
    s, led = _world(rate_params(36_500), {"c1": 100, "c2": 100})
    declare_crisis(s, 1, "pandemic", "vote")
    apply_tick(s, led, [_loan("c1", 2, 300, s.ruleset_version)], current_tick=2)
    assert s.loans["c1"]["rate_bp_annual"] == 0
    assert loan_owed(s.loans["c1"], 40) == 300  # zero accrual in crisis
    s.crisis["active"] = False  # crisis ended (vote/expiry tested elsewhere)
    apply_tick(s, led, [_loan("c2", 41, 300, s.ruleset_version)], current_tick=41)
    assert s.loans["c2"]["rate_bp_annual"] == 36_500
    assert loan_owed(s.loans["c2"], 51) == 330


def test_defaulted_loan_stops_accruing():
    """L1 charge-off: accrual freezes at due_tick once defaulted."""
    s, led = _world(rate_params(36_500), {"c1": 100})
    apply_tick(s, led, [_loan("c1", 1, 300, s.ruleset_version)], current_tick=1)
    ev = credit_phase(s, 60, s.active_ruleset_params())  # term 50 -> default
    assert ev and s.loans["c1"]["defaulted"] is True
    owed_at_default = loan_owed(s.loans["c1"], 60)
    assert loan_owed(s.loans["c1"], 200) == owed_at_default  # frozen


def test_absent_rate_key_replays_old_formula():
    """Backward contract: old credit dicts (no rate_bp_annual) keep the exact
    pre-interest owed arithmetic — old worlds replay untouched."""
    p = copy.deepcopy(DEFAULT_RULESET_PARAMS)
    p["triage_overrides"] = {}
    p["credit"] = {"enabled": True, "max_per_citizen": 1_000,
                   "term_ticks": 50, "fee_bp": 500}
    s, led = _world(p, {"c1": 100})
    apply_tick(s, led, [_loan("c1", 1, 300, s.ruleset_version)], current_tick=1)
    assert s.loans["c1"].get("rate_bp_annual", 0) == 0
    assert loan_owed(s.loans["c1"], 40) == 315  # 300 + 5% flat fee only
