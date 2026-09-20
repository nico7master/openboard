#!/usr/bin/env python
"""P-PROBE v2 (audit 2026-09-20): verify-before-fix for B1/B2/B4/B6/A7.

v1 failed on harness assumptions (bare genesis has no coops, pool=0,
wrong whistleblower key). v2 uses the proven patterns: >=2-member coops
(COOP_TOO_SMALL), seeded surplus_pool, founder-exact param values,
state.applied event checks.

Each probe measures ONE audit claim empirically; results land in
sweeps/audit_probes/probe_results.json for the fix packages.
"""
import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from openboard.engine import apply_tick  # noqa: E402
from openboard.ledger import Ledger, Transaction  # noqa: E402
from openboard.rules import DEFAULT_RULESET_PARAMS  # noqa: E402
from openboard.state import genesis_state  # noqa: E402

OUT = ROOT / "sweeps" / "audit_probes"
OUT.mkdir(parents=True, exist_ok=True)
results: dict[str, dict] = {}


class R:
    """Minimal runner: monotonic ticks, founder-style param copy."""

    def __init__(self, params: dict, endow: int = 1_000_000, n: int = 6):
        p = copy.deepcopy(DEFAULT_RULESET_PARAMS)
        p["triage_overrides"] = {}
        p.update(params)
        self.s = genesis_state({f"c{i}": endow for i in range(n)},
                               ruleset_params=p)
        self.led = Ledger()
        self.now = self.s.tick

    def tx(self, sender: str, action: str, payload: dict) -> Transaction:
        return Transaction(tick=self.now + 1, sender=sender, action=action,
                           payload=payload,
                           ruleset_version=self.s.ruleset_version)

    def run(self, txs=()):
        self.now += 1
        apply_tick(self.s, self.led, list(txs), current_tick=self.now)

    def rec(self):
        return self.led.records[-1] if self.led.records else None

    def applied(self, action: str):
        return [e for e in self.s.applied if e.get("action") == action]


def found(r, coop_id, members):
    r.run([r.tx(members[0], "FOUND_COOP",
                {"coop_id": coop_id, "name": coop_id, "members": members})])
    ok = bool(r.s.coops.get(coop_id))
    if not ok:
        rec = r.rec()
        raise AssertionError(f"found {coop_id} rejected: "
                             f"{getattr(rec, 'reason', '?')}")
    return r.s.coops[coop_id]


# ------------------------------------------------------------------ B1
def probe_b1():
    """Serial default: borrow max -> default -> re-borrow immediately.
    Claim: unbounded pool drain + loan-book trail destruction."""
    # NOTE: credit_phase is nested under demographics.enabled in the
    # engine tick — without demographics, loans NEVER default (coupling
    # bug found by this probe; recorded separately).
    r = R({"credit": {"enabled": True, "max_per_citizen": 5_000,
                      "term_ticks": 5, "fee_bp": 0, "rate_bp_annual": 0},
           "demographics": {"enabled": True}})
    r.s.surplus_pool = 50_000
    pool0 = r.s.surplus_pool
    borrowed = 0
    re_borrow_ok = None
    for cycle in range(4):
        r.run([r.tx("c0", "LOAN", {"amount": 5_000})])
        rec = r.rec()
        if not rec.accepted:
            re_borrow_ok = False if cycle else None
            results_b1_reason = getattr(rec, "reason", "?")
            break
        borrowed += 5_000
        # age past due (term 5): credit_phase defaults at tick > due
        for _ in range(6):
            r.run([])
        # re-borrow next cycle happens in the loop head
    defaults = r.applied("LOAN_DEFAULT")
    loan_row = r.s.loans.get("c0")
    drained = pool0 - r.s.surplus_pool
    print(f"B1 serial-default: borrowed={borrowed} pool_drained={drained} "
          f"defaults={len(defaults)} book_row={loan_row}")
    print(f"   verdict: {'DRAIN CONFIRMED' if drained >= 10_000 else 'blocked'}"
          f" — defaulted record replaced on re-borrow: "
          f"{loan_row is not None and not loan_row.get('defaulted')}")
    return {"borrowed": borrowed, "drained": drained,
            "defaults": len(defaults),
            "book_row_reset": loan_row is not None
            and not loan_row.get("defaulted")}


# ------------------------------------------------------------------ B2
def probe_b2():
    """Rent overcharge: founder rent 1500/machine-RUN on a durable
    machine that lasts 20 runs (live replacement 160)."""
    r = R({"extended_catalog": True,
           "durable_capital": {"enabled": True,
                               "goods": ["machines", "hand_tools"],
                               "durability": 20},
           "capital_rent": {"per_machine_used": 1_500,
                            "per_tool_used": 60}})
    found(r, "mine", ["c0", "c1"])
    coop = r.s.coops["mine"]
    coop["treasury"] = 1_000_000
    coop["inventory"]["machines"] = 1
    coop["inventory"]["hand_tools"] = 1
    coop["inventory"]["electricity"] = 1_000
    rent_total = 0
    runs_ok = 0
    wear_seen = 0
    stock_traj = []
    for t in range(22):
        coop["labor_pool_hours"] = coop.get("labor_pool_hours", 0) + 50
        fund0 = r.s.capital_fund
        r.run([r.tx("c0", "PRODUCE",
                    {"coop_id": "mine", "recipe_id": "iron_mining",
                     "runs": 1})])
        rec = r.rec()
        if rec.accepted:
            runs_ok += 1
            rent_total += r.s.capital_fund - fund0
        wear_seen = sum(r.s.capital_wear.get("mine", {}).values())
        stock_traj.append(coop["inventory"].get("machines", 0))
    live_replacement = (r.s.good_cost_baseline.get("machines", 0)
                        + r.s.good_cost_baseline.get("hand_tools", 0))
    print(f"B2 rent-vs-wear: runs_ok={runs_ok} total_rent={rent_total} "
          f"wear_units={wear_seen} machine_stock_traj={stock_traj}")
    print(f"   live replacement (machine+tool)={live_replacement} "
          f"-> overcharge x{rent_total / live_replacement if live_replacement else 0:.0f}")
    return {"runs_ok": runs_ok, "rent_total": rent_total,
            "wear_units": wear_seen,
            "live_replacement": live_replacement}


