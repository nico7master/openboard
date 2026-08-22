#!/usr/bin/env python
"""Stage 1 gate: democracy in the loop. 3 seeds x 2000 ticks with
governance LIVE and a balanced electorate. Tracks proposal activity,
rule evolution, and economic stability. Usage: politics_gate.py [ticks] [seed...]"""
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "dashboard"))

from server import Run  # noqa: E402
from openboard.metrics import gini  # noqa: E402


def run_world(seed: int, ticks: int, heal: bool = False):
    run = Run(seed=seed, governance=True)
    if heal:
        # break the world on purpose: no wealth tax at genesis. Can the
        # society perceive rising inequality and vote the tax back in?
        run.state.rulesets[0]["params"].pop("wealth_tax", None)
    proposals = passed = failed = 0
    gini_path, unmet_path = [], []
    rule_versions = set()
    for t in range(2, ticks + 1):
        actions = []
        for name, meta in sorted(run.bots.items()):
            rng = random.Random(f"{seed}:{t}:{name}")
            actions.extend(meta["fn"](name, run.state, run.state.active_ruleset_params(), t, rng))
        run._apply_batch(t, actions)
        run._record_timeline()
        s = run.state
        wealth = (list(s.balances.values()) + [s.surplus_pool, s.capital_fund]
                  + [c.get("treasury", 0) for c in s.coops.values()])
        gini_path.append(gini(wealth))
        unmet_path.append(sum(len(v) for v in s.unmet_needs.values()))
        rule_versions.update(rs["version"] for rs in s.rulesets)
    events = [e for e in run.state.applied if e and e.get("action") == "PROPOSAL_SETTLED"]
    proposals = len(events)
    passed = sum(1 for e in events if e["result"] == "passed")
    failed = proposals - passed
    # money invariant (exact formula from tests: initial + minted - retired)
    s = run.state
    total = sum(s.balances.values()) + s.surplus_pool + s.capital_fund \
        + sum(c.get("treasury", 0) for c in s.coops.values())
    expected = 14 * 500 + 4 * 600 + s.money_minted - s.money_retired
    invariant = total - expected
    # heal evidence: when did wealth_tax come back (if it was removed)?
    heal_tick = None
    if heal:
        for e in events:
            if e["result"] == "passed":
                # find the passed proposal that restored the tax
                p = run.state.proposals.get(e["proposal_id"], {})
                if p and "wealth_tax" in p.get("params", {}):
                    heal_tick = e["tick"]
                    break
        else:
            heal_tick = run.state.tick if "wealth_tax" in run.state.active_ruleset_params() else None
    return {
        "seed": seed, "gini_end": gini_path[-1], "gini_max": max(gini_path),
        "gini_peak": gini_path[heal_tick - 2] if heal and heal_tick and heal_tick >= 2 else None,
        "unmet_end": unmet_path[-1], "unmet_last500": max(unmet_path[-500:]),
        "proposals": proposals, "passed": passed, "failed": failed,
        "rule_versions": len(rule_versions), "invariant_ok": invariant == 0,
        "heal_tick": heal_tick, "tax_restored": "wealth_tax" in run.state.active_ruleset_params(),
        "tax_rate": run.state.active_ruleset_params().get("wealth_tax", {}).get("rate_bp", 0),
    }


def main():
    ticks = int(sys.argv[1]) if len(sys.argv) > 1 else 2000
    args = [a for a in sys.argv[2:] if not a.startswith("--")]
    heal = "--heal" in sys.argv
    seeds = [int(x) for x in args] or [42, 7, 123]
    for seed in seeds:
        r = run_world(seed, ticks, heal=heal)
        extra = ""
        if heal:
            extra = (f" tax_restored={r['tax_restored']} at_tick={r['heal_tick']} "
                     f"gini_at_heal={r['gini_peak']} final_rate={r['tax_rate']}bp")
        print(f"seed {r['seed']}: gini end={r['gini_end']} max={r['gini_max']} "
              f"unmet end={r['unmet_end']} last500max={r['unmet_last500']} "
              f"proposals={r['proposals']} passed={r['passed']} failed={r['failed']} "
              f"rule_versions={r['rule_versions']} invariant={'OK' if r['invariant_ok'] else 'BROKEN'}{extra}")


if __name__ == "__main__":
    main()
