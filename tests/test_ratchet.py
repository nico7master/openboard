"""Stage 5 blocking fix regression: capital ratchet must never re-engage.

Commit f4c9be8 fixed the 'deferred maintenance' disease where the capital
maintenance block skipped replenishment whenever want_produce was true.
Probes 60-65 then mapped the full dynamics: producers DO bid and DO get
served (PRODUCER_INPUT_CLEAR), machines are listed continuously by
machine_works, and the coop consumes one machine per production run
(capital wear by design). Therefore the honest recovery signal is NOT
terminal inventory (a producing coop legitimately sits at 0 between
wear cycles) but: machines DELIVERED to the coop AND a PRODUCE run with
the PRIMARY recipe within the 50-tick promise.
"""
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "dashboard"))

from server import Run  # noqa: E402

WINDOW = 50


def test_miner_recovers_primary_production_within_50_ticks() -> None:
    seed = 42
    run = Run(seed=seed)

    def drive(t0: int, t1: int) -> None:
        for t in range(t0, t1 + 1):
            actions = []
            for name, meta in sorted(run.bots.items()):
                rng = random.Random(f"{seed}:{t}:{name}")
                actions.extend(
                    meta["fn"](name, run.state, run.state.active_ruleset_params(), t, rng)
                )
            run._apply_batch(t, actions)

    # live steady state: real treasuries, listings, auctions
    drive(2, 302)
    s = run.state
    primary_recipe = s.coops["miners"].get("recipe_intent") or s.coops["miners"].get("trade")
    assert primary_recipe, "miners must declare a primary trade"

    # force the exact ratchet precondition: zero machines
    s.coops["miners"]["inventory"]["machines"] = 0

    # recovery must happen within the 50-tick promise:
    # (a) capital delivered via PRODUCER_INPUT_CLEAR, and
    # (b) at least one PRODUCE run with the primary recipe
    delivered = 0
    produced_primary = 0
    for t in range(303, 303 + WINDOW + 1):
        actions = []
        for name, meta in sorted(run.bots.items()):
            rng = random.Random(f"{seed}:{t}:{name}")
            actions.extend(
                meta["fn"](name, run.state, run.state.active_ruleset_params(), t, rng)
            )
        pre = len(s.applied)
        run._apply_batch(t, actions)
        for e in s.applied[pre:]:
            if (
                e.get("action") == "PRODUCER_INPUT_CLEAR"
                and e.get("good") == "machines"
                and any(x.get("coop_id") == "miners" for x in e.get("served", []))
            ):
                delivered += sum(x["qty"] for x in e["served"] if x.get("coop_id") == "miners")
            if (
                e.get("action") == "PRODUCE"
                and e.get("coop_id") == "miners"
                and e.get("recipe_id") == primary_recipe
            ):
                produced_primary += 1

    assert delivered >= 1, f"no machines delivered to miners within {WINDOW} ticks"
    assert produced_primary >= 1, (
        f"miners did not resume primary production ({primary_recipe}) within {WINDOW} ticks"
    )