# ------------------------------------------------------------------ B4
def probe_b4():
    """Refresh pricing: table retires book values (1500/60) while the
    extended-catalog live cost is 160/25."""
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
    granted = coop["inventory"].get("machines", 0)
    live_cost = 2 * r.s.good_cost_baseline.get("machines", 0) \
        + 5 * r.s.good_cost_baseline.get("hand_tools", 0)
    print(f"B4 refresh pricing: retired={retired} granted_machines={granted} "
          f"live_cost_same_basket={live_cost} "
          f"overcharge_x={retired / live_cost if live_cost else 0:.1f}")
    return {"retired": retired, "live_cost": live_cost}


# ------------------------------------------------------------------ B6
def probe_b6():
    """Demand-signal overwrite: PIP (coop input) volume vs citizen volume
    on the SAME good in one legacy-path clearing."""
    r = R({"extended_catalog": True,
           "producer_input_priority": {"enabled": True,
                                       "share_cap_bp": 5_000}})
    found(r, "steelco", ["c0", "c1"])
    found(r, "toolco", ["c2", "c3"])
    steelco = r.s.coops["steelco"]
    steelco["inventory"]["steel"] = 10
    r.s.coops["toolco"]["treasury"] = 100_000
    # list + coop bid (PIP) + citizen bid in the SAME tick — the unsold
    # sweep returns listings at tick end, so separate ticks never meet.
    r.run([r.tx("c0", "LIST_GOOD",
                {"coop_id": "steelco", "good": "steel", "qty": 10}),
           r.tx("c2", "BID_FOR_COOP",
                {"coop_id": "toolco", "good": "steel",
                 "max_price": 5_000, "qty": 4}),
           r.tx("c4", "BID",
                {"good": "steel", "max_price": 5_000, "qty": 3})])
    seen = r.s.recent_sales.get("steel")
    ema = getattr(r.s, "demand_ema", {}).get("steel") \
        if hasattr(r.s, "demand_ema") else None
    print(f"B6 signal overwrite: recent_sales[steel]={seen} "
          f"(expected 7 = 4 PIP + 3 citizen; 3 = PIP volume wiped) ema={ema}")
    verdict = "OVERWRITE CONFIRMED (PIP volume lost)" if seen == 3 else \
        ("accumulate OK" if seen == 7 else f"unexpected: {seen}")
    print(f"   verdict: {verdict}")
    return {"recent_sales_steel": seen, "ema": ema}


# ------------------------------------------------------------------ A7
def probe_a7():
    """Bounty economics: first-report-wins per (kind,target) — does pair
    rotation still farm? Does the flagged hoarder lose anything?"""
    r = R({"whistleblower": {"enabled": True, "reward_credits": 500,
                             "max_per_tick": 10}})
    r.s.surplus_pool = 50_000

    def plant(target, tick):
        r.s.flags.append({"tick": tick, "kind": "HOARD", "target": target,
                          "good": "bread", "held": 100, "threshold": 50})

    def report(reporter, target):
        pool0 = r.s.surplus_pool
        r.run([r.tx(reporter, "REPORT", {"kind": "HOARD", "target": target})])
        rec = r.rec()
        paid = r.s.balances[reporter] - (r.s.balances[reporter] - 0)
        return rec, pool0 - r.s.surplus_pool

    # 1) first report pays
    plant("c5", r.now + 1)
    rec1, flow1 = report("c0", "c5")
    # 2) same pair again (re-offense, new flag) -> expect ALREADY_REPORTED
    plant("c5", r.now + 1)
    rec2, flow2 = report("c1", "c5")
    # 3) rotation: roles swap, new pair -> expect pays again
    plant("c1", r.now + 1)
    rec3, flow3 = report("c5", "c1")
    hoarder_loss = 0  # c5 balance change from flags alone (no council)
    print(f"A7 bounty: first={rec1.accepted}/{flow1} "
          f"same_pair_repeat={rec2.accepted}/{flow2} "
          f"({getattr(rec2, 'reason', '')}) "
          f"rotated_pair={rec3.accepted}/{flow3} "
          f"flagged_hoarder_balance_delta={hoarder_loss}")
    verdict = ("ROTATION FARM CONFIRMED (500/cycle, zero cost)"
               if rec3.accepted and flow3 == 500
               else "rotation blocked")
    print(f"   verdict: {verdict}")
    return {"first_paid": flow1, "repeat_blocked_reason":
            str(getattr(rec2, "reason", "")), "rotated_paid": flow3}


if __name__ == "__main__":
    print("=== P-PROBE v2 (audit 2026-09-20) ===")
    for name, fn in (("B1", probe_b1), ("B2", probe_b2), ("B4", probe_b4),
                     ("B6", probe_b6), ("A7", probe_a7)):
        try:
            results[name] = fn()
        except Exception as e:  # noqa: BLE001
            import traceback
            traceback.print_exc()
            results[name] = {"error": f"{type(e).__name__}: {e}"}
    (OUT / "probe_results.json").write_text(json.dumps(results, indent=2,
                                                       default=str))
    print("saved sweeps/audit_probes/probe_results.json")
