"""Policy Lab: knobs, deterministic forks, comparison, adoption path."""
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "dashboard"))

from openboard.policy import (
    KNOBS, _apply_patch_to_params, compare, fork_experiment, knob_by_id,
    option_by_id,
)
from openboard.rules import validate_params
from server import BASELINE_BOTS, Run


# ------------------------------------------------------------- registry

def test_knob_registry_valid():
    ids = [k["id"] for k in KNOBS]
    assert len(ids) == len(set(ids)), "duplicate knob ids"
    for k in KNOBS:
        assert k["question"], f"{k['id']} missing question"
        assert k["options"], f"{k['id']} has no options"
        for o in k["options"]:
            assert o["label"] and isinstance(o["patch"], dict)


def test_option_patches_schema_valid():
    run = Run(seed=42, governance=False)
    params = run.state.active_ruleset_params()
    goods = set(run.state.goods.keys())
    for k in KNOBS:
        for o in k["options"]:
            merged = _apply_patch_to_params(params, o["patch"])
            reason = validate_params(merged, known_goods=goods)
            assert reason is None, f"{k['id']}/{o['label']}: {reason}"


def test_deep_merge_preserves_required_keys():
    """wealth_tax requires exactly {threshold, rate_bp}: a rate-only patch
    must INHERIT threshold from the live params, not drop it."""
    base = {"wealth_tax": {"threshold": 5000, "rate_bp": 400}}
    out = _apply_patch_to_params(base, {"wealth_tax": {"rate_bp": 800}})
    assert out["wealth_tax"] == {"threshold": 5000, "rate_bp": 800}


# --------------------------------------------------------- fork machinery

def _drive(run: Run, ticks: int) -> None:
    """Advance `ticks` ticks starting AFTER the current tick (tick 1's
    founding batch is applied by Run.__init__ and must not be overwritten)."""
    for t in range(run.state.tick + 1, run.state.tick + ticks + 1):
        actions = []
        for name, meta in sorted(run.bots.items()):
            rng = random.Random(f"{run.seed}:{t}:{name}")
            actions.extend(meta["fn"](name, run.state, run.state.active_ruleset_params(), t, rng))
        run._apply_batch(t, actions)


def test_noop_fork_is_byte_identical():
    """Same params in both forks => identical outcomes (determinism)."""
    run = Run(seed=42, governance=False)
    _drive(run, 30)
    res = fork_experiment(run, "work_week", "Standard (8h)", ticks=40)
    b, p = res["baseline"], res["policy"]
    assert b["gini_bp"] == p["gini_bp"]
    assert b["treasury"] == p["treasury"]
    assert b["max_people_unmet"] == p["max_people_unmet"]


def test_fork_does_not_touch_live_world():
    run = Run(seed=42, governance=False)
    _drive(run, 30)
    gini_before = run.state.balances.copy()
    tick_before = run.state.tick
    fork_experiment(run, "labor_pool", "Capped", ticks=30)
    assert run.state.balances == gini_before, "live world mutated by fork"
    assert run.state.tick == tick_before, "live world must not advance"


def test_policy_fork_changes_params_only_in_policy():
    run = Run(seed=42, governance=False)
    _drive(run, 20)
    base_params = run.state.active_ruleset_params()
    fork_experiment(run, "work_week", "Short (6h)", ticks=10)
    assert run.state.active_ruleset_params() == base_params, "live params changed"


def test_compare_rows_plain_language():
    run = Run(seed=42, governance=False)
    _drive(run, 30)
    res = fork_experiment(run, "wealth_tax", "Heavy", ticks=30)
    rows = compare(res)
    metrics = [r["metric"] for r in rows]
    assert "Inequality (Gini)" in metrics
    for r in rows:
        assert r["verdict"] in ("better", "worse", "same")
        assert r["sentence"].strip(), "empty plain sentence"


def test_tick_cap_enforced():
    run = Run(seed=42, governance=False)
    res = fork_experiment(run, "wealth_tax", "Firm", ticks=100_000)
    assert res["ticks"] <= 500, "D-PL.4: experiment ticks capped"


# ------------------------------------------------------------ adopt path

def test_adopt_via_rule_change_transaction():
    """Adoption = real ledger RULE_CHANGE, not silent param edit (D-PL.3)."""
    from openboard.ledger import Transaction
    from openboard.policy import knob_by_id

    run = Run(seed=42, governance=False)
    _drive(run, 20)
    before = run.state.active_ruleset_params()["wealth_tax"]["rate_bp"]

    knob = knob_by_id("wealth_tax")
    opt = option_by_id(knob, "Heavy")
    params = _apply_patch_to_params(run.state.active_ruleset_params(), opt["patch"])
    assert validate_params(params, known_goods=set(run.state.goods.keys())) is None

    tx = __import__("openboard.ledger", fromlist=["Transaction"]).Transaction(
        tick=run.state.tick + 1,
        sender=sorted(run.state.balances.keys())[0],
        action="RULE_CHANGE",
        payload={"params": params, "activation_tick": run.state.tick + 2},
        ruleset_version=run.state.ruleset_version,
    )
    run.pending.append(tx)
    # real tick path: Run.tick() merges pending txs into the batch
    for _ in range(3):
        run.tick()

    assert run.state.ruleset_version >= 2, "RULE_CHANGE must bump version"
    after = run.state.active_ruleset_params()["wealth_tax"]["rate_bp"]
    assert after == 800 and before == 400
    rc = [e for e in run.state.applied if e.get("action") == "RULE_CHANGE"]
    assert rc, "RULE_CHANGE event recorded in ledger"
