#!/usr/bin/env python
"""Priority 2 study: Player Behavior (docs/STUDY_PLAN.md).

Three questions, six arms, all at 1000 citizens / 650 ticks / 3 seeds:

  SKILLS  skills_off vs skills_on
          Learning-by-doing (+5%/lvl output, +3%/lvl wage, cap 5).
          Q: does boosted production outpace the capital (machine) chain?

  VOTING  vote_plain vs vote_bad
          Governance ON in both (natural politician bots active).
          vote_bad adds a scripted referendum at t=10: per-tick wealth tax
          {threshold: 1M units, rate_bp: 3000} + 700 scripted YES votes
          (quorum 500; 700 also clears the 2/3 constitutional bar).
          Q: can a majority vote a tax that kills its own factories?

  CRISIS  crisis_off vs crisis_on
          shocks profile 'harsh' in both. crisis_on adds the crisis rule
          (auto-declare on deaths, scripted ratification 600 YES, override
          suspends interest + gouging + need-first distribution).
          Q: does the emergency override save more people than laissez-faire?

Chaos rule (FINDINGS.md): compare within-seed only; 3 seeds per arm.
One combo per process, resumable JSON per combo under sweeps/p2/.
Always launch via scripts/memrun.sh.

Usage: p2_probe.py ARM SEED [ticks]
  ARM in: skills_off skills_on vote_plain vote_bad crisis_off crisis_on
Env: SMOKE=1 -> 12 ticks, 80 citizens (wiring check; prints diagnostics)
"""
import copy
import json
import os
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "dashboard"))
sys.path.insert(0, str(ROOT / "scripts"))

from server import Run  # noqa: E402
from stage6_scale_gate import (  # noqa: E402
    ESSENTIALS, drive, money_delta, scale_world, trim_retention,
)
from openboard.ledger import Transaction  # noqa: E402
from openboard.metrics import gini  # noqa: E402

OUT_DIR = ROOT / "sweeps" / "p2"
TARGET_CITIZENS = 1000

SMOKE = os.environ.get("SMOKE") == "1"
if SMOKE:
    TARGET_CITIZENS = 80

PROPOSE_TICK = 3 if SMOKE else 10
VOTE_WINDOW = 3
VOTE_SHARE = 0.72                     # ~720/1000 full, ~130/181 smoke
N_RATIFY = 50 if SMOKE else 600       # (unused once forced declarations on)

SKILLS_PARAMS = {
    "enabled": True, "hours_per_level": 100, "max_level": 5,
    "output_bonus_bp": 500, "wage_bonus_bp": 300,
}
# catastrophic referendum: 50%/tick of everything above 500 credits.
# The tax is a pool transfer (nothing destroyed) - the kill channel is
# savings starvation: founders/demand/founder accumulation all dry up.
BAD_TAX = {"threshold": 50_000, "rate_bp": 5000}
CRISIS_PARAMS = {"enabled": True, "max_ticks": 100}
SHOCKS_PARAMS = {"enabled": True, "profile": "harsh"}
GOV_PARAMS = {
    "enabled": True, "vote_window_ticks": VOTE_WINDOW,
    "quorum_bp": 5_000, "trial_period_ticks": 10,
}
# deterministic crisis windows: source='vote' is pre-ratified, so no
# ratification scripting needed. Re-declared after each max_ticks expiry.
CRISIS_TICKS = (5,) if SMOKE else (100, 300, 500)

ARMS = (
    "skills_off", "skills_on",
    "vote_plain", "vote_bad",
    "crisis_off", "crisis_on",
)


class P2Run(Run):
    """Arm-specific params + scripted transactions via _apply_batch
    (the one hook that always fires under drive())."""

    def __init__(self, arm: str, **kw):
        self.arm = arm
        self.proposed = False
        self.voted = False
        self.ratified_once = False
        self.declared = {}  # crisis ticks already force-declared
        super().__init__(
            scenario="equal",
            governance=arm.startswith("vote"),
            **kw,
        )

    def _params(self):
        p = super()._params()
        arm = self.arm
        if arm.startswith("skills"):
            sk = dict(SKILLS_PARAMS)
            sk["enabled"] = arm == "skills_on"
            p["skills"] = sk
        elif arm.startswith("vote"):
            p["governance"] = dict(GOV_PARAMS)
        elif arm.startswith("crisis"):
            p["shocks"] = dict(SHOCKS_PARAMS)
            if arm == "crisis_on":
                p["crisis"] = dict(CRISIS_PARAMS)
        return p

    def _alive(self, n: int) -> list[str]:
        names = sorted(k for k in self.state.balances)
        return names[:n]

    def _apply_batch(self, tick, batch):
        s = self.state
        arm = self.arm

        # --- voting: scripted catastrophic referendum -------------
        if arm == "vote_bad" and tick == PROPOSE_TICK and not self.proposed:
            self.proposed = True
            full = copy.deepcopy(s.active_ruleset_params())
            full["wealth_tax"] = dict(BAD_TAX)
            full["governance"] = dict(GOV_PARAMS)
            batch.append(Transaction(
                tick=tick, sender=self._alive(1)[0], action="PROPOSE",
                payload={"params": full,
                         "activation_tick": tick + VOTE_WINDOW + 2},
                ruleset_version=1,
            ))
        if (arm == "vote_bad" and tick == PROPOSE_TICK + 1
                and not self.voted and s.next_proposal_id > 1):
            self.voted = True
            pid = f"p{s.next_proposal_id - 1}"  # the just-opened proposal
            n_yes = int(len(s.balances) * VOTE_SHARE)
            for name in self._alive(n_yes):
                batch.append(Transaction(
                    tick=tick, sender=name, action="VOTE",
                    payload={"proposal_id": pid, "choice": "for"},
                    ruleset_version=1,
                ))

        # --- crisis: deterministic pre-ratified declarations ------
        if arm == "crisis_on" and tick in CRISIS_TICKS and not self.declared.get(tick):
            from openboard.crisis import declare_crisis
            self.declared[tick] = True
            declare_crisis(s, tick, "pandemic", "vote")

        super()._apply_batch(tick, batch)


