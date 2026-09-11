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
    # Stage 5 · shocks/demographics/research/crisis: rule-gated, absent-when-default
    active_shocks: list[dict[str, Any]] = field(default_factory=list)
    citizens_meta: dict[str, dict[str, Any]] = field(default_factory=dict)  # age, sick, alive
    research: dict[str, Any] = field(default_factory=dict)
    # A1 financial depth: credit union. citizen -> {principal, repaid,
    # due_tick, defaulted}. Present only when the ruleset enables `credit`.
    loans: dict[str, dict[str, Any]] = field(default_factory=dict)
    # A3 delegative democracy: citizen -> delegate. Present only when the
    # ruleset enables `delegation` (replay compat: absent = off).
    delegations: dict[str, str] = field(default_factory=dict)
    crisis: dict[str, Any] = field(default_factory=dict)
    common_pool: dict[str, int] = field(default_factory=dict)  # society's reclaimed goods (from dissolved hoards)
    last_clearing: dict[str, int] = field(default_factory=dict)  # good -> last auction clearing price (public price signal)
    # D18 replacement-rate signal: good -> units sold in the most recent
    # clearing (rebuilt every tick by the market phase). Stock-based
    # produce gates cannot see flow demand: a coop selling 4 coal/tick
    # steadily holds 278 (> target 120) and reads as 'no demand' — so it
    # never produces again (observed: miners rich, machines delivered,
    # debt-free, zero PRODUCE in 50 ticks, ratchet promise missed).
    # Recent sales ARE demand: produce to replace what sold.
    recent_sales: dict[str, int] = field(default_factory=dict)
    # D18 unserved-bid signal: good -> coop bid volume that wanted to buy
    # in the producer-input pass but went unserved (tick-scoped). The
    # replacement-rate loop equates production to sales, and sales can
    # never exceed production — a stable fixed point at ANY level (the
    # trickle equilibrates: gate 23 bread 59/tick, grain 52/tick, no
    # growth). Unserved bids are the GROWTH signal: livestock bid 2,050
    # grain per 100 ticks against 52/tick supply; a farmer producing to
    # replace sales alone never scales. Unserved demand is unmet demand.
    unserved_bids: dict[str, int] = field(default_factory=dict)
    demand_ema: dict[str, float] = field(default_factory=dict)  # D21f: smoothed demand signal (ephemeral)
    # D19 durable capital: coop -> good -> runs of wear accumulated since
    # the last unit of that capital good was consumed. Durable goods
    # (machines, hand_tools) are EQUIPMENT, not ingredients: a coop holds
    # 1 unit and wears it through N runs before replacing.
    capital_wear: dict[str, dict[str, int]] = field(default_factory=dict)
    # Circular flow (2026-08-21 milestone)
    unmet_needs: dict[str, dict[str, int]] = field(default_factory=dict)  # citizen -> good -> ticks unmet
    consumed_totals: dict[str, int] = field(default_factory=dict)  # good -> lifetime units consumed
    dividends_paid: int = 0  # cumulative credits paid as citizen dividends
    services_paid: int = 0  # cumulative credits refunded for essential consumption
    coop_dividends_paid: int = 0  # cumulative patronage dividends coop -> members
    # True-cost accounting: per-coop VWAP per good, integer 1/10,000 cr per
    # unit. Populated only when the active ruleset enables cost_accounting
    # vwap (replay compat: absent param -> stays empty -> hash unchanged).
    coop_vwap: dict[str, dict[str, int]] = field(default_factory=dict)
    # Capital maintenance: cumulative tools/machines consumed per co-op
    # (tracked only while capital_refresh is active).
    capital_burned: dict[str, int] = field(default_factory=dict)
    # Depreciation reserve: capital rent is earmarked here and ONLY capital
    # refresh draws from it. Populated only when capital_rent is active
    # (replay compat: absent param -> 0 -> hash unchanged).
    capital_fund: int = 0
    innovation_pool: int = 0  # Stage 5: research funding pool (surplus -> innovation)
    # Ephemeral per-tick WORK-hours counter (anti multi-tx mint exploit).
    # Cleared at tick boundaries before any snapshot -> state hashes are
    # unaffected; populated only while transactions are being applied.
    worked_hours_tick: dict[str, int] = field(default_factory=dict)
    # WP1.3: learning-by-doing — "citizen|coop_id" -> accumulated skill
    # hours. Omitted from snapshots when empty -> old-world state hashes
    # stay byte-identical (replay compat).
    skills: dict[str, int] = field(default_factory=dict)
    # WP1.4: demand memory — "citizen|good" -> remembered shortage pain
    # (0..1000). Bumped by unmet streaks, decays ~1%/tick. Omitted from
    # snapshots when empty -> old-world state hashes stay byte-identical.
    shortage_memory: dict[str, int] = field(default_factory=dict)
    # L2 scarcity signal (bp of floor premium currently justified by unmet
    # demand); present only while a shortage persists. Rule-gated writes.
    scarcity_signal: dict[str, int] = field(default_factory=dict)

    def snapshot_dict(self) -> dict[str, Any]:
        """Canonical, fully-JSON view of the state."""
        snap = {
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
        if self.skills:
            snap["skills"] = dict(sorted(self.skills.items()))
        if self.shortage_memory:
            snap["shortage_memory"] = dict(sorted(self.shortage_memory.items()))
        if self.scarcity_signal:
            snap["scarcity_signal"] = dict(sorted(self.scarcity_signal.items()))

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
        if self.coop_vwap:
            snap["coop_vwap"] = {c: dict(sorted(g.items())) for c, g in sorted(self.coop_vwap.items())}
        if self.capital_burned:
            snap["capital_burned"] = dict(sorted(self.capital_burned.items()))
        if self.capital_fund:
            snap["capital_fund"] = self.capital_fund
        if self.innovation_pool:
            snap["innovation_pool"] = self.innovation_pool
        if self.crisis:
            snap["crisis"] = dict(self.crisis)
        if self.active_shocks:
            snap["active_shocks"] = [dict(x) for x in self.active_shocks]
        if self.citizens_meta:
            snap["citizens_meta"] = {c: dict(m) for c, m in sorted(self.citizens_meta.items())}
        if self.research:
            snap["research"] = dict(self.research)
        if self.loans:
            snap["loans"] = {c: dict(l) for c, l in sorted(self.loans.items())}
        if self.delegations:
            snap["delegations"] = dict(sorted(self.delegations.items()))
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
            skills=dict(self.skills),
            shortage_memory=dict(self.shortage_memory),
            scarcity_signal=dict(self.scarcity_signal),
            surplus_pool=self.surplus_pool,
            treasury_in=self.treasury_in,
            listings={g: list(ls) for g, ls in self.listings.items()},
            bids=[dict(b) for b in self.bids],
            proposals={p: _clone_proposal(pr) for p, pr in self.proposals.items()},
            next_proposal_id=self.next_proposal_id,
            flags=[dict(f) for f in self.flags],
            active_shocks=[dict(x) for x in self.active_shocks],
            citizens_meta={c: dict(m) for c, m in self.citizens_meta.items()},
            research=dict(self.research),
            crisis=dict(self.crisis),
            common_pool=dict(self.common_pool),
            last_clearing=dict(self.last_clearing),
            unmet_needs={c: dict(inv) for c, inv in self.unmet_needs.items()},
            consumed_totals=dict(self.consumed_totals),
            dividends_paid=self.dividends_paid,
            services_paid=self.services_paid,
            coop_dividends_paid=self.coop_dividends_paid,
            coop_vwap={c: dict(g) for c, g in self.coop_vwap.items()},
            capital_burned=dict(self.capital_burned),
            capital_fund=self.capital_fund,
            innovation_pool=self.innovation_pool,
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
        _default_recipes = True
    else:
        _default_recipes = False
    baselines = {gid: DEFAULT_BASELINES[gid] for gid in goods if gid in DEFAULT_BASELINES}

    if ruleset_params is None:
        from .rules import DEFAULT_RULESET_PARAMS

        params = dict(DEFAULT_RULESET_PARAMS)
        params["triage_overrides"] = {}
    else:
        params = dict(ruleset_params)
        params["triage_overrides"] = dict(ruleset_params.get("triage_overrides", {}))

    if _default_recipes and params.get("extended_catalog"):
        # Stage 3: competition & real capital. Activated only by rule
        # param so pre-Stage-3 worlds replay byte-identically.
        from .catalog import EXTENDED_RECIPES
        recipes.update({rid: r.to_dict() for rid, r in EXTENDED_RECIPES.items()})
        # Capital baselines must reflect MARKET reality (batch-built
        # machines ~160cr), not the legacy one-off book value (1,500).
        # Otherwise the book value leaks into producer cost floors via
        # VWAP fallback and prices coal at 71cr — killing the whole
        # downstream chain (observed collapse by t~200).
        baselines["machines"] = 160
        baselines["hand_tools"] = 25

    genesis_ruleset = RuleSetDoc(
        version=1, params=params, activated_at=0, change_tx_hash="genesis"
    )

    # Fixed supply (money_cap, D15): the FULL money stock exists at day
    # zero. Citizen stakes are stated in credits; all state money is in
    # units (units_per_credit per credit, default 100 -> 0.5 credits is
    # representable). Citizens keep their nominal stakes x units; the
    # remainder of the cap is the Society Pool (the nation's credit fund).
    # All money-denominated baselines scale by units so recipes/prices
    # keep their real values. No minting ever follows: wages and birth
    # stakes are transfers (wage shortfall = coop debt), so
    # sum(balances) + pools == cap forever.
    mc = params.get("money_cap") or {}
    upc = int(mc.get("units_per_credit", 100))
    total_units = int(mc.get("total", 2_100_000_000))
    balances = dict(citizens)
    surplus_pool = 0
    minted_total = 0
    isc = params.get("inequality_seed") or {}
    if mc.get("enabled"):
        if isc.get("enabled"):
            # Real-world unequal start (D16): the top 1% own 50% of ALL
            # money; everyone else splits the remainder; the Society Pool
            # starts EMPTY — society is publicly poor while private wealth
            # concentrates. Policies must earn public funds (wealth tax).
            n = len(balances)
            top_n = max(1, (n * int(isc.get("top_pct_bp", 100))) // 10_000)
            top_share = total_units * int(isc.get("top_share_bp", 5_000)) // 10_000
            sorted_ids = sorted(balances.keys())
            rich = sorted_ids[:top_n]
            rest = sorted_ids[top_n:]
            for cid in rich:
                balances[cid] = top_share // len(rich)
            placed = top_share
            if rest:
                each = (total_units - top_share) // len(rest)
                for cid in rest:
                    balances[cid] = each
                placed += each * len(rest)
            surplus_pool = 0  # society starts publicly poor
            minted_total = 0
            # NOTE: leftover units (rounding dust) stay unplaced; the
            # invariant counts only circulated money.
        else:
            stake_units = 500 * upc
            for cid in balances:
                balances[cid] = 500 * upc
            placed = stake_units * len(balances)
            surplus_pool = max(0, total_units - placed)
            minted_total = 0  # nothing minted post-genesis, ever
        # scale money-denominated baselines and money params to units
        for g in list(baselines):
            baselines[g] = baselines[g] * upc
        if params.get("wage_multiplier_bp") is not None:
            pass  # bp-based: scales with hours; wage credits x upc handled
        for k in ("surplus_reserve_cap", "energy_price", "transfer_limit"):
            if isinstance(params.get(k), int):
                params[k] = params[k] * upc
        if isinstance(params.get("wealth_tax"), dict):
            wt = params["wealth_tax"]
            if isinstance(wt.get("threshold"), int):
                wt["threshold"] = wt["threshold"] * upc

    return WorldState(
        tick=0,
        balances=balances,
        applied=[],
        labor_hours={cid: 0 for cid in citizens},
        goods=goods,
        recipes=recipes,
        coops={},
        rulesets=[genesis_ruleset.to_dict()],
        ruleset_version=1,
        good_cost_baseline=baselines,
        money_minted=minted_total,
        money_retired=0,
        citizen_inventory={cid: {} for cid in citizens},
        surplus_pool=surplus_pool,
        treasury_in=0,
        listings={},
        bids=[],
    )
