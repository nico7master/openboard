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

DEFAULT_RULESET_PARAMS: dict[str, Any] = {
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
        "hoard_multiplier": 3,  # essentials held > multiplier x quota = hoard
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

    # unknown extra keys are rejected too: complete documents only
    if set(params.keys()) != set(REQUIRED_PARAMS):
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
