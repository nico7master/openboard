"""Policy Lab: plain-language policy knobs + honest fork experiments.

The game loop is 'change the rules -> watch what happens'. Because the
engine is deterministic, forking the SAME world snapshot into a baseline
and a policy variant and driving both with the bot cast makes every
difference in outcome PROVABLY caused by the policy change (D-PL.1).

Knobs are a registry (D-PL.5): each knob is one plain-language question
with options that patch rule params. Adding a policy = one dict entry.
Adoption always goes through RULE_CHANGE (ledger event, D-PL.3).
"""
from __future__ import annotations

import copy
import random
from typing import Any, Callable

from openboard.metrics import gini


# ----------------------------------------------------------------- knobs
# option value None = remove an OPTIONAL_PARAM (schema default applies)
KNOBS: list[dict[str, Any]] = [
    {
        "id": "wealth_tax",
        "question": "How hard should society tax the very rich?",
        "param": "wealth_tax",
        "current_of": "rate_bp",
        "options": [
            {"label": "None", "patch": {"wealth_tax": None},
             "explanation": "No wealth tax — fortunes grow unchecked."},
            {"label": "Light", "patch": {"wealth_tax": {"rate_bp": 100}},
             "explanation": "A gentle 1% levy on large fortunes."},
            {"label": "Firm", "patch": {"wealth_tax": {"rate_bp": 400}},
             "explanation": "A firm 4% levy — the tested balance point."},
            {"label": "Heavy", "patch": {"wealth_tax": {"rate_bp": 800}},
             "explanation": "A heavy 8% levy — strong equality, may chill saving."},
        ],
    },
    {
        "id": "dividend_share",
        "question": "What share of the surplus goes straight back to citizens?",
        "param": "surplus_spending",
        "current_of": "dividend_share_bp",
        "options": [
            {"label": "Small", "patch": {"surplus_spending": {"dividend_share_bp": 1000}},
             "explanation": "10% of surplus becomes citizen dividends."},
            {"label": "Half", "patch": {"surplus_spending": {"dividend_share_bp": 5000}},
             "explanation": "50% of surplus flows back as dividends."},
            {"label": "Most", "patch": {"surplus_spending": {"dividend_share_bp": 8000}},
             "explanation": "80% of surplus flows back — big checks, leaner public funds."},
        ],
    },
    {
        "id": "work_week",
        "question": "How long is the standard work day?",
        "param": "max_work_hours_cumulative",
        "current_of": None,
        "options": [
            {"label": "Short (6h)", "patch": {"max_work_hours_cumulative": 6},
             "explanation": "More free time, less production per citizen."},
            {"label": "Standard (8h)", "patch": {"max_work_hours_cumulative": 8},
             "explanation": "The tested default."},
            {"label": "Long (10h)", "patch": {"max_work_hours_cumulative": 10},
             "explanation": "More output, more burnout risk."},
        ],
    },
    {
        "id": "labor_pool",
        "question": "Should society cap the shared labor pool?",
        "param": "labor_pool_cap",
        "current_of": None,
        "options": [
            {"label": "Uncapped", "patch": {"labor_pool_cap": None},
             "explanation": "Anyone may work any amount — maximum output, hoarding risk."},
            {"label": "Capped", "patch": {"labor_pool_cap": 160},
             "explanation": "A shared-hours ceiling protects against labor hoarding."},
        ],
    },
    {
        "id": "needs_generosity",
        "question": "How generous are the guaranteed needs quotas?",
        "param": "needs",
        "current_of": None,
        "kind": "needs_scale",
        "options": [
            {"label": "Standard", "patch": {"needs_scale": 1.0},
             "explanation": "Current quotas."},
            {"label": "Generous (+50%)", "patch": {"needs_scale": 1.5},
             "explanation": "Everyone is entitled to 50% more of every good — costs rise."},
        ],
    },
]


def knob_by_id(knob_id: str) -> dict[str, Any] | None:
    for k in KNOBS:
        if k["id"] == knob_id:
            return k
    return None


def option_by_id(knob: dict[str, Any], option_id: str) -> dict[str, Any] | None:
    for i, o in enumerate(knob["options"]):
        if o["label"] == option_id or f"{knob['id']}:{i}" == option_id:
            return o
    return None