def _inventory_by_good(state) -> dict[str, int]:
    totals: dict[str, int] = {}
    for c in state.coops.values():
        for g, q in (c.get("inventory") or {}).items():
            totals[g] = totals.get(g, 0) + int(q)
    return totals


def run(arm: str, seed: int, ticks: int) -> dict:
    out = OUT_DIR / f"{arm}_s{seed}.json"
    if out.exists():
        return json.loads(out.read_text())  # resumable
    t0 = time.perf_counter()
    r = P2Run(arm=arm, seed=seed)
    series = []
    produced_total = deaths_total = 0
    tax_units_total = tax_events = 0
    crisis_ticks = 0
    action_hist: Counter = Counter()
    goods_keys = None

    for t in range(2, ticks + 1):
        drive(r, seed, t, t)
        if t == 2:
            scale_world(r, TARGET_CITIZENS)
        s = r.state
        for e in s.applied:
            a = e.get("action", "")
            action_hist[a] += 1
            if a.startswith("PRODUCE") and a != "PRODUCE_FAIL":
                produced_total += 1
            elif a == "CITIZEN_DEATH":
                deaths_total += 1
            elif a == "WEALTH_TAX":
                tax_events += 1
                tax_units_total += int(e.get("tax", 0))  # key is 'tax', not 'amount'
        if getattr(s, "crisis", None) and s.crisis.get("active"):
            crisis_ticks += 1

        if t % 5 == 0 or t == ticks:
            inv = _inventory_by_good(s)
            machine_total = sum(q for g, q in inv.items()
                                if "machine" in g or "tool" in g)
            unmet = sum(1 for u in s.unmet_needs.values()
                        if any(u.get(g) for g in ESSENTIALS))
            series.append([t, len(s.balances), gini(list(s.balances.values())),
                           unmet, int(s.surplus_pool), produced_total,
                           deaths_total, machine_total])
        s.applied.clear()
        r.batches.clear()
        if t % 50 == 0:
            trim_retention(r)

    s = r.state
    proposals = {
        pid: {"status": p["status"],
              "votes": len(p["ballots"]),
              "activation_tick": p["activation_tick"]}
        for pid, p in s.proposals.items()
    }
    money = money_delta(r)
    money_ok = money == 0
    detail = f"money_delta={money}" if not money_ok else None
    final_inv = _inventory_by_good(s)
    unmet_final = sum(1 for u in s.unmet_needs.values()
                      if any(u.get(g) for g in ESSENTIALS))
    res = {
        "arm": arm, "seed": seed, "ticks": ticks,
        "smoke": SMOKE,
        "wall_s": round(time.perf_counter() - t0, 1),
        "final": {
            "pop": len(s.balances),
            "unmet": unmet_final,
            "pool_units": int(s.surplus_pool),
            "gini": gini(list(s.balances.values())),
            "produced_total": produced_total,
            "deaths_total": deaths_total,
            "tax_events": tax_events,
            "tax_units_total": tax_units_total,
            "crisis_ticks": crisis_ticks,
            "inventory": final_inv,
            "money_ok": money_ok,
            "money_detail": detail if not money_ok else None,
        },
        "proposals": proposals,
        "crisis_state": dict(getattr(s, "crisis", None) or {}),
        "series": series,  # [t, pop, gini, unmet, pool, produced, deaths, machines]
    }
    if SMOKE:
        res["diag"] = {
            "action_hist": dict(action_hist.most_common(30)),
            "goods_keys": sorted(s.goods.keys()) if hasattr(s, "goods") else None,
        }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, indent=2, sort_keys=True))
    return res


if __name__ == "__main__":
    arm = sys.argv[1] if len(sys.argv) > 1 else "skills_on"
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 42
    ticks = int(sys.argv[3]) if len(sys.argv) > 3 else (12 if SMOKE else 650)
    res = run(arm, seed, ticks)
    print(json.dumps(res, sort_keys=True), flush=True)
