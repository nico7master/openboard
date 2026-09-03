"""Rules-as-data (D7): versioned rule-set documents.

The engine is a rule-set interpreter. Rule-sets are complete documents
(git-commit style snapshots) recorded on the ledger; every transaction
executes under the version active at its tick — replay applies exactly
those versions (version pinning).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import Reason

REQUIRED_PARAMS = (
    "transfer_limit",
    "max_coop_members",
    "min_coop_members",
    "triage_overrides",
    "wage_multiplier_bp",
    "energy_price",
    "max_work_hours_per_tick",
    "bootstrap_endowment",
    "essential_need_quota",
    "surplus_reserve_cap",
    "governance",
    "constitution_phase",
    "oversight",
)

VALID_TRIAGE = ("market", "essential", "emergency")

# Circular-flow milestone params (needs & surplus spending). OPTIONAL on
# purpose: rules are hash-covered state — old histories replayed under the
# new engine must resolve identical rulesets. Absent key = feature disabled;
# present key = strictly validated below.
OPTIONAL_PARAMS = ("needs", "surplus_spending", "coop_distribution", "capital_rent", "cost_accounting", "capital_refresh", "wealth_tax", "labor_pool_cap", "max_work_hours_cumulative", "extended_catalog", "capital_backstop", "needs_cycle", "fair_clearing", "producer_input_priority", "credit", "delegation")

DEFAULT_RULESET_PARAMS: dict[str, Any] = {
    "fair_clearing": True,  # D14 L5: need-rotation on by default (v0.02)
    "transfer_limit": 0,  # 0 = unlimited
    "max_coop_members": 12,
    "min_coop_members": 2,
    "triage_overrides": {},
    "wage_multiplier_bp": 10_000,  # basis points: 10000 = 1.0x
    "energy_price": 2,  # credits per kwh for cost accounting
    "max_work_hours_per_tick": 8,
    "bootstrap_endowment": {
        "water": 200,
        "electricity": 500,
        "hand_tools": 5,
        "machines": 1,
    },
    "essential_need_quota": {
        "grain": 10,
        "vegetables": 8,
        "fruit": 5,
        "fish": 4,
        "meat": 2,
        "eggs": 6,
        "milk": 6,
        "flour": 5,
        "bread": 4,
        "canned_food": 3,
        "cheese": 1,
        "meals": 3,
        "housing": 1,
        "electricity": 50,
        "heating_fuel": 20,
        "water": 10,
        "healthcare": 2,
        # Stage 4: every need-good must be purchasable via BUY_ESSENTIAL —
        # a need-good missing here is silently unbought (observed:
        # transport/books/clothing listed but zero citizen purchases)
        "transport": 4, "clothing": 2, "education": 1,
        "childcare": 2, "books": 2, "furniture": 1,
        "household_goods": 2, "maintenance": 2, "medicine": 1,
    },
    "surplus_reserve_cap": 5_000,
    "governance": {
        "enabled": False,  # bootstrap: RULE_CHANGE is the instant path (D10)
        "vote_window_ticks": 3,  # votes accepted for window_ticks after propose
        "quorum_bp": 5_000,  # 50% of citizens must cast
        "trial_period_ticks": 10,  # rollback is easy inside this window
    },
    "constitution_phase": "bootstrap",  # "hardened" -> 2/3 majority required
    "oversight": {
        "hoard_multiplier": 8,  # essentials held > multiplier x quota = hoard (2026-09-01 recalibration: multiplier 3 flagged 166/166 citizens — a signal firing on 100% of the population carries zero information)
        "market_power_share_bp": 7_000,  # >70% listed share of one good
        "free_rider_min_hours": 5,  # lifetime labor below this = free rider
        "council_members": [],  # elected council (votable param, D9)
    },
}


@dataclass(frozen=True)
class RuleSetDoc:
    """One complete rule-set version."""

    version: int
    params: dict[str, Any]
    activated_at: int  # first tick this version is active
    change_tx_hash: str  # provenance: RULE_CHANGE transaction hash ("genesis" for v1)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "params": self.params,
            "activated_at": self.activated_at,
            "change_tx_hash": self.change_tx_hash,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "RuleSetDoc":
        return cls(
            version=d["version"],
            params=d["params"],
            activated_at=d["activated_at"],
            change_tx_hash=d["change_tx_hash"],
        )

    @staticmethod
    def genesis() -> "RuleSetDoc":
        return RuleSetDoc(version=1, params=dict(DEFAULT_RULESET_PARAMS), activated_at=0, change_tx_hash="genesis")


def validate_params(params: Any, known_goods: set[str] | None = None) -> Reason | None:
    """Schema validation for rule params. None = valid."""
    if not isinstance(params, dict):
        return Reason.INVALID_RULESET

    for key in REQUIRED_PARAMS:
        if key not in params:
            return Reason.INVALID_RULESET

    for key in ("transfer_limit", "max_coop_members", "min_coop_members"):
        v = params[key]
        if isinstance(v, bool) or not isinstance(v, int) or v < 0:
            return Reason.INVALID_RULESET

    for key in ("wage_multiplier_bp", "energy_price", "max_work_hours_per_tick", "surplus_reserve_cap"):
        v = params[key]
        if isinstance(v, bool) or not isinstance(v, int) or v < 0:
            return Reason.INVALID_RULESET

    if params["min_coop_members"] < 1:
        return Reason.INVALID_RULESET
    if params["max_work_hours_per_tick"] < 1:
        return Reason.INVALID_RULESET

    endowment = params["bootstrap_endowment"]
    if not isinstance(endowment, dict):
        return Reason.INVALID_RULESET
    for good, qty in endowment.items():
        if not isinstance(good, str) or isinstance(qty, bool) or not isinstance(qty, int) or qty <= 0:
            return Reason.INVALID_RULESET
        if known_goods is not None and good not in known_goods:
            return Reason.INVALID_RULESET

    quota = params["essential_need_quota"]
    if not isinstance(quota, dict):
        return Reason.INVALID_RULESET
    for good, qty in quota.items():
        if not isinstance(good, str) or isinstance(qty, bool) or not isinstance(qty, int) or qty <= 0:
            return Reason.INVALID_RULESET
        if known_goods is not None and good not in known_goods:
            return Reason.INVALID_RULESET

    overrides = params["triage_overrides"]
    if not isinstance(overrides, dict):
        return Reason.INVALID_RULESET
    for good, triage in overrides.items():
        if not isinstance(good, str) or triage not in VALID_TRIAGE:
            return Reason.INVALID_RULESET
        if known_goods is not None and good not in known_goods:
            return Reason.INVALID_RULESET

    if params["constitution_phase"] not in ("bootstrap", "hardened"):
        return Reason.INVALID_RULESET

    gov = params["governance"]
    if not isinstance(gov, dict) or set(gov.keys()) != {"enabled", "vote_window_ticks", "quorum_bp", "trial_period_ticks"}:
        return Reason.INVALID_RULESET
    if not isinstance(gov["enabled"], bool):
        return Reason.INVALID_RULESET
    for key in ("vote_window_ticks", "trial_period_ticks"):
        v = gov[key]
        if isinstance(v, bool) or not isinstance(v, int) or v < 1:
            return Reason.INVALID_RULESET
    q = gov["quorum_bp"]
    if isinstance(q, bool) or not isinstance(q, int) or q < 0 or q > 10_000:
        return Reason.INVALID_RULESET

    ov = params["oversight"]
    if not isinstance(ov, dict) or set(ov.keys()) != {"hoard_multiplier", "market_power_share_bp", "free_rider_min_hours", "council_members"}:
        return Reason.INVALID_RULESET
    for key in ("hoard_multiplier", "market_power_share_bp", "free_rider_min_hours"):
        v = ov[key]
        if isinstance(v, bool) or not isinstance(v, int) or v < 0:
            return Reason.INVALID_RULESET
    council = ov["council_members"]
    if not isinstance(council, list) or not all(isinstance(m, str) for m in council):
        return Reason.INVALID_RULESET

    # Circular-flow params: optional; validated strictly when present.
    # NOT in DEFAULT_RULESET_PARAMS — rulesets are hash-covered state, so
    # changing defaults would break replay of every existing history.
    # New runs opt in via explicit ruleset_params (dashboard does).
    if "needs" in params:
        needs = params["needs"]
        if not isinstance(needs, dict):
            return Reason.INVALID_RULESET
        for good, quota in needs.items():
            if not isinstance(good, str) or isinstance(quota, bool) or not isinstance(quota, int) or quota < 0 or quota > 1000:
                return Reason.INVALID_RULESET
            if known_goods is not None and good not in known_goods:
                return Reason.INVALID_RULESET

    if "needs_cycle" in params:
        nc = params["needs_cycle"]
        if not isinstance(nc, dict):
            return Reason.INVALID_RULESET
        for good, n in nc.items():
            if not isinstance(good, str) or isinstance(n, bool) or not isinstance(n, int) or n < 1 or n > 10_000:
                return Reason.INVALID_RULESET
            if known_goods is not None and good not in known_goods:
                return Reason.INVALID_RULESET

    if "fair_clearing" in params:
        if not isinstance(params["fair_clearing"], bool):
            return Reason.INVALID_RULESET

    if "surplus_spending" in params:
        ss = params["surplus_spending"]
        required_ss = {
            "dividend_share_bp", "services_share_bp", "min_pool_buffer", "max_dividend_per_tick"
        }
        # Optional per-capita cap (C2): present = scales with population;
        # absent = legacy TOTAL cap semantics (old worlds unchanged).
        optional_ss = {"max_dividend_per_citizen_tick"}
        if not isinstance(ss, dict) or not required_ss <= set(ss.keys()) or not set(ss.keys()) <= required_ss | optional_ss:
            return Reason.INVALID_RULESET
        for key in ("dividend_share_bp", "services_share_bp"):
            v = ss[key]
            if isinstance(v, bool) or not isinstance(v, int) or v < 0 or v > 10_000:
                return Reason.INVALID_RULESET
        for key in tuple(required_ss) + tuple(optional_ss):
            if key in ss:
                v = ss[key]
                if isinstance(v, bool) or not isinstance(v, int) or v < 0:
                    return Reason.INVALID_RULESET

    if "coop_distribution" in params:
        cd = params["coop_distribution"]
        if not isinstance(cd, dict) or set(cd.keys()) != {"buffer", "share_bp"}:
            return Reason.INVALID_RULESET
        v = cd["buffer"]
        if isinstance(v, bool) or not isinstance(v, int) or v < 0:
            return Reason.INVALID_RULESET
        v = cd["share_bp"]
        if isinstance(v, bool) or not isinstance(v, int) or v < 0 or v > 10_000:
            return Reason.INVALID_RULESET

    if "capital_rent" in params:
        cr = params["capital_rent"]
        if not isinstance(cr, dict) or set(cr.keys()) != {"per_machine_used", "per_tool_used"}:
            return Reason.INVALID_RULESET
        for key in ("per_machine_used", "per_tool_used"):
            v = cr[key]
            if isinstance(v, bool) or not isinstance(v, int) or v < 0 or v > 5_000:
                return Reason.INVALID_RULESET

    if "extended_catalog" in params:
        if not isinstance(params["extended_catalog"], bool):
            return Reason.INVALID_RULESET

    if "producer_input_priority" in params:
        pip = params["producer_input_priority"]
        ok = (
            pip is None
            or (isinstance(pip, dict)
                and set(pip.keys()) <= {"enabled", "share_cap_bp"}
                and isinstance(pip.get("enabled", False), bool)
                and (isinstance(pip.get("share_cap_bp", 5_000), bool) is False
                     and isinstance(pip.get("share_cap_bp", 5_000), int)
                     and 0 <= pip.get("share_cap_bp", 5_000) <= 10_000))
        )
        if not ok:
            return Reason.INVALID_RULESET

    if "capital_backstop" in params:
        cb = params["capital_backstop"]
        allowed = {"interval_ticks", "input_advance", "founding_equipment"}
        if not isinstance(cb, dict) or not set(cb.keys()) <= allowed:
            return Reason.INVALID_RULESET
        if "interval_ticks" not in cb:
            return Reason.INVALID_RULESET
        iv = cb["interval_ticks"]
        if isinstance(iv, bool) or not isinstance(iv, int) or iv <= 0 or iv > 1_000:
            return Reason.INVALID_RULESET
        ia = cb.get("input_advance")
        if ia is not None and (not isinstance(ia, dict) or set(ia.keys()) != {"max_per_coop"}):
            return Reason.INVALID_RULESET
        if ia is not None:
            mx = ia["max_per_coop"]
            if isinstance(mx, bool) or not isinstance(mx, int) or mx < 0:
                return Reason.INVALID_RULESET
        fe = cb.get("founding_equipment")
        if fe is not None and not isinstance(fe, bool):
            return Reason.INVALID_RULESET

    if "cost_accounting" in params:
        ca = params["cost_accounting"]
        if not isinstance(ca, dict) or set(ca.keys()) != {"method"} or ca["method"] != "vwap":
            return Reason.INVALID_RULESET

    if "capital_refresh" in params:
        crr = params["capital_refresh"]
        if not isinstance(crr, dict) or set(crr.keys()) != {"interval_ticks", "hand_tools", "machines"}:
            return Reason.INVALID_RULESET
        for key in ("interval_ticks", "hand_tools", "machines"):
            v = crr[key]
            if isinstance(v, bool) or not isinstance(v, int) or v < 0 or v > 10_000:
                return Reason.INVALID_RULESET
        if crr["interval_ticks"] < 1:
            return Reason.INVALID_RULESET

    if "wealth_tax" in params:
        wt = params["wealth_tax"]
        if not isinstance(wt, dict) or set(wt.keys()) != {"threshold", "rate_bp"}:
            return Reason.INVALID_RULESET
        for key in ("threshold", "rate_bp"):
            v = wt[key]
            if isinstance(v, bool) or not isinstance(v, int) or v < 0 or v > 1_000_000:
                return Reason.INVALID_RULESET
        if wt["rate_bp"] > 10_000:
            return Reason.INVALID_RULESET

    if "max_work_hours_cumulative" in params:
        v = params["max_work_hours_cumulative"]
        if isinstance(v, bool) or not isinstance(v, int) or v < 1 or v > 168:
            return Reason.INVALID_RULESET

    if "labor_pool_cap" in params:
        v = params["labor_pool_cap"]
        if isinstance(v, bool) or not isinstance(v, int) or v < 0 or v > 1_000_000:
            return Reason.INVALID_RULESET

    # unknown extra keys are rejected too: complete documents only
    if set(params.keys()) - set(REQUIRED_PARAMS) - set(OPTIONAL_PARAMS):
        return Reason.INVALID_RULESET

    return None


def active_version(rulesets: list[RuleSetDoc], tick: int) -> int:
    """Version active at `tick`: highest activated_at <= tick; ties -> higher version."""
    best: RuleSetDoc | None = None
    for rs in rulesets:
        if rs.activated_at <= tick:
            if best is None or rs.activated_at > best.activated_at or (
                rs.activated_at == best.activated_at and rs.version > best.version
            ):
                best = rs
    if best is None:
        raise ValueError(f"no ruleset active at tick {tick}")
    return best.version


def active_ruleset(rulesets: list[RuleSetDoc], tick: int) -> RuleSetDoc:
    version = active_version(rulesets, tick)
    for rs in rulesets:
        if rs.version == version:
            return rs
    raise ValueError(f"ruleset version {version} not found")
