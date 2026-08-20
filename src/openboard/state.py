"""World state and canonical state hashing.

Spec §4.1: after each tick the engine commits hash(canonical(state)) —
external verifiers compare state hashes without trusting the operator.

Phase 2: state grows economy entities — labor hours, goods catalog,
recipes, cooperatives, and the full rule-set version history (D7).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .ledger import canonical_json, sha256_hex
from .rules import RuleSetDoc


@dataclass
class WorldState:
    """The full world state. Grows per phase; hashing contract is stable."""

    tick: int = 0
    balances: dict[str, int] = field(default_factory=dict)
    applied: list[dict[str, Any]] = field(default_factory=list)
    # Phase 2 entities
    labor_hours: dict[str, int] = field(default_factory=dict)  # citizen -> lifetime hours
    goods: dict[str, dict[str, str]] = field(default_factory=dict)  # good_id -> {category, triage, unit}
    recipes: dict[str, dict[str, Any]] = field(default_factory=dict)  # recipe_id -> recipe dict
    coops: dict[str, dict[str, Any]] = field(default_factory=dict)  # coop_id -> {name, members, founded_tick, inventory}
    rulesets: list[dict[str, Any]] = field(default_factory=list)  # full version history
    ruleset_version: int = 1  # active at current tick

    def snapshot_dict(self) -> dict[str, Any]:
        """Canonical, fully-JSON view of the state."""
        return {
            "tick": self.tick,
            "balances": dict(sorted(self.balances.items())),
            "applied": list(self.applied),
            "labor_hours": dict(sorted(self.labor_hours.items())),
            "goods": {k: self.goods[k] for k in sorted(self.goods.keys())},
            "recipes": {k: self.recipes[k] for k in sorted(self.recipes.keys())},
            "coops": {k: self.coops[k] for k in sorted(self.coops.keys())},
            "rulesets": list(self.rulesets),
            "ruleset_version": self.ruleset_version,
        }

    def state_hash(self) -> str:
        return sha256_hex(canonical_json(self.snapshot_dict()))

    def clone(self) -> "WorldState":
        return WorldState(
            tick=self.tick,
            balances=dict(self.balances),
            applied=[dict(entry) for entry in self.applied],
            labor_hours=dict(self.labor_hours),
            goods={k: dict(v) for k, v in self.goods.items()},
            recipes={k: _clone_recipe(v) for k, v in self.recipes.items()},
            coops={k: _clone_coop(v) for k, v in self.coops.items()},
            rulesets=[dict(rs) for rs in self.rulesets],
            ruleset_version=self.ruleset_version,
        )

    def active_ruleset_params(self) -> dict[str, Any]:
        for rs in self.rulesets:
            if rs["version"] == self.ruleset_version:
                return rs["params"]
        raise ValueError(f"ruleset version {self.ruleset_version} not found in state")

    def effective_triage(self, good_id: str) -> str:
        """D8: rule overrides > catalog default."""
        overrides = self.active_ruleset_params().get("triage_overrides", {})
        return overrides.get(good_id, self.goods[good_id]["triage"])


def _clone_recipe(r: dict[str, Any]) -> dict[str, Any]:
    return {
        "recipe_id": r["recipe_id"],
        "inputs": dict(r["inputs"]),
        "labor_hours": r["labor_hours"],
        "energy": r["energy"],
        "outputs": dict(r["outputs"]),
    }


def _clone_coop(c: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": c["name"],
        "members": list(c["members"]),
        "founded_tick": c["founded_tick"],
        "inventory": dict(c["inventory"]),
    }


def genesis_state(
    citizens: dict[str, int],
    goods: dict[str, dict[str, str]] | None = None,
    recipes: dict[str, dict[str, Any]] | None = None,
    ruleset_params: dict[str, Any] | None = None,
) -> WorldState:
    """Genesis: citizen balances, goods catalog, recipes, rule-set v1.

    Phase-1 compatible: goods/recipes/ruleset_params default to the starter
    catalog and default rule-set when omitted.
    """
    if not all(isinstance(v, int) and not isinstance(v, bool) for v in citizens.values()):
        raise ValueError("genesis balances must be integers")

    from .catalog import GOODS, RECIPES

    if goods is None:
        goods = {gid: dict(g) for gid, g in GOODS.items()}
    if recipes is None:
        recipes = {rid: r.to_dict() for rid, r in RECIPES.items()}

    if ruleset_params is None:
        from .rules import DEFAULT_RULESET_PARAMS

        params = dict(DEFAULT_RULESET_PARAMS)
        params["triage_overrides"] = {}
    else:
        params = dict(ruleset_params)
        params["triage_overrides"] = dict(ruleset_params.get("triage_overrides", {}))

    genesis_ruleset = RuleSetDoc(
        version=1, params=params, activated_at=0, change_tx_hash="genesis"
    )

    return WorldState(
        tick=0,
        balances=dict(citizens),
        applied=[],
        labor_hours={cid: 0 for cid in citizens},
        goods=goods,
        recipes=recipes,
        coops={},
        rulesets=[genesis_ruleset.to_dict()],
        ruleset_version=1,
    )
