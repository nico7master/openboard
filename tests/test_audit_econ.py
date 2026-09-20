"""Audit 2026-09-20 P-ECON regression battery (B1/B2/B4/B6 + N1).

Every test pins a probe-confirmed defect and its fix:
- B1: a defaulted loan blocks new credit and PRESERVES the book row
  (the old overwrite destroyed both the pool and the audit trail).
- N1: credit_phase runs without demographics -> loans actually default.
- B2: durable-capital rent = live replacement amortized over durability
  (was: full replacement EVERY run -> x169 overcharge); non-durable
  worlds keep exact legacy rent (replay-safe).
- B4: capital_refresh prices from live good_cost_baseline (was: stale
  credit-era book values -> x7.4 fund drain).
- B6: the per-tick demand window ACCUMULATES across PIP + citizen passes
  (was: citizen pass overwrote the PIP volume producers plan on).
"""
import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from openboard.engine import apply_tick  # noqa: E402
from openboard.ledger import Ledger, Transaction  # noqa: E402
from openboard.rules import DEFAULT_RULESET_PARAMS  # noqa: E402
from openboard.state import genesis_state  # noqa: E402


class R:
    def __init__(self, params, endow=1_000_000, n=6):
        p = copy.deepcopy(DEFAULT_RULESET_PARAMS)
        p["triage_overrides"] = {}
        p.update(params)
        self.s = genesis_state({f"c{i}": endow for i in range(n)},
                               ruleset_params=p)
        self.led = Ledger()
        self.now = self.s.tick

    def tx(self, sender, action, payload):
        return Transaction(tick=self.now + 1, sender=sender, action=action,
                           payload=payload,
                           ruleset_version=self.s.ruleset_version)

    def run(self, txs=()):
        self.now += 1
        apply_tick(self.s, self.led, list(txs), current_tick=self.now)

    def rec(self):
        return self.led.records[-1] if self.led.records else None


def found(r, coop_id, members):
    r.run([r.tx(members[0], "FOUND_COOP",
                {"coop_id": coop_id, "name": coop_id, "members": members})])
    assert r.s.coops.get(coop_id), f"found rejected: {r.rec().reason}"
    return r.s.coops[coop_id]


# ------------------------------------------------------------------ B1+N1
def test_defaulted_loan_blocks_new_credit_and_keeps_trail():
    r = R({"credit": {"enabled": True, "max_per_citizen": 5_000,
                      "term_ticks": 5, "fee_bp": 0, "rate_bp_annual": 0}})
    r.s.surplus_pool = 50_000
    pool0 = r.s.surplus_pool
    r.run([r.tx("c0", "LOAN", {"amount": 5_000})])
    assert r.rec().accepted
    for _ in range(7):
        r.run([])
    defaults = [e for e in r.s.applied if e.get("action") == "LOAN_DEFAULT"]
    assert defaults, "loan must default (N1: without demographics too)"
    assert r.s.loans["c0"].get("defaulted") is True
    # the fix: re-borrow is REJECTED and the trail survives
    r.run([r.tx("c0", "LOAN", {"amount": 5_000})])
    assert not r.rec().accepted
    assert r.rec().reason == "LOAN_DEFAULTED"
    assert r.s.loans["c0"]["principal"] == 5_000  # row preserved
    # drain bounded to the single defaulted borrow
    assert pool0 - r.s.surplus_pool == 5_000


def test_good_citizen_can_still_borrow_after_someone_else_defaults():
    r = R({"credit": {"enabled": True, "max_per_citizen": 5_000,
                      "term_ticks": 5, "fee_bp": 0, "rate_bp_annual": 0}})
    r.s.surplus_pool = 50_000
    r.run([r.tx("c0", "LOAN", {"amount": 5_000})])
    for _ in range(7):
        r.run([])
    r.run([r.tx("c1", "LOAN", {"amount": 5_000})])
    assert r.rec().accepted, "unrelated citizen must not be blocked"


