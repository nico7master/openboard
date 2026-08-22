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
    coops: dict[str, dict[str, Any]] = field(default_factory=dict)  # coop_id -> coop dict
    rulesets: list[dict[str, Any]] = field(default_factory=list)  # full version history
    ruleset_version: int = 1  # active at current tick
    # Phase 3 production
    good_cost_baseline: dict[str, int] = field(default_factory=dict)  # good -> credits/unit
    money_minted: int = 0  # credits created by wages (D4)
    money_retired: int = 0  # credits destroyed (surplus retirement arrives Phase 4)
    # Phase 4 markets
    citizen_inventory: dict[str, dict[str, int]] = field(default_factory=dict)  # citizen -> good -> qty
    surplus_pool: int = 0  # society's pool: price-minus-cost deltas flow here
    treasury_in: int = 0  # cumulative treasury inflow (revenue) — accounting only
    listings: dict[str, list[dict[str, Any]]] = field(default_factory=dict)  # good -> listing dicts (tick-scoped)
    bids: list[dict[str, Any]] = field(default_factory=list)  # active bids (tick-scoped)
    # Phase 5 governance
    proposals: dict[str, dict[str, Any]] = field(default_factory=dict)  # proposal_id -> proposal dict
    next_proposal_id: int = 1  # deterministic counter (p1, p2, ...)
    # Phase 6 oversight
    flags: list[dict[str, Any]] = field(default_factory=list)  # public anomaly flags (append-only)
    common_pool: dict[str, int] = field(default_factory=dict)  # society's reclaimed goods (from dissolved hoards)
    last_clearing: dict[str, int] = field(default_factory=dict)  # good -> last auction clearing price (public price signal)
    # Circular flow (2026-08-21 milestone)
    unmet_needs: dict[str, dict[str, int]] = field(default_factory=dict)  # citizen -> good -> ticks unmet
    consumed_totals: dict[str, int] = field(default_factory=dict)  # good -> lifetime units consumed
    dividends_paid: int = 0  # cumulative credits paid as citizen dividends
    services_paid: int = 0  # cumulative credits refunded for essential consumption
    coop_dividends_paid: int = 0  # cumulative patronage dividends coop -> members

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
            "good_cost_baseline": dict(sorted(self.good_cost_baseline.items())),
            "money_minted": self.money_minted,
            "money_retired": self.money_retired,
            "citizen_inventory": {c: dict(sorted(inv.items())) for c, inv in sorted(self.citizen_inventory.items())},
            "surplus_pool": self.surplus_pool,
            "treasury_in": self.treasury_in,
            "listings": {g: list(ls) for g, ls in sorted(self.listings.items())},
            "bids": list(self.bids),
            "proposals": {p: dict(pr) for p, pr in sorted(self.proposals.items())},
            "next_proposal_id": self.next_proposal_id,
            "flags": list(self.flags),
            "common_pool": dict(sorted(self.common_pool.items())),
            "last_clearing": dict(sorted(self.last_clearing.items())),
        }

        # Circular-flow fields: included ONLY when used. Hash-compat: old
        # histories replayed under this engine must hash identically to
        # their recorded hashes, so absent-when-default is load-bearing.
        if self.unmet_needs:
            snap["unmet_needs"] = {
                c: dict(sorted(inv.items())) for c, inv in sorted(self.unmet_needs.items())
            }
        if self.consumed_totals:
            snap["consumed_totals"] = dict(sorted(self.consumed_totals.items()))
        if self.dividends_paid:
            snap["dividends_paid"] = self.dividends_paid
        if self.services_paid:
            snap["services_paid"] = self.services_paid
        if self.coop_dividends_paid:
            snap["coop_dividends_paid"] = self.coop_dividends_paid
        return snap

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
            good_cost_baseline=dict(self.good_cost_baseline),
            money_minted=self.money_minted,
            money_retired=self.money_retired,
            citizen_inventory={c: dict(inv) for c, inv in self.citizen_inventory.items()},
            surplus_pool=self.surplus_pool,
            treasury_in=self.treasury_in,
            listings={g: list(ls) for g, ls in self.listings.items()},
            bids=[dict(b) for b in self.bids],
            proposals={p: _clone_proposal(pr) for p, pr in self.proposals.items()},
            next_proposal_id=self.next_proposal_id,
            flags=[dict(f) for f in self.flags],
            common_pool=dict(self.common_pool),
            last_clearing=dict(self.last_clearing),
            unmet_needs={c: dict(inv) for c, inv in self.unmet_needs.items()},
            consumed_totals=dict(self.consumed_totals),
            dividends_paid=self.dividends_paid,
            services_paid=self.services_paid,
            coop_dividends_paid=self.coop_dividends_paid,
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


def _clone_proposal(pr: dict[str, Any]) -> dict[str, Any]:
    cloned = dict(pr)
    cloned["ballots"] = dict(pr.get("ballots", {}))
    cloned["params"] = dict(pr.get("params", {}))
    return cloned


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
        "labor_pool_hours": c.get("labor_pool_hours", 0),
        "wage_remainder_bp": c.get("wage_remainder_bp", 0),
        "treasury": c.get("treasury", 0),
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

    from .catalog import DEFAULT_BASELINES, GOODS, RECIPES

    if goods is None:
        goods = {gid: dict(g) for gid, g in GOODS.items()}
    if recipes is None:
        recipes = {rid: r.to_dict() for rid, r in RECIPES.items()}
    baselines = {gid: DEFAULT_BASELINES[gid] for gid in goods if gid in DEFAULT_BASELINES}

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
        good_cost_baseline=baselines,
        money_minted=0,
        money_retired=0,
        citizen_inventory={cid: {} for cid in citizens},
        surplus_pool=0,
        treasury_in=0,
        listings={},
        bids=[],
    )