def _apply_patch_to_params(params: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    """Return a validated-shape copy of `params` with the knob patch applied.
    Schema rule: OPTIONAL_PARAM dicts have REQUIRED key sets (wealth_tax =
    {threshold, rate_bp}; surplus_spending requires 4+ keys), so patches
    are DEEP-MERGED into the live values, never substituted. Value None
    removes an OPTIONAL_PARAM (schema default takes over)."""
    out = copy.deepcopy(params)
    for key, val in patch.items():
        if val is None:
            out.pop(key, None)
        elif key == "needs_scale":
            base = out.get("needs") or {}
            out["needs"] = {g: max(1, int(round(q * val))) for g, q in base.items()}
        elif isinstance(val, dict) and isinstance(out.get(key), dict):
            merged = dict(out[key])
            merged.update(val)
            out[key] = merged
        else:
            out[key] = val
    return out


def fork_experiment(live_run: Any, knob_id: str, option_id: str, ticks: int = 200) -> dict[str, Any]:
    """Fork the live world into baseline + policy clones, drive both with
    the same bot cast (D-PL.2), and return an honest comparison.
    Runs on a snapshot: the live world keeps ticking (stamped fork_tick)."""
    from server import Run  # local import: fork uses the dashboard Run class

    knob = knob_by_id(knob_id)
    if knob is None:
        raise ValueError(f"unknown knob {knob_id}")
    option = option_by_id(knob, option_id)
    if option is None:
        raise ValueError(f"unknown option {option_id}")
    ticks = max(10, min(int(ticks), 500))  # D-PL.4

    with live_run.lock:
        snap = live_run.to_save()
        fork_tick = live_run.state.tick
        seed = live_run.seed

    base = live_run.from_save(snap)
    pol = live_run.from_save(snap)

    # policy patch: validate the merged params, then mutate the POLICY
    # FORK's active ruleset IN PLACE. A version bump here would make the
    # engine reject every bot tx as RULESET_MISMATCH (measured: 359 events
    # vs 3,982 in baseline at tick 2) — the fork is a throwaway what-if
    # world, so provenance is not needed. The LIVE adopt path uses real
    # ledger RULE_CHANGE (D-PL.3).
    pol_params = _apply_patch_to_params(base.state.active_ruleset_params(), option["patch"])
    from openboard.rules import validate_params
    reason = validate_params(pol_params, known_goods=set(pol.state.goods.keys()))
    if reason is not None:
        raise ValueError(f"policy patch invalid: {reason}")
    _active_idx = max(range(len(pol.state.rulesets)), key=lambda i: pol.state.rulesets[i]["version"])
    pol.state.rulesets[_active_idx]["params"] = pol_params

    def drive(run: Any) -> None:
        for t in range(fork_tick + 1, fork_tick + ticks + 1):
            actions = []
            for name, meta in sorted(run.bots.items()):
                rng = random.Random(f"{seed}:{t}:{name}")
                actions.extend(meta["fn"](name, run.state, run.state.active_ruleset_params(), t, rng))
            run._apply_batch(t, actions)

    drive(base)
    drive(pol)
    return {
        "knob_id": knob_id,
        "option": option["label"],
        "explanation": option["explanation"],
        "fork_tick": fork_tick,
        "ticks": ticks,
        "baseline": _collect(base, fork_tick + ticks - 200),
        "policy": _collect(pol, fork_tick + ticks - 200),
    }


def _collect(run: Any, window_from: int) -> dict[str, Any]:
    s = run.state
    citizens = len(s.balances)
    # needs met in final window (sampled like the gate)
    worst = 0
    unmet_people = 0
    for t in range(max(1, window_from), s.tick + 1):
        if t % 10:
            continue
        people = 0
        for cit, d in s.unmet_needs.items():
            if any(v > 0 for v in d.values()):
                people += 1
            worst = max(worst, max((int(v) for v in d.values()), default=0))
        unmet_people = max(unmet_people, people)
    balances = sorted(s.balances.values())
    g = gini(balances) if hasattr(gini, "__call__") else None
    total = sum(balances) or 1
    top10 = sum(balances[-max(1, len(balances) // 10):]) * 100 // total
    flags: dict[str, int] = {}
    for e in s.applied:
        if e.get("tick", 0) > window_from and e.get("action") in ("HOARD", "MARKET_POWER", "FREE_RIDER", "WASH_BID"):
            flags[e["action"]] = flags.get(e["action"], 0) + 1
    return {
        "population": citizens,
        "worst_unmet_streak": worst,
        "max_people_unmet": unmet_people,
        "gini_bp": g,
        "top10_share_bp": top10,
        "flags": flags,
        "treasury": s.surplus_pool,
    }


def compare(result: dict[str, Any]) -> list[dict[str, Any]]:
    """Plain-language metric rows: {metric, baseline, policy, verdict, sentence}."""
    b, p = result["baseline"], result["policy"]
    rows: list[dict[str, Any]] = []

    def pct(x, y):
        if x == 0:
            return 100 if y == 0 else -100
        return round((x - y) * 100 / x)

    # inequality
    bg, pg = b["gini_bp"], p["gini_bp"]
    d = pct(bg, pg)
    rows.append({
        "metric": "Inequality (Gini)", "baseline": bg, "policy": pg,
        "verdict": "better" if pg < bg * 995 // 1000 else ("worse" if pg > bg * 1005 // 1000 else "same"),
        "sentence": (f"Inequality {'fell' if d > 0 else 'rose' if d < 0 else 'stayed flat'} "
                     f"{abs(d)}% under the policy."),
    })
    # unmet
    bu, pu = b["max_people_unmet"], p["max_people_unmet"]
    rows.append({
        "metric": "People with unmet needs", "baseline": bu, "policy": pu,
        "verdict": "better" if pu < bu else ("worse" if pu > bu else "same"),
        "sentence": (f"{pu} people went without needs under the policy, "
                     f"vs {bu} at baseline."),
    })
    # treasury/dividend capacity
    bt, pt = b["treasury"], p["treasury"]
    rows.append({
        "metric": "Surplus pool", "baseline": bt, "policy": pt,
        "verdict": "better" if pt > bt * 105 // 100 else ("worse" if pt < bt * 95 // 100 else "same"),
        "sentence": (f"The surplus pool {'grew' if pt > bt else 'shrank' if pt < bt else 'held steady'} "
                     f"under the policy."),
    })
    # oversight noise
    bf = sum(b["flags"].values())
    pf = sum(p["flags"].values())
    rows.append({
        "metric": "Oversight flags", "baseline": bf, "policy": pf,
        "verdict": "better" if pf < bf * 95 // 100 else ("worse" if pf > bf * 105 // 100 else "same"),
        "sentence": f"Oversight raised {pf} flags vs {bf} at baseline.",
    })
    return rows