# ------------------------------------------------------------------ B2
def _rent_world():
    r = R({"extended_catalog": True,
           "durable_capital": {"enabled": True,
                               "goods": ["machines", "hand_tools"],
                               "durability": 20},
           "capital_rent": {"per_machine_used": 1_500,
                            "per_tool_used": 60}})
    found(r, "mine", ["c0", "c1"])
    coop = r.s.coops["mine"]
    coop["treasury"] = 1_000_000
    coop["inventory"].update({"machines": 1, "hand_tools": 1,
                              "electricity": 1_000})
    return r, coop


def test_durable_rent_is_amortized_not_double_depreciation():
    r, coop = _rent_world()
    rent_total = 0
    for _ in range(20):
        coop["labor_pool_hours"] = coop.get("labor_pool_hours", 0) + 50
        fund0 = r.s.capital_fund
        r.run([r.tx("c0", "PRODUCE", {"coop_id": "mine",
                                      "recipe_id": "iron_mining", "runs": 1})])
        assert r.rec().accepted, r.rec().reason
        rent_total += r.s.capital_fund - fund0
    # live replacement: machine 160 + tool 25 = 185; rent must be ~that,
    # NOT 20x the stale 1,500 rate (probe measured 31,200 before the fix)
    assert 150 <= rent_total <= 220, f"rent {rent_total} not amortized"


def test_nondurable_world_keeps_exact_legacy_rent():
    # replay-safety: no durable_capital -> rent formula byte-identical legacy
    r = R({"extended_catalog": True,
           "capital_rent": {"per_machine_used": 1_500,
                            "per_tool_used": 60}})
    found(r, "mine", ["c0", "c1"])
    coop = r.s.coops["mine"]
    coop["treasury"] = 10_000_000
    coop["inventory"].update({"machines": 999, "hand_tools": 999,
                              "electricity": 10_000})
    coop["labor_pool_hours"] = 50
    fund0 = r.s.capital_fund
    r.run([r.tx("c0", "PRODUCE", {"coop_id": "mine",
                                  "recipe_id": "iron_mining", "runs": 1})])
    assert r.rec().accepted
    assert r.s.capital_fund - fund0 == 1_500 + 60  # exact legacy rates


# ------------------------------------------------------------------ B4
def test_refresh_prices_from_live_baseline():
    r = R({"extended_catalog": True,
           "capital_refresh": {"interval_ticks": 10,
                               "machines": 2, "hand_tools": 5}})
    r.s.capital_fund = 100_000
    found(r, "works", ["c0", "c1"])
    coop = r.s.coops["works"]
    coop["inventory"]["machines"] = 0
    coop["inventory"]["hand_tools"] = 0
    fund0 = r.s.capital_fund
    for _ in range(10):
        r.run([])
    retired = fund0 - r.s.capital_fund
    live = (2 * r.s.good_cost_baseline["machines"]
            + 5 * r.s.good_cost_baseline["hand_tools"])
    assert retired == live, f"retired {retired} != live basket {live}"


# ------------------------------------------------------------------ B6
def test_demand_window_accumulates_pip_and_citizen_volume():
    r = R({"extended_catalog": True,
           "producer_input_priority": {"enabled": True,
                                       "share_cap_bp": 5_000}})
    found(r, "steelco", ["c0", "c1"])
    found(r, "toolco", ["c2", "c3"])
    r.s.coops["steelco"]["inventory"]["steel"] = 10
    r.s.coops["toolco"]["treasury"] = 100_000
    # same tick: listing + coop bid (PIP pass) + citizen bid (main pass)
    r.run([r.tx("c0", "LIST_GOOD", {"coop_id": "steelco",
                                     "good": "steel", "qty": 10}),
           r.tx("c2", "BID_FOR_COOP", {"coop_id": "toolco",
                                        "good": "steel",
                                        "max_price": 5_000, "qty": 4}),
           r.tx("c4", "BID", {"good": "steel",
                               "max_price": 5_000, "qty": 3})])
    assert r.s.recent_sales.get("steel") == 7, \
        f"window kept {r.s.recent_sales.get('steel')}, expected 7"
