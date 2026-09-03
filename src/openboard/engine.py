"""Deterministic tick engine (Phases 1–2).

One tick = one action batch, settled in fixed deterministic order —
sorted by (sender, action, content hash, ruleset version). No wall-clock,
no randomness. Rejections are ledger records, never crashes.

Phase 2: the engine is a rule-set interpreter — the active rule version is
resolved for the tick BEFORE processing; every transaction must be pinned
to that version (RULESET_MISMATCH otherwise). RULE_CHANGE transactions
activate new versions at strictly future ticks.
"""

from __future__ import annotations

import random
from typing import Any

from .errors import Reason
from .ledger import Ledger, Transaction
from .rules import RuleSetDoc, validate_params
from .state import WorldState

SUPPORTED_ACTIONS = frozenset({"TRANSFER", "RULE_CHANGE", "FOUND_COOP", "JOIN_COOP", "LEAVE_COOP", "WORK", "PRODUCE", "LIST_GOOD", "BID", "BID_FOR_COOP", "BUY_ESSENTIAL", "PROPOSE", "VOTE", "ROLLBACK", "INTERVENE", "CRISIS_VOTE", "LOAN", "REPAY", "DELEGATE"})


def _is_int(v: Any) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


# ---------------------------------------------------------------- TRANSFER


def _validate_transfer(state: WorldState, tx: Transaction, params: dict[str, Any]) -> Reason | None:
    payload: dict[str, Any] = tx.payload

    if tx.sender not in state.balances:
        return Reason.UNKNOWN_SENDER

    if not isinstance(payload, dict) or set(payload.keys()) != {"to", "amount"}:
        return Reason.INVALID_PAYLOAD

    amount = payload.get("amount")
    to = payload.get("to")

    if not _is_int(amount):
        return Reason.NON_INTEGER_AMOUNT
    if to not in state.balances:
        return Reason.UNKNOWN_CITIZEN
    if amount <= 0:
        return Reason.RULE_VIOLATION

    limit = params.get("transfer_limit", 0)
    if limit > 0 and amount > limit:
        return Reason.RULE_VIOLATION  # above transfer limit — votable rule (D5/D7)

    if state.balances[tx.sender] < amount:
        return Reason.INSUFFICIENT_CREDITS
    return None


def _apply_transfer(state: WorldState, tx: Transaction) -> dict[str, Any]:
    amount = tx.payload["amount"]
    to = tx.payload["to"]
    state.balances[tx.sender] -= amount
    state.balances[to] += amount
    return {
        "tick": tx.tick,
        "sender": tx.sender,
        "action": "TRANSFER",
        "to": to,
        "amount": amount,
    }


# ---------------------------------------------------------------- CREDIT
# A1 financial depth: the credit union. Society lends from the surplus pool
# (society's savings = the credit fund). Loans MOVE credits, never mint them
# (same invariant class as dividends). Gated by the optional `credit` rule
# param; absent key = feature off = old worlds replay byte-identically.


def _credit_params(params: dict[str, Any]) -> dict[str, Any] | None:
    cp = params.get("credit")
    if not isinstance(cp, dict) or not cp.get("enabled"):
        return None
    return cp


def _loan_owed(loan: dict[str, Any]) -> int:
    principal_left = loan["principal"] - loan.get("repaid_principal", 0)
    fee_total = loan["principal"] * loan.get("fee_bp", 0) // 10_000
    fee_left = fee_total - loan.get("repaid_fees", 0)
    return principal_left + max(0, fee_left)


def _validate_loan(state: WorldState, tx: Transaction, params: dict[str, Any]) -> Reason | None:
    cp = _credit_params(params)
    if cp is None:
        return Reason.CREDIT_DISABLED
    if tx.sender not in state.balances:
        return Reason.UNKNOWN_SENDER
    payload: dict[str, Any] = tx.payload
    if not isinstance(payload, dict) or set(payload.keys()) != {"amount"}:
        return Reason.INVALID_PAYLOAD
    amount = payload.get("amount")
    if not _is_int(amount) or amount <= 0:
        return Reason.RULE_VIOLATION
    existing = state.loans.get(tx.sender)
    if existing is not None and not existing.get("defaulted"):
        return Reason.LOAN_ACTIVE
    cap = cp.get("max_per_citizen", 0)
    if not _is_int(cap) or cap <= 0 or amount > cap:
        return Reason.RULE_VIOLATION
    if state.surplus_pool < amount:
        return Reason.INSUFFICIENT_CREDITS
    return None


def _apply_loan(state: WorldState, tx: Transaction, params: dict[str, Any]) -> dict[str, Any]:
    amount = tx.payload["amount"]
    cp = params["credit"]
    due = tx.tick + int(cp.get("term_ticks", 100))
    state.surplus_pool -= amount
    state.balances[tx.sender] += amount
    state.loans[tx.sender] = {
        "principal": amount,
        "repaid_principal": 0,
        "repaid_fees": 0,
        "opened_tick": tx.tick,
        "due_tick": due,
        "fee_bp": int(cp.get("fee_bp", 0)),
        "defaulted": False,
    }
    return {
        "tick": tx.tick,
        "action": "LOAN",
        "citizen": tx.sender,
        "principal": amount,
        "due_tick": due,
        "pool_after": state.surplus_pool,
    }


def _validate_delegate(state: WorldState, tx: Transaction, params: dict[str, Any]) -> Reason | None:
    if not _delegation_enabled(params):
        return Reason.RULE_VIOLATION
    if tx.sender not in state.balances:
        return Reason.UNKNOWN_SENDER
    if not isinstance(tx.payload, dict) or set(tx.payload.keys()) != {"to"}:
        return Reason.INVALID_PAYLOAD
    to = tx.payload["to"]
    if to is not None:
        if not isinstance(to, str) or to not in state.balances:
            return Reason.UNKNOWN_CITIZEN
        if to == tx.sender:
            return Reason.RULE_VIOLATION
    return None


def _validate_repay(state: WorldState, tx: Transaction, params: dict[str, Any]) -> Reason | None:
    if tx.sender not in state.balances:
        return Reason.UNKNOWN_SENDER
    if not isinstance(tx.payload, dict) or set(tx.payload.keys()) != {"amount"}:
        return Reason.INVALID_PAYLOAD
    if not _is_int(tx.payload.get("amount")) or tx.payload["amount"] <= 0:
        return Reason.RULE_VIOLATION
    loan = state.loans.get(tx.sender)
    if loan is None or loan.get("defaulted"):
        return Reason.NO_ACTIVE_LOAN
    if tx.payload["amount"] > _loan_owed(loan):
        return Reason.RULE_VIOLATION
    if state.balances[tx.sender] < tx.payload["amount"]:
        return Reason.INSUFFICIENT_CREDITS
    return None


def _apply_repay(state: WorldState, tx: Transaction) -> dict[str, Any]:
    loan = state.loans[tx.sender]
    pay = min(tx.payload["amount"], _loan_owed(loan))
    principal_left = loan["principal"] - loan.get("repaid_principal", 0)
    principal_pay = min(pay, principal_left)
    fee_pay = pay - principal_pay
    state.balances[tx.sender] -= pay
    state.surplus_pool += pay
    loan["repaid_principal"] = loan.get("repaid_principal", 0) + principal_pay
    loan["repaid_fees"] = loan.get("repaid_fees", 0) + fee_pay
    closed = loan.get("repaid_principal", 0) >= loan["principal"]
    entry = {
        "tick": tx.tick,
        "action": "REPAY",
        "citizen": tx.sender,
        "amount": pay,
        "principal_part": principal_pay,
        "fee_part": fee_pay,
        "closed": closed,
        "pool_after": state.surplus_pool,
    }
    if closed:
        del state.loans[tx.sender]
        entry["status"] = "repaid"
    return entry


def credit_phase(state: WorldState, tick: int, params: dict[str, Any]) -> list[dict[str, Any]]:
    """Mark overdue loans defaulted (socialized risk, ledger-visible)."""
    cp = _credit_params(params)
    if cp is None:
        return []
    events: list[dict[str, Any]] = []
    for citizen in sorted(state.loans.keys()):
        loan = state.loans[citizen]
        if not loan.get("defaulted") and tick > loan["due_tick"]:
            loan["defaulted"] = True
            events.append({
                "tick": tick,
                "action": "LOAN_DEFAULT",
                "citizen": citizen,
                "principal": loan["principal"],
                "owed": _loan_owed(loan),
            })
            state.flags.append({
                "tick": tick,
                "kind": "LOAN_DEFAULT",
                "target": citizen,
                "citizen": citizen,
                "principal": loan["principal"],
            })
    return events



# ---------------------------------------------------------------- DELEGATION
# A3 delegative democracy: a citizen may hand their vote to another citizen
# (revocable anytime). Uninformed citizens get expert-quality default votes;
# the informed can steer; direct votes always override the delegate.
# Gated by the optional `delegation` rule param; absent = off = old worlds
# replay byte-identically.


def _delegation_enabled(params: dict[str, Any]) -> bool:
    d = params.get("delegation")
    return isinstance(d, dict) and bool(d.get("enabled"))


def resolve_delegation(state: WorldState, citizen: str, max_hops: int = 16) -> str | None:
    """Resolve a delegation chain transitively; broken chains or cycles
    contribute nothing (the abstention stands)."""
    seen = {citizen}
    current = citizen
    for _ in range(max_hops):
        nxt = state.delegations.get(current)
        if nxt is None or nxt not in state.balances:
            return None
        if nxt in seen:
            return None  # cycle: no vote
        seen.add(nxt)
        current = nxt
    return None  # chain too long: treat as broken


def _validate_delegate(state: WorldState, tx: Transaction, params: dict[str, Any]) -> Reason | None:
    if not _delegation_enabled(params):
        return Reason.CREDIT_DISABLED  # reuse: feature-disabled family
    payload: dict[str, Any] = tx.payload
    if not isinstance(payload, dict) or set(payload.keys()) != {"to"}:
        return Reason.INVALID_PAYLOAD
    to = payload.get("to")
    if to is not None and (not isinstance(to, str) or to not in state.balances):
        return Reason.UNKNOWN_CITIZEN
    if to == tx.sender:
        return Reason.RULE_VIOLATION  # no self-delegation
    return None


def _apply_delegate(state: WorldState, tx: Transaction) -> dict[str, Any]:
    to = tx.payload["to"]
    entry: dict[str, Any] = {
        "tick": tx.tick,
        "action": "DELEGATE",
        "citizen": tx.sender,
        "to": to,
    }
    if to is None:
        state.delegations.pop(tx.sender, None)
        entry["status"] = "revoked"
    else:
        state.delegations[tx.sender] = to
    return entry


def expand_ballots(state: WorldState, ballots: dict[str, str]) -> dict[str, str]:
    """Expand raw ballots with delegated votes. A citizen who did not vote
    directly contributes their delegate's (resolved) choice. Direct votes
    always win over delegation. Cycle-safe, deterministic."""
    expanded = dict(ballots)
    for citizen in sorted(state.balances.keys()):
        if citizen in ballots:
            continue  # direct vote stands
        choice = None
        current = citizen
        seen = {citizen}
        for _ in range(16):
            nxt = state.delegations.get(current)
            if nxt is None or nxt in seen or nxt not in state.balances:
                break
            seen.add(nxt)
            if nxt in ballots:
                choice = ballots[nxt]
                break
            current = nxt
        if choice is not None:
            expanded[citizen] = choice
    return expanded



# ------------------------------------------------------------- RULE_CHANGE


def _validate_rule_change(state: WorldState, tx: Transaction, params: dict[str, Any]) -> Reason | None:
    payload = tx.payload

    if tx.sender not in state.balances:
        return Reason.UNKNOWN_SENDER

    # D10 bootstrap story: once governance is enabled, the instant path is
    # locked — all rule change flows through proposals and votes.
    if _gov_params(params)["enabled"]:
        return Reason.GOVERNANCE_LOCKED

    if not isinstance(payload, dict) or set(payload.keys()) != {"params", "activation_tick"}:
        return Reason.INVALID_PAYLOAD

    activation = payload.get("activation_tick")
    if not _is_int(activation):
        return Reason.INVALID_PAYLOAD
    if activation <= tx.tick:
        return Reason.ACTIVATION_IN_PAST  # strictly future only — no retroactivity

    reason = validate_params(payload.get("params"), known_goods=set(state.goods.keys()))
    if reason is not None:
        return reason

    return None


def _apply_rule_change(state: WorldState, tx: Transaction, ledger: Ledger) -> dict[str, Any]:
    params = tx.payload["params"]
    activation = tx.payload["activation_tick"]
    next_version = max(rs["version"] for rs in state.rulesets) + 1

    doc = RuleSetDoc(
        version=next_version,
        params=params,
        activated_at=activation,
        change_tx_hash=tx.content_hash(),
    )
    state.rulesets.append(doc.to_dict())

    return {
        "tick": tx.tick,
        "sender": tx.sender,
        "action": "RULE_CHANGE",
        "new_version": next_version,
        "activated_at": activation,
        "change_tx_hash": tx.content_hash(),
    }


# --------------------------------------------------------------- FOUND_COOP


def _member_of(state: WorldState, citizen: str) -> str | None:
    for coop_id, coop in state.coops.items():
        if citizen in coop["members"]:
            return coop_id
    return None


def _validate_found_coop(state: WorldState, tx: Transaction, params: dict[str, Any]) -> Reason | None:
    payload = tx.payload

    if tx.sender not in state.balances:
        return Reason.UNKNOWN_SENDER

    # Optional declared trade: the coop states which recipe it intends
    # to run (used by the founding equipment grant). Absent = legacy.
    allowed_keys = {"coop_id", "name", "members"} | {"recipe_id"}
    if not isinstance(payload, dict) or not set(payload.keys()) <= allowed_keys or not {"coop_id", "name", "members"} <= set(payload.keys()):
        return Reason.INVALID_PAYLOAD

    coop_id = payload.get("coop_id")
    members = payload.get("members")

    if not isinstance(coop_id, str) or not coop_id:
        return Reason.INVALID_PAYLOAD
    if not isinstance(members, list) or not all(isinstance(m, str) for m in members):
        return Reason.INVALID_PAYLOAD
    if tx.sender not in members:
        return Reason.NOT_A_MEMBER
    if len(set(members)) != len(members):
        return Reason.INVALID_PAYLOAD

    for m in members:
        if m not in state.balances:
            return Reason.UNKNOWN_CITIZEN
        if _member_of(state, m) is not None:
            return Reason.ALREADY_IN_COOP

    if coop_id in state.coops:
        return Reason.COOP_EXISTS

    if len(members) < params.get("min_coop_members", 2):
        return Reason.COOP_TOO_SMALL
    if len(members) > params.get("max_coop_members", 12):
        return Reason.COOP_FULL

    return None


def _apply_found_coop(state: WorldState, tx: Transaction, params: dict[str, Any]) -> dict[str, Any]:
    payload = tx.payload
    endowment = params.get("bootstrap_endowment", {})
    state.coops[payload["coop_id"]] = {
        "name": payload["name"],
        "members": list(payload["members"]),
        "founded_tick": tx.tick,
        "inventory": {g: q for g, q in endowment.items()},  # socially granted means of production
        "labor_pool_hours": 0,
        "wage_remainder_bp": 0,
        **({"recipe_intent": payload["recipe_id"]} if payload.get("recipe_id") else {}),
    }
    return {
        "tick": tx.tick,
        "sender": tx.sender,
        "action": "FOUND_COOP",
        "coop_id": payload["coop_id"],
        "members": list(payload["members"]),
        "endowment": dict(endowment),
    }


# ---------------------------------------------------------------- JOIN_COOP


def _validate_join_coop(state: WorldState, tx: Transaction, params: dict[str, Any]) -> Reason | None:
    payload = tx.payload

    if tx.sender not in state.balances:
        return Reason.UNKNOWN_SENDER

    if not isinstance(payload, dict) or set(payload.keys()) != {"coop_id"}:
        return Reason.INVALID_PAYLOAD

    coop_id = payload.get("coop_id")
    if coop_id not in state.coops:
        return Reason.COOP_NOT_FOUND

    if _member_of(state, tx.sender) is not None:
        return Reason.ALREADY_IN_COOP

    coop = state.coops[coop_id]
    if len(coop["members"]) >= params.get("max_coop_members", 12):
        return Reason.COOP_FULL

    return None


def _apply_join_coop(state: WorldState, tx: Transaction) -> dict[str, Any]:
    coop = state.coops[tx.payload["coop_id"]]
    coop["members"].append(tx.sender)
    return {
        "tick": tx.tick,
        "sender": tx.sender,
        "action": "JOIN_COOP",
        "coop_id": tx.payload["coop_id"],
    }



def _validate_leave_coop(state: WorldState, tx: Transaction, params: dict[str, Any]) -> Reason | None:
    """LEAVE_COOP (2026-09-01, need-driven labor mobility): symmetric to
    JOIN_COOP. A member may exit their co-op freely — labor is not owned
    by the co-op. Leaving an empty co-op is allowed (it simply idles)."""
    payload = tx.payload

    if tx.sender not in state.balances:
        return Reason.UNKNOWN_SENDER

    if not isinstance(payload, dict) or set(payload.keys()) != {"coop_id"}:
        return Reason.INVALID_PAYLOAD

    coop_id = payload.get("coop_id")
    if coop_id not in state.coops:
        return Reason.COOP_NOT_FOUND

    if _member_of(state, tx.sender) is None:
        return Reason.NOT_A_MEMBER

    return None


def _apply_leave_coop(state: WorldState, tx: Transaction) -> dict[str, Any]:
    coop = state.coops[tx.payload["coop_id"]]
    coop["members"].remove(tx.sender)
    return {
        "tick": tx.tick,
        "sender": tx.sender,
        "action": "LEAVE_COOP",
        "coop_id": tx.payload["coop_id"],
    }


# --------------------------------------------------------------------- WORK


def _validate_work(state: WorldState, tx: Transaction, params: dict[str, Any]) -> Reason | None:
    payload = tx.payload

    if tx.sender not in state.balances:
        return Reason.UNKNOWN_SENDER

    # Stage 5 - demographics: children (age < adulthood_ticks) may not
    # WORK. Real childhood (spec section 2): they consume and grow first.
    from .demographics import is_child
    if is_child(state, tx.sender, params):
        return Reason.INVALID_HOURS  # child labor forbidden (dignity floor)

    if not isinstance(payload, dict) or set(payload.keys()) != {"coop_id", "hours"}:
        return Reason.INVALID_PAYLOAD

    hours = payload.get("hours")
    coop_id = payload.get("coop_id")

    if not _is_int(hours):
        return Reason.INVALID_HOURS
    if coop_id not in state.coops:
        return Reason.COOP_NOT_FOUND
    coop = state.coops[coop_id]
    if tx.sender not in coop["members"]:
        return Reason.NOT_A_MEMBER
    if hours <= 0:
        return Reason.INVALID_HOURS
    # Anti-exploit (wage-mint farming): logging labor society cannot use
    # mints unbacked credits forever. A coop's labor pool only accepts
    # hours it could plausibly consume (cap = planned slack).
    cap = params.get("labor_pool_cap")
    if cap is not None and coop["labor_pool_hours"] + hours > cap:
        return Reason.LABOR_POOL_FULL
    if hours > params.get("max_work_hours_per_tick", 8):
        return Reason.INVALID_HOURS
    # Cumulative per-tick cap (anti multi-transaction mint exploit): the
    # per-tx cap alone allowed N WORK txs to mint N x cap in one tick.
    cum_cap = params.get("max_work_hours_cumulative")
    if cum_cap is not None and state.worked_hours_tick.get(tx.sender, 0) + hours > cum_cap:
        return Reason.INVALID_HOURS

    return None


def _apply_work(state: WorldState, tx: Transaction, params: dict[str, Any]) -> dict[str, Any]:
    coop = state.coops[tx.payload["coop_id"]]
    hours = tx.payload["hours"]
    mult_bp = params.get("wage_multiplier_bp", 10_000)

    # Integer-only wage math with remainder accumulation (no floats, ever)
    total_bp = hours * mult_bp + coop.get("wage_remainder_bp", 0)
    credits = total_bp // 10_000
    coop["wage_remainder_bp"] = total_bp % 10_000

    # Wage funding (D14 flaw fix L2): pay from the coop's treasury first;
    # mint only the shortfall. Society stands behind honest work, but a
    # solvent coop no longer silently expands the money supply.
    # Legacy mode ("mint", the v0.01 behavior) stays available for replay.
    # Fixed-supply mode (money_cap): minting is FORBIDDEN. The treasury
    # pays what it can; any shortfall becomes the coop's wage debt to the
    # worker (visible on the ledger, repaid automatically from future
    # sales by the wage-debt repayment phase).
    mc = params.get("money_cap") or {}
    upc = int(mc.get("units_per_credit", 100)) if mc.get("enabled") else 1
    owed = credits * upc  # wage in state units (credits when no cap)
    if mc.get("enabled"):
        funded = min(coop.get("treasury", 0), owed)
        coop["treasury"] = coop.get("treasury", 0) - funded
        state.balances[tx.sender] += funded
        if funded < owed:
            debt = owed - funded
            wd = coop.setdefault("wage_debt", {})
            wd[tx.sender] = wd.get(tx.sender, 0) + (owed - funded)
    else:
        mint_mode = params.get("wage_mint_mode", "mint")
        if mint_mode == "treasury_first":
            funded = min(coop.get("treasury", 0), credits)
            minted = credits - funded
            coop["treasury"] = coop.get("treasury", 0) - funded
            state.balances[tx.sender] += credits
            state.money_minted += minted
        else:
            state.balances[tx.sender] += credits
            state.money_minted += credits

    coop["labor_pool_hours"] += hours
    state.labor_hours[tx.sender] += hours
    state.worked_hours_tick[tx.sender] = state.worked_hours_tick.get(tx.sender, 0) + hours

    return {
        "tick": tx.tick,
        "sender": tx.sender,
        "action": "WORK",
        "coop_id": tx.payload["coop_id"],
        "hours": hours,
        "wage_credits": credits,
    }


# ------------------------------------------------------------------ PRODUCE


def _validate_produce(state: WorldState, tx: Transaction, params: dict[str, Any]) -> Reason | None:
    payload = tx.payload

    if tx.sender not in state.balances:
        return Reason.UNKNOWN_SENDER

    if not isinstance(payload, dict) or set(payload.keys()) != {"coop_id", "recipe_id", "runs"}:
        return Reason.INVALID_PAYLOAD

    runs = payload.get("runs")
    recipe_id = payload.get("recipe_id")
    coop_id = payload.get("coop_id")

    if not _is_int(runs) or runs <= 0:
        return Reason.INVALID_RUNS
    if coop_id not in state.coops:
        return Reason.COOP_NOT_FOUND
    coop = state.coops[coop_id]
    if tx.sender not in coop["members"]:
        return Reason.NOT_A_MEMBER
    if recipe_id not in state.recipes:
        return Reason.RECIPE_NOT_FOUND

    recipe = state.recipes[recipe_id]
    inventory = coop["inventory"]

    # Material inputs × runs
    for good, qty in recipe["inputs"].items():
        if inventory.get(good, 0) < qty * runs:
            return Reason.NOT_ENOUGH_INPUTS

    # Energy × runs (electricity good)
    energy_needed = recipe["energy"] * runs
    if energy_needed > 0 and inventory.get("electricity", 0) < energy_needed:
        return Reason.NOT_ENOUGH_ENERGY

    # Labor pool × runs
    if coop.get("labor_pool_hours", 0) < recipe["labor_hours"] * runs:
        return Reason.NOT_ENOUGH_LABOR

    return None


def _vwap_add(state: WorldState, coop_id: str, good: str, qty_before: int, qty_added: int, unit_price: int) -> None:
    """Moving-average purchase cost, integer 1/10,000 cr per unit.
    qty_before is the coop's inventory of `good` before this purchase."""
    per = state.coop_vwap.setdefault(coop_id, {})
    old_v = per.get(good)
    if old_v is None:
        # seed from book baseline scaled to 1e-4 units
        old_v = state.good_cost_baseline.get(good, 1) * 10_000
    new_v = (old_v * qty_before + unit_price * 10_000 * qty_added) // (qty_before + qty_added) if (qty_before + qty_added) > 0 else old_v
    per[good] = new_v


def _vwap_unit_cost(state: WorldState, coop_id: str, good: str) -> int:
    """Coop's per-unit cost of `good` in whole credits: VWAP if tracked,
    else book baseline (replacement-cost fallback)."""
    v = state.coop_vwap.get(coop_id, {}).get(good)
    return v // 10_000 if v is not None else state.good_cost_baseline.get(good, 1)


def _apply_produce(state: WorldState, tx: Transaction, params: dict[str, Any]) -> dict[str, Any]:
    coop = state.coops[tx.payload["coop_id"]]
    recipe = state.recipes[tx.payload["recipe_id"]]
    runs = tx.payload["runs"]
    inventory = coop["inventory"]

    # Consume inputs
    for good, qty in recipe["inputs"].items():
        inventory[good] -= qty * runs

    # Consume energy
    energy_consumed = recipe["energy"] * runs
    if energy_consumed > 0:
        inventory["electricity"] -= energy_consumed

    # Consume labor from pool
    coop["labor_pool_hours"] -= recipe["labor_hours"] * runs

    # Public capital, private use: society charges rent for machines
    # consumed as inputs (depreciation of socially-owned capital flows to
    # the surplus pool, which recycles it to citizens). Capped at treasury.
    cr = params.get("capital_rent") or {}
    machine_rent_rate = cr.get("per_machine_used", 0)
    tool_rent_rate = cr.get("per_tool_used", 0)
    machines_used = recipe["inputs"].get("machines", 0) * runs
    tools_used = recipe["inputs"].get("hand_tools", 0) * runs
    capital_rent = 0
    if (machine_rent_rate > 0 and machines_used > 0) or (tool_rent_rate > 0 and tools_used > 0):
        treasury = coop.get("treasury", 0)
        capital_rent = min(machine_rent_rate * machines_used + tool_rent_rate * tools_used, treasury)
        if capital_rent > 0:
            coop["treasury"] = treasury - capital_rent
            # Earmarked depreciation reserve: capital refresh draws from
            # this fund only, so replacement money is never spent on
            # dividends (the t~800 machine-death failure mode).
            state.capital_fund += capital_rent

    # Produce outputs
    outputs_produced: dict[str, int] = {}
    for good, qty in recipe["outputs"].items():
        inventory[good] = inventory.get(good, 0) + qty * runs
        outputs_produced[good] = qty * runs

    # Cost baseline: ceil((labor + energy + material inputs) / total output units)
    # Round UP, never down: production at cost must not price below cost.
    # Floor division priced high-output staples (100 grain per run) at 0,
    # collapsing the whole market into pure surplus.
    vwap_on = (params.get("cost_accounting") or {}).get("method") == "vwap"
    labor_cost = recipe["labor_hours"] * runs  # 1 credit/hour base accounting
    if vwap_on:
        coop_id_ = tx.payload["coop_id"]
        energy_cost = energy_consumed * _vwap_unit_cost(state, coop_id_, "electricity") if energy_consumed else 0
        input_cost = sum(
            qty * runs * _vwap_unit_cost(state, coop_id_, good) for good, qty in recipe["inputs"].items()
        )
        # Track capital consumption whenever capital goods are used as
        # inputs (Stage 3 gate metric: self-sustained capital). Was gated
        # behind capital_refresh; decoupled so market-bought capital is
        # also visible. capital_burned only enters snapshots when nonzero —
        # worlds that never burn capital hash identically.
        burned = recipe["inputs"].get("machines", 0) * runs + recipe["inputs"].get("hand_tools", 0) * runs
        if burned:
            state.capital_burned[coop_id_] = state.capital_burned.get(coop_id_, 0) + burned
    else:
        energy_cost = energy_consumed * params.get("energy_price", 2)
        input_cost = sum(
            qty * runs * state.good_cost_baseline.get(good, 1) for good, qty in recipe["inputs"].items()
        )
    total_units = sum(outputs_produced.values())

    baselines_stamped: dict[str, int] = {}
    if total_units > 0:
        unit_baseline = max(1, -(-(labor_cost + energy_cost + input_cost) // total_units))
        for good in outputs_produced:
            state.good_cost_baseline[good] = unit_baseline
            baselines_stamped[good] = unit_baseline

    result = {
        "tick": tx.tick,
        "sender": tx.sender,
        "action": "PRODUCE",
        "coop_id": tx.payload["coop_id"],
        "recipe_id": tx.payload["recipe_id"],
        "runs": runs,
        "outputs": outputs_produced,
        "cost_baselines": baselines_stamped,
        "capital_rent_paid": capital_rent,
        "capital_rent_pool_after": state.surplus_pool if capital_rent else None,
    }
    return result


# ----------------------------------------------------------------- MARKETS


def _validate_list_good(state: WorldState, tx: Transaction, params: dict[str, Any]) -> Reason | None:
    payload = tx.payload

    if tx.sender not in state.balances:
        return Reason.UNKNOWN_SENDER

    if not isinstance(payload, dict) or set(payload.keys()) != {"coop_id", "good", "qty"}:
        return Reason.INVALID_PAYLOAD

    coop_id = payload.get("coop_id")
    good = payload.get("good")
    qty = payload.get("qty")

    if coop_id not in state.coops:
        return Reason.COOP_NOT_FOUND
    coop = state.coops[coop_id]
    if tx.sender not in coop["members"]:
        return Reason.NOT_A_MEMBER
    if good not in state.goods:
        return Reason.GOOD_UNKNOWN
    if not _is_int(qty) or qty <= 0:
        return Reason.INVALID_QTY
    if coop["inventory"].get(good, 0) < qty:
        return Reason.NOT_ENOUGH_INVENTORY
    return None


def _apply_list_good(state: WorldState, tx: Transaction) -> dict[str, Any]:
    payload = tx.payload
    coop = state.coops[payload["coop_id"]]
    good = payload["good"]
    qty = payload["qty"]

    # Escrow: goods leave inventory into the listing
    coop["inventory"][good] -= qty
    floor = state.good_cost_baseline.get(good, 1)

    state.listings.setdefault(good, []).append({
        "coop_id": payload["coop_id"],
        "qty": qty,
        "floor": floor,
        "listed_tick": tx.tick,
    })

    return {
        "tick": tx.tick,
        "sender": tx.sender,
        "action": "LIST_GOOD",
        "coop_id": payload["coop_id"],
        "good": good,
        "qty": qty,
        "floor": floor,
    }


def _validate_bid(state: WorldState, tx: Transaction, params: dict[str, Any]) -> Reason | None:
    payload = tx.payload

    if tx.sender not in state.balances:
        return Reason.UNKNOWN_SENDER

    keys = {"good", "max_price", "qty"}
    if not isinstance(payload, dict) or set(payload.keys()) != keys:
        return Reason.INVALID_PAYLOAD

    good = payload.get("good")
    price = payload.get("max_price")
    qty = payload.get("qty")

    if good not in state.goods:
        return Reason.GOOD_UNKNOWN
    if not _is_int(price) or price <= 0:
        return Reason.INVALID_PRICE
    if not _is_int(qty) or qty <= 0:
        return Reason.INVALID_QTY

    floor = state.good_cost_baseline.get(good, 1)
    if price < floor:
        return Reason.INVALID_PRICE  # below cost floor

    # Affordability at submission (max exposure = price × qty)
    if state.balances[tx.sender] < price * qty:
        return Reason.INSUFFICIENT_FUNDS
    return None


def _apply_bid(state: WorldState, tx: Transaction) -> dict[str, Any]:
    payload = tx.payload
    state.bids.append({
        "bidder": tx.sender,
        "coop_id": None,
        "good": payload["good"],
        "max_price": payload["max_price"],
        "qty": payload["qty"],
    })
    return {
        "tick": tx.tick,
        "sender": tx.sender,
        "action": "BID",
        "good": payload["good"],
        "max_price": payload["max_price"],
        "qty": payload["qty"],
    }


def _validate_bid_for_coop(state: WorldState, tx: Transaction, params: dict[str, Any]) -> Reason | None:
    payload = tx.payload

    if tx.sender not in state.balances:
        return Reason.UNKNOWN_SENDER

    keys = {"coop_id", "good", "max_price", "qty"}
    if not isinstance(payload, dict) or set(payload.keys()) != keys:
        return Reason.INVALID_PAYLOAD

    coop_id = payload.get("coop_id")
    good = payload.get("good")
    price = payload.get("max_price")
    qty = payload.get("qty")

    if coop_id not in state.coops:
        return Reason.COOP_NOT_FOUND
    coop = state.coops[coop_id]
    if tx.sender not in coop["members"]:
        return Reason.NOT_A_MEMBER
    if good not in state.goods:
        return Reason.GOOD_UNKNOWN
    if not _is_int(price) or price <= 0:
        return Reason.INVALID_PRICE
    if not _is_int(qty) or qty <= 0:
        return Reason.INVALID_QTY

    floor = state.good_cost_baseline.get(good, 1)
    if price < floor:
        return Reason.INVALID_PRICE

    if coop.get("treasury", 0) < price * qty:
        return Reason.INSUFFICIENT_FUNDS
    return None


def _apply_bid_for_coop(state: WorldState, tx: Transaction) -> dict[str, Any]:
    payload = tx.payload
    state.bids.append({
        "bidder": tx.sender,
        "coop_id": payload["coop_id"],
        "good": payload["good"],
        "max_price": payload["max_price"],
        "qty": payload["qty"],
    })
    return {
        "tick": tx.tick,
        "sender": tx.sender,
        "action": "BID_FOR_COOP",
        "coop_id": payload["coop_id"],
        "good": payload["good"],
        "max_price": payload["max_price"],
        "qty": payload["qty"],
    }


def _validate_buy_essential(state: WorldState, tx: Transaction, params: dict[str, Any]) -> Reason | None:
    payload = tx.payload

    if tx.sender not in state.balances:
        return Reason.UNKNOWN_SENDER

    if not isinstance(payload, dict) or set(payload.keys()) != {"good", "qty"}:
        return Reason.INVALID_PAYLOAD

    good = payload.get("good")
    qty = payload.get("qty")

    if good not in state.goods:
        return Reason.GOOD_UNKNOWN
    if not _is_int(qty) or qty <= 0:
        return Reason.INVALID_QTY

    triage = state.effective_triage(good)
    if triage not in ("essential", "emergency"):
        return Reason.NOT_ESSENTIAL

    quota = params.get("essential_need_quota", {}).get(good, 0)
    if qty > quota:
        return Reason.QUOTA_EXCEEDED

    price = state.good_cost_baseline.get(good, 1)
    if state.balances[tx.sender] < price * qty:
        return Reason.INSUFFICIENT_FUNDS

    # supply check happens at clearing (FCFS); nothing else to verify here
    return None


def _apply_buy_essential(state: WorldState, tx: Transaction) -> dict[str, Any]:
    payload = tx.payload
    state.bids.append({
        "bidder": tx.sender,
        "coop_id": None,
        "good": payload["good"],
        "max_price": state.good_cost_baseline.get(payload["good"], 1),  # baseline price, no bidding
        "qty": payload["qty"],
        "essential": True,
    })
    return {
        "tick": tx.tick,
        "sender": tx.sender,
        "action": "BUY_ESSENTIAL",
        "good": payload["good"],
        "qty": payload["qty"],
    }


def _clear_markets(state: WorldState, tick: int, params: dict[str, Any], ledger: Ledger) -> list[dict[str, Any]]:
    """End-of-tick market clearing. Deterministic (spec §9).

    1. Essential FCFS pass: essential/emergency goods sold at the seller's
       cost floor to essential buyers in deterministic order.
    2. Auction pass: remaining listed units sold to market bids at the
       uniform clearing price (lowest winning bid, never below floor).
    3. Unsold units return to their sellers.
    4. Surplus (price - floor) flows to the pool; pool beyond the reserve
       cap is retired from circulation.

    Money conservation is exact: every unit sold at price P moves exactly
    P credits from the buyer to seller floor + pool (P - floor). Integer
    only, no rounding — nothing is ever created or destroyed by clearing.
    """
    events: list[dict[str, Any]] = []

    if not state.listings and not state.bids:
        return events

    essential_buyers: dict[str, list[dict[str, Any]]] = {}
    auction_bids: dict[str, list[dict[str, Any]]] = {}

    for bid in sorted(
        state.bids,
        key=lambda b: (b["bidder"], str(b["coop_id"]), b["good"], b["qty"], b["max_price"]),
    ):
        if bid.get("essential"):
            essential_buyers.setdefault(bid["good"], []).append(bid)
        else:
            auction_bids.setdefault(bid["good"], []).append(bid)

    # --- Pass 1: essentials FCFS at the cost floor (D8: need first)
    # Common-pool draw first: reclaimed hoard goods at cost (§6.4).
    # Buyers pay the pool; pool value later funds public purposes.
    # Fair clearing (votable): rotate buyer service order each tick so
    # scarce essentials don't permanently starve alphabetically-late
    # citizens under deterministic FCFS. Off => legacy order (replay-safe).
    fair = params.get("fair_clearing", False)
    # Stage 5 - crisis override forces need-based rotation ON
    from . import crisis as _crisis_fair
    if _crisis_fair.crisis_active(state):
        fair = True

    def _served(good: str) -> list[dict[str, Any]]:
        buyers = essential_buyers[good]
        if not fair or len(buyers) < 2:
            return buyers
        off = tick % len(buyers)
        return buyers[off:] + buyers[:off]

    for good in sorted(essential_buyers.keys() & state.common_pool.keys()):
        pool_qty = state.common_pool[good]
        if pool_qty <= 0:
            continue
        for buyer in _served(good):
            if pool_qty <= 0:
                break
            take = min(buyer["qty"], pool_qty)
            price = state.good_cost_baseline.get(good, 1)
            if state.balances[buyer["bidder"]] < take * price:
                continue
            state.balances[buyer["bidder"]] -= take * price
            state.surplus_pool += take * price  # society reclaims value at cost
            inv = state.citizen_inventory.setdefault(buyer["bidder"], {})
            inv[good] = inv.get(good, 0) + take
            state.common_pool[good] -= take
            pool_qty -= take
            buyer["qty"] -= take

    # --- Producer input priority (Stage 4, votable; default OFF).
    # Without it, citizens' essential FCFS stripped every unit of
    # bread/vegetables/meat at the floor before producer auction bids
    # filled: the kitchen bid 1,603 bread, received 0, and never
    # produced a single meal in 1,000 ticks — producer input
    # starvation. This pass lets coops buy the inputs of their trade
    # at the seller's floor BEFORE the citizen pass, so production
    # chains can run. share_cap_bp keeps citizens first-class:
    # producers may claim at most that share of each good's listed
    # units per tick. Money flow mirrors the essential pass exactly
    # (buyer treasury -> seller treasury at floor, no pool cut).
    pip = params.get("producer_input_priority") or {}
    # Stage 5 - crisis override: advantages/priorities are suspended
    # during an active crisis (need-first distribution, spec section 4).
    from . import crisis as _crisis_mod
    if _crisis_mod.crisis_active(state):
        pip = {}
    if pip.get("enabled"):
        cap_bp = max(0, min(10_000, int(pip.get("share_cap_bp", 5_000))))
        for good in sorted(state.listings.keys()):
            entries = [e for e in state.listings[good] if e["qty"] > 0]
            if not entries:
                continue
            pbids = [
                b for b in auction_bids.get(good, [])
                if b.get("coop_id") is not None and b["qty"] > 0
            ]
            if not pbids:
                continue
            total_qty = sum(e["qty"] for e in entries)
            claimable = (total_qty * cap_bp) // 10_000
            if claimable <= 0:
                continue
            pbids.sort(key=lambda b: (b["bidder"], b["qty"]))
            # rotate service order by tick: alphabetical FCFS starved late
            # names forever when supply is scarce (millers lost grain to
            # livestock_co every tick; bread chain died) — mirrors the
            # fair_clearing rotation citizens already have.
            if len(pbids) > 1:
                _off = tick % len(pbids)
                pbids = pbids[_off:] + pbids[:_off]
            served: list[dict[str, Any]] = []
            for bid in pbids:
                if claimable <= 0:
                    break
                coop = state.coops[bid["coop_id"]]
                want = min(bid["qty"], claimable)
                got = 0
                paid = 0
                for entry in entries:
                    if want <= 0:
                        break
                    if entry["qty"] <= 0:
                        continue
                    if entry["coop_id"] == bid["coop_id"]:
                        continue  # no self-dealing (wash guard)
                    take = min(entry["qty"], want)
                    price = entry["floor"]
                    if coop.get("treasury", 0) < take * price:
                        break
                    coop["treasury"] -= take * price
                    entry["qty"] -= take
                    seller = state.coops[entry["coop_id"]]
                    seller["treasury"] = seller.get("treasury", 0) + take * price
                    state.treasury_in += take * price
                    # per-fill integer VWAP: price is the entry floor (int).
                    # A single float anywhere corrupts baselines -> _is_int
                    # rejects every later bid for the good (observed: bread
                    # chain died tick ~1 after a float slipped into vwap).
                    inv = coop["inventory"]
                    if (params.get("cost_accounting") or {}).get("method") == "vwap":
                        _vwap_add(state, bid["coop_id"], good, inv.get(good, 0), take, price)
                    inv[good] = inv.get(good, 0) + take
                    want -= take
                    got += take
                    paid += take * price
                    claimable -= take
                if got > 0:
                    bid["qty"] -= got
                    served.append({"coop_id": bid["coop_id"], "qty": got, "paid": paid})
            # fully-served producer bids leave the auction book
            if good in auction_bids:
                auction_bids[good] = [
                    b for b in auction_bids[good]
                    if not (b.get("coop_id") is not None and b["qty"] <= 0)
                ]
            if served:
                events.append({
                    "tick": tick,
                    "action": "PRODUCER_INPUT_CLEAR",
                    "good": good,
                    "served": served,
                })

    for good in sorted(essential_buyers.keys() & state.listings.keys()):
        sold_records: list[dict[str, Any]] = []
        total_sold = 0
        listed = sum(e["qty"] for e in state.listings[good])

        for buyer in _served(good):
            need = buyer["qty"]
            got = 0
            paid = 0
            for entry in state.listings[good]:
                if need <= 0:
                    break
                take = min(entry["qty"], need)
                if take <= 0:
                    continue
                price = entry["floor"]
                if state.balances[buyer["bidder"]] < take * price:
                    break  # cannot pay at settlement — deterministic drop
                state.balances[buyer["bidder"]] -= take * price
                entry["qty"] -= take
                seller = state.coops[entry["coop_id"]]
                seller["treasury"] = seller.get("treasury", 0) + take * price
                state.treasury_in += take * price
                need -= take
                got += take
                paid += take * price
            if got > 0:
                inv = state.citizen_inventory.setdefault(buyer["bidder"], {})
                inv[good] = inv.get(good, 0) + got
                total_sold += got
                sold_records.append({"bidder": buyer["bidder"], "qty": got, "paid": paid})

        events.append({
            "tick": tick,
            "action": "MARKET_CLEAR_ESSENTIAL",
            "good": good,
            "listed": listed,
            "sold": total_sold,
            "buyers": sold_records,
        })

    # --- Pass 2: uniform-price auction for the rest
    for good in sorted(state.listings.keys()):
        entries = [e for e in state.listings[good] if e["qty"] > 0]
        if not entries:
            continue

        supply = sum(e["qty"] for e in entries)
        bids = auction_bids.get(good, [])
        bids.sort(key=lambda b: (-b["max_price"], b["bidder"], str(b["coop_id"])))

        winners: list[dict[str, Any]] = []
        remaining_supply = supply
        committed: dict[str, int] = {}  # payer key -> credits already promised
        for bid in bids:
            if remaining_supply <= 0:
                break
            take = min(bid["qty"], remaining_supply)
            # live funds re-check at settlement, accounting for cumulative
            # exposure: multiple winning bids by one payer must jointly fit
            key = bid["coop_id"] if bid["coop_id"] is not None else bid["bidder"]
            if bid["coop_id"] is not None:
                funds = state.coops[bid["coop_id"]].get("treasury", 0)
            else:
                funds = state.balances[bid["bidder"]]
            if funds - committed.get(key, 0) < take * bid["max_price"]:
                continue  # dropped: cannot pay at settlement
            committed[key] = committed.get(key, 0) + take * bid["max_price"]
            winners.append({"bid": bid, "take": take})
            remaining_supply -= take

        if not winners:
            _return_unsold(state, good)
            events.append({
                "tick": tick,
                "action": "MARKET_CLEAR_AUCTION",
                "good": good,
                "listed": supply,
                "sold": 0,
                "clearing_price": None,
                "surplus_delta": 0,
                "winners": [],
            })
            continue

        clearing = min(w["bid"]["max_price"] for w in winners)
        total_sold = supply - remaining_supply
        state.last_clearing[good] = clearing  # public price signal
        floor = state.good_cost_baseline.get(good, 1)

        # WASH_BID detection (§6.4): a winning personal bidder who belongs
        # to the selling co-op AND bids far above floor is wash-trading —
        # faking demand on their own listing. Detect the attempt, not just
        # realized inflation (other bidders may anchor the clearing price).
        for w in winners:
            if w["bid"]["coop_id"] is None and w["bid"]["max_price"] > 2 * floor:
                for entry in entries:
                    if entry["qty"] > 0:
                        seller_members = state.coops[entry["coop_id"]].get("members", [])
                        if w["bid"]["bidder"] in seller_members:
                            flag = {
                                "tick": tick,
                                "kind": "WASH_BID",
                                "target": w["bid"]["bidder"],
                                "good": good,
                                "bid_price": w["bid"]["max_price"],
                                "clearing": clearing,
                                "floor": floor,
                            }
                            if ("WASH_BID", flag["target"], good) not in {(f["kind"], f["target"], f.get("good", "")) for f in state.flags}:
                                state.flags.append(flag)

        # buyers pay take x clearing (exact)
        vwap_on = (params.get("cost_accounting") or {}).get("method") == "vwap"
        for w in winners:
            bid = w["bid"]
            payment = w["take"] * clearing
            if bid["coop_id"] is not None:
                coop = state.coops[bid["coop_id"]]
                coop["treasury"] = max(0, coop.get("treasury", 0) - payment)
                inv = coop["inventory"]
                if vwap_on:
                    _vwap_add(state, bid["coop_id"], good, inv.get(good, 0) - w["take"], w["take"], clearing)
            else:
                state.balances[bid["bidder"]] -= payment
                inv = state.citizen_inventory.setdefault(bid["bidder"], {})
            inv[good] = inv.get(good, 0) + w["take"]

        # sellers receive floor per unit; pool receives clearing - floor (exact)
        surplus_delta = 0
        to_sell = total_sold
        for entry in entries:
            if to_sell <= 0:
                break
            take = min(entry["qty"], to_sell)
            floor_used = min(entry["floor"], clearing)
            seller = state.coops[entry["coop_id"]]
            seller["treasury"] = seller.get("treasury", 0) + take * floor_used
            state.treasury_in += take * floor_used
            surplus_delta += take * (clearing - floor_used)
            state.surplus_pool += take * (clearing - floor_used)
            entry["qty"] -= take
            to_sell -= take

        _return_unsold(state, good)

        events.append({
            "tick": tick,
            "action": "MARKET_CLEAR_AUCTION",
            "good": good,
            "listed": supply,
            "sold": total_sold,
            "clearing_price": clearing,
            "surplus_delta": surplus_delta,
            "winners": [
                {"bidder": w["bid"]["bidder"], "coop_id": w["bid"]["coop_id"], "qty": w["take"], "price": clearing}
                for w in winners
            ],
        })

    # --- Pass 3: retire pool beyond the cap
    # Fixed supply (money_cap): NO destruction. The pool is the nation's
    # credit fund; deflation comes from scarcity, not from burning money.
    cap = params.get("surplus_reserve_cap", 0)
    if not (params.get("money_cap") or {}).get("enabled") and state.surplus_pool > cap:
        excess = state.surplus_pool - cap
        state.surplus_pool -= excess
        state.money_retired += excess
        events.append({
            "tick": tick,
            "action": "SURPLUS_RETIRE",
            "excess_retired": excess,
            "pool_after": state.surplus_pool,
        })

    state.listings = {g: ls for g, ls in state.listings.items() if any(e["qty"] > 0 for e in ls)}
    state.bids = []
    return events


def _return_unsold(state: WorldState, good: str) -> int:
    """Return all remaining listed units to their sellers (exact, no rounding)."""
    remaining = 0
    for entry in state.listings.get(good, []):
        qty = entry["qty"]
        if qty > 0:
            coop = state.coops[entry["coop_id"]]
            coop["inventory"][good] = coop["inventory"].get(good, 0) + qty
            entry["qty"] = 0
            remaining += qty
    return remaining


# ------------------------------------------------------------- GOVERNANCE


# ---------------------------------------------------- CIRCULAR FLOW


def _consume_phase(state: WorldState, tick: int, params: dict[str, Any]) -> list[dict[str, Any]]:
    """Citizens use up goods to live (deterministic; spec: circular flow).

    For every citizen and every needed good, consume min(held, quota).
    Goods are destroyed — that is the point: demand is recurring.
    Unmet needs are tracked publicly (welfare signal, God View alerts).
    Inert when the ruleset has no `needs` param (replay compat).
    """
    needs = params.get("needs")
    if not needs:
        return []
    # Optional per-good consumption cycles: quota is consumed every N ticks
    # instead of every tick (integer-native fractional needs). Goods without
    # an entry consume daily as before — old worlds replay identically.
    cycles = params.get("needs_cycle") or {}

    events: list[dict[str, Any]] = []
    for citizen in sorted(state.balances.keys()):
        inv = state.citizen_inventory.setdefault(citizen, {})
        consumed: dict[str, int] = {}
        unmet: dict[str, bool] = {}
        # Stage 5 - demographics: children consume a scaled integer share
        # of each quota (child_need_pct). Inert without demographics.
        from .demographics import is_child, child_need_pct
        _scale_bp = 10_000
        if is_child(state, citizen, params):
            _scale_bp = child_need_pct(params) * 100
        for good in sorted(needs.keys()):
            quota = needs[good]
            if quota <= 0:
                continue
            if is_child(state, citizen, params):
                # integer-native scaling: floor(scaled), min 1 when any
                # need exists (children always need something to live).
                # Base is 10_000 (bp), NOT _scale_bp (dividing by the
                # scale itself is a silent no-op).
                quota = max(1, (quota * _scale_bp) // 10_000)
            cyc = cycles.get(good, 1)
            if cyc > 1 and tick % cyc != 0:
                continue  # not this good's consumption day
            held = inv.get(good, 0)
            take = min(held, quota)
            if take > 0:
                inv[good] = held - take
                state.consumed_totals[good] = state.consumed_totals.get(good, 0) + take
                consumed[good] = take
            if take >= quota:
                # fully met this tick — reset the streak
                if citizen in state.unmet_needs and good in state.unmet_needs[citizen]:
                    del state.unmet_needs[citizen][good]
                    if not state.unmet_needs[citizen]:
                        del state.unmet_needs[citizen]
            else:
                streaks = state.unmet_needs.setdefault(citizen, {})
                streaks[good] = streaks.get(good, 0) + 1
                unmet[good] = True
        if consumed or unmet:
            events.append({
                "tick": tick,
                "action": "CONSUMED",
                "citizen": citizen,
                "consumed": consumed,
                "unmet": unmet,
            })
    return events


def _surplus_spend_phase(state: WorldState, tick: int, params: dict[str, Any]) -> list[dict[str, Any]]:
    """Surplus returns to society (D11 spending half; circular flow).

    1. Citizen dividend: pool -> every citizen, even integer split
       (remainder stays in the pool; nothing is lost to rounding).
    2. Public services: pool refunds citizens for essential units they
       actually consumed this tick, at cost baseline — essentials are
       funded by the social surplus. Budget-capped, sorted order.

    Inert when the ruleset has no `surplus_spending` param (replay compat).
    Retirement above `surplus_reserve_cap` still happens in clearing,
    after spending — spending has priority over retirement.
    """
    ss = params.get("surplus_spending")
    if not ss:
        return []

    n = len(state.balances)
    if n == 0:
        return []

    buffer = ss.get("min_pool_buffer", 0)
    spendable = max(0, state.surplus_pool - buffer)

    events: list[dict[str, Any]] = []

    # --- 1) citizen dividend
    # Per-tick dividend cap: the legacy `max_dividend_per_tick` is a TOTAL
    # shared by all citizens (mis-scaled at large populations: 200 cr across
    # 986 citizens ~ 0.2 cr each). The optional per-capita key
    # `max_dividend_per_citizen_tick` caps per head instead and takes
    # precedence when present — old worlds without the key replay exactly.
    div_budget = spendable * ss.get("dividend_share_bp", 0) // 10_000
    per_citizen_cap = ss.get("max_dividend_per_citizen_tick")
    if per_citizen_cap is not None:
        # per-capita cap (scales with population) takes precedence
        div_budget = min(div_budget, int(per_citizen_cap) * n)
    else:
        # legacy TOTAL cap — old worlds without the new key replay exactly
        div_budget = min(div_budget, ss.get("max_dividend_per_tick", 0))
    div_budget = max(0, div_budget)
    per_citizen = div_budget // n
    div_paid = per_citizen * n
    if div_paid > 0:
        state.surplus_pool -= div_paid
        state.dividends_paid += div_paid
        for citizen in sorted(state.balances.keys()):
            state.balances[citizen] += per_citizen
        events.append({
            "tick": tick,
            "action": "SURPLUS_SPEND",
            "kind": "dividend",
            "per_citizen": per_citizen,
            "total": div_paid,
            "pool_after": state.surplus_pool,
        })

    # --- 2) public services: refund essential consumption at cost
    remaining = max(0, state.surplus_pool - buffer)
    serv_budget = min(remaining, spendable * ss.get("services_share_bp", 0) // 10_000)
    if serv_budget > 0:
        refunds: list[dict[str, Any]] = []
        paid = 0
        # This tick's events are the tail of `applied` (events are appended
        # in non-decreasing tick order). Locate the block boundary backward,
        # then iterate forward — same events, same order, O(this tick)
        # instead of O(whole ledger) per run of this loop.
        i = len(state.applied) - 1
        while i >= 0 and state.applied[i].get("tick") == tick:
            i -= 1
        start = i + 1
        for e in state.applied[start:]:
            if e.get("action") != "CONSUMED":
                continue
            citizen = e["citizen"]
            for good, qty in sorted(e.get("consumed", {}).items()):
                if paid >= serv_budget:
                    break
                if state.effective_triage(good) not in ("essential", "emergency"):
                    continue  # services fund essentials only
                rate = state.good_cost_baseline.get(good, 0)
                if rate <= 0 or qty <= 0:
                    continue
                refund = min(qty * rate, serv_budget - paid)
                state.surplus_pool -= refund
                state.balances[citizen] += refund
                state.services_paid += refund
                paid += refund
                refunds.append({"citizen": citizen, "good": good, "qty": qty, "refund": refund})
            if paid >= serv_budget:
                break
        if paid > 0:
            events.append({
                "tick": tick,
                "action": "SURPLUS_SPEND",
                "kind": "services",
                "total": paid,
                "pool_after": state.surplus_pool,
                "refunds": refunds,
            })

    return events


def _coop_distribute_phase(state: WorldState, tick: int, params: dict[str, Any]) -> list[dict[str, Any]]:
    """Patronage dividends: co-op surplus returns to worker-members.

    A co-op treasury with zero outflow hoards; the circular flow requires
    surplus above an operating buffer to flow back to the members who
    created it. Even integer split; remainder stays in the treasury.
    Inert when the ruleset has no `coop_distribution` param.
    """
    cd = params.get("coop_distribution")
    if not cd:
        return []

    buffer = cd.get("buffer", 0)
    share_bp = cd.get("share_bp", 0)
    events: list[dict[str, Any]] = []

    for coop_id in sorted(state.coops.keys()):
        coop = state.coops[coop_id]
        treasury = coop.get("treasury", 0)
        spendable = max(0, treasury - buffer)
        if spendable <= 0:
            continue
        dist = spendable * share_bp // 10_000
        members = [m for m in coop.get("members", []) if m in state.balances]
        if dist <= 0 or not members:
            continue
        per = dist // len(members)
        paid = per * len(members)
        if paid <= 0:
            continue
        coop["treasury"] = max(0, treasury - paid)
        for m in sorted(members):
            state.balances[m] += per
        state.coop_dividends_paid += paid
        events.append({
            "tick": tick,
            "action": "COOP_DISTRIBUTE",
            "coop_id": coop_id,
            "per_member": per,
            "total": paid,
            "treasury_after": coop["treasury"],
        })
    return events


def _wage_debt_repay_phase(state: WorldState, tick: int, params: dict[str, Any]) -> list[dict[str, Any]]:
    """Fixed supply (money_cap): coops repay wage debt from treasury,
    oldest debt first, after the day's sales. Transfers only — the fixed
    supply is never expanded. Deterministic (sorted coops, citizens)."""
    mc = params.get("money_cap") or {}
    if not mc.get("enabled"):
        return []
    events: list[dict[str, Any]] = []
    for cid in sorted(state.coops.keys()):
        coop = state.coops[cid]
        wd = coop.get("wage_debt") or {}
        if not wd or coop.get("treasury", 0) <= 0:
            continue
        for who in sorted(wd.keys()):
            if coop.get("treasury", 0) <= 0:
                break
            owed = wd[who]
            pay = min(owed, coop["treasury"])
            if pay <= 0:
                continue
            coop["treasury"] -= pay
            wd[who] = owed - pay
            state.balances[who] = state.balances.get(who, 0) + pay
            if wd[who] <= 0:
                del wd[who]
            events.append({
                "tick": tick,
                "action": "WAGE_DEBT_REPAY",
                "coop_id": cid,
                "citizen": who,
                "paid": pay,
            })
    return events


def _wealth_tax_phase(state: WorldState, tick: int, params: dict[str, Any]) -> list[dict[str, Any]]:
    """Wealth tax above a threshold, paid into the surplus pool.

    Integer floor math, deterministic (sorted citizens). A pure transfer:
    money supply unchanged. Inert without the rule param.
    """
    wt = params.get("wealth_tax")
    if not wt:
        return []
    threshold = wt.get("threshold", 0)
    rate_bp = wt.get("rate_bp", 0)
    if threshold <= 0 or rate_bp <= 0:
        return []

    # D14 flaw fix L4: optionally count coop net assets (treasury share +
    # inventory valued at cost baselines, attributed evenly to members) in
    # the tax base. Without this, goods are a tax-free wealth hideout
    # (nothing decays). Opt-in via wt["include_inventory"]; legacy worlds
    # replay unchanged.
    member_shares: dict[str, int] = {}
    if wt.get("include_inventory"):
        base = state.good_cost_baseline
        for cid in sorted(state.coops.keys()):
            c = state.coops[cid]
            members = c.get("members") or []
            if not members:
                continue
            inv_value = sum(base.get(g, 1) * q for g, q in (c.get("inventory") or {}).items())
            net = int(c.get("treasury", 0)) + inv_value
            per = net // len(members)
            if per > 0:
                for m in sorted(members):
                    member_shares[m] = member_shares.get(m, 0) + per

    events: list[dict[str, Any]] = []
    for who in sorted(state.balances.keys()):
        bal = state.balances[who] + member_shares.get(who, 0)
        excess = bal - threshold
        if excess <= 0:
            continue
        tax = excess * rate_bp // 10_000
        if tax <= 0:
            continue
        pay = min(tax, state.balances[who])
        state.balances[who] -= pay
        tax = pay
        state.surplus_pool += tax
        events.append({
            "tick": tick,
            "action": "WEALTH_TAX",
            "citizen": who,
            "tax": tax,
            "pool_after": state.surplus_pool,
        })
    return events


# Target capital stocks for public maintenance (until the toolsmith
# milestone makes capital goods endogenous).
_CAP_TARGETS = {"hand_tools": 100, "machines": 25}
_CAP_REPLACEMENT_COST = {"hand_tools": 60, "machines": 1_500}


def _capital_refresh_phase(state: WorldState, tick: int, params: dict[str, Any]) -> list[dict[str, Any]]:
    """Every interval_ticks, top up capital stocks below target.

    Replacement cost is paid from the surplus pool and retired (public
    capital maintenance takes money out of supply). Deterministic: sorted
    coop ids, spend while the pool lasts. Inert without the rule param.
    """
    cr = params.get("capital_refresh") or {}
    interval = cr.get("interval_ticks", 0)
    if interval <= 0 or tick % interval != 0:
        return []

    events: list[dict[str, Any]] = []
    for coop_id in sorted(state.coops.keys()):
        coop = state.coops[coop_id]
        inv = coop.get("inventory", {})
        top_up: dict[str, int] = {}
        cost = 0
        for good, target in _CAP_TARGETS.items():
            need = max(0, target - inv.get(good, 0))
            per_batch = cr.get(good, 0)
            give = min(need, per_batch) if per_batch > 0 else need
            if give > 0:
                top_up[good] = give
                cost += give * _CAP_REPLACEMENT_COST[good]
        if not top_up or cost <= 0:
            continue
        if cost > state.capital_fund:
            # partial in deterministic order: tools first, then machines
            spend = 0
            partial: dict[str, int] = {}
            for good in sorted(top_up.keys(), key=lambda g: _CAP_REPLACEMENT_COST[g]):
                for unit in range(top_up[good]):
                    nxt = spend + _CAP_REPLACEMENT_COST[good]
                    if nxt > state.capital_fund:
                        break
                    spend = nxt
                    partial[good] = partial.get(good, 0) + 1
            if not partial:
                continue
            top_up = partial
            cost = spend
        for good, qty in top_up.items():
            inv[good] = inv.get(good, 0) + qty
        state.capital_fund -= cost
        if not (params.get("money_cap") or {}).get("enabled"):
            state.money_retired += cost  # legacy: destruction shrinks supply
        # fixed supply: the pool paid, money stays in circulation (transfer)
        events.append({
            "tick": tick,
            "action": "CAPITAL_REFRESH",
            "coop_id": coop_id,
            "granted": top_up,
            "cost_retired": cost,
            "fund_after": state.capital_fund,
        })
    return events


def _gov_params(params: dict[str, Any]) -> dict[str, Any]:
    gov = params.get("governance") or {}
    return {
        "enabled": gov.get("enabled", False),
        "vote_window_ticks": gov.get("vote_window_ticks", 3),
        "quorum_bp": gov.get("quorum_bp", 5_000),
        "trial_period_ticks": gov.get("trial_period_ticks", 10),
    }


def _validate_propose(state: WorldState, tx: Transaction, params: dict[str, Any]) -> Reason | None:
    payload = tx.payload

    if tx.sender not in state.balances:
        return Reason.UNKNOWN_SENDER

    if not isinstance(payload, dict) or set(payload.keys()) != {"params", "activation_tick"}:
        return Reason.INVALID_PAYLOAD

    gov = _gov_params(params)
    if not gov["enabled"]:
        return Reason.GOVERNANCE_DISABLED

    activation = payload.get("activation_tick")
    if not _is_int(activation):
        return Reason.INVALID_PAYLOAD
    window_close = tx.tick + gov["vote_window_ticks"]
    if activation <= window_close:
        return Reason.ACTIVATION_IN_PAST  # must activate after the window closes

    reason = validate_params(payload.get("params"), known_goods=set(state.goods.keys()))
    if reason is not None:
        return reason

    # Constitutional guard: proposals may not disable governance or its ratchet
    if payload["params"].get("governance", {}).get("enabled") is False:
        return Reason.CONSTITUTIONAL_GUARD

    return None


def _apply_propose(state: WorldState, tx: Transaction, params: dict[str, Any]) -> dict[str, Any]:
    gov = _gov_params(params)
    proposal_id = f"p{state.next_proposal_id}"
    state.next_proposal_id += 1

    state.proposals[proposal_id] = {
        "proposal_id": proposal_id,
        "proposer": tx.sender,
        "params": dict(tx.payload["params"]),
        "activation_tick": tx.payload["activation_tick"],
        "opened_tick": tx.tick,
        "closes_tick": tx.tick + gov["vote_window_ticks"],
        "ballots": {},
        "status": "open",
        "is_rollback": False,
        "target_version": None,
        "change_tx_hash": tx.content_hash(),
    }

    return {
        "tick": tx.tick,
        "sender": tx.sender,
        "action": "PROPOSE",
        "proposal_id": proposal_id,
        "closes_tick": tx.tick + gov["vote_window_ticks"],
    }


def _validate_vote(state: WorldState, tx: Transaction, params: dict[str, Any]) -> Reason | None:
    payload = tx.payload

    if tx.sender not in state.balances:
        return Reason.UNKNOWN_SENDER

    if not isinstance(payload, dict) or set(payload.keys()) != {"proposal_id", "choice"}:
        return Reason.INVALID_PAYLOAD

    gov = _gov_params(params)
    if not gov["enabled"]:
        return Reason.GOVERNANCE_DISABLED

    proposal_id = payload.get("proposal_id")
    proposal = state.proposals.get(proposal_id)
    if proposal is None:
        return Reason.PROPOSAL_NOT_FOUND
    if proposal["status"] != "open":
        return Reason.VOTE_WINDOW_CLOSED
    if tx.tick > proposal["closes_tick"]:
        return Reason.VOTE_WINDOW_CLOSED

    if payload.get("choice") not in ("for", "against"):
        return Reason.INVALID_CHOICE

    if tx.sender in proposal["ballots"]:
        return Reason.ALREADY_VOTED  # one person, one vote — constitutional core #4

    return None


def _apply_vote(state: WorldState, tx: Transaction) -> dict[str, Any]:
    proposal = state.proposals[tx.payload["proposal_id"]]
    proposal["ballots"][tx.sender] = tx.payload["choice"]

    return {
        "tick": tx.tick,
        "sender": tx.sender,
        "action": "VOTE",
        "proposal_id": tx.payload["proposal_id"],
        "choice": tx.payload["choice"],
    }


def _validate_rollback(state: WorldState, tx: Transaction, params: dict[str, Any]) -> Reason | None:
    payload = tx.payload

    if tx.sender not in state.balances:
        return Reason.UNKNOWN_SENDER

    if not isinstance(payload, dict) or set(payload.keys()) != {"target_version"}:
        return Reason.INVALID_PAYLOAD

    gov = _gov_params(params)
    if not gov["enabled"]:
        return Reason.GOVERNANCE_DISABLED

    target = payload.get("target_version")
    if not _is_int(target):
        return Reason.INVALID_PAYLOAD

    target_doc = next((rs for rs in state.rulesets if rs["version"] == target), None)
    if target_doc is None:
        return Reason.TARGET_VERSION_NOT_FOUND
    if target == max(rs["version"] for rs in state.rulesets):
        return Reason.TARGET_VERSION_NOT_FOUND  # rolling back to the active version is meaningless

    # Constitutional guard: rollback target must not predate governance-on
    if not _gov_params(target_doc["params"])["enabled"] and _gov_params(params)["enabled"]:
        return Reason.CONSTITUTIONAL_GUARD

    return None


def _apply_rollback(state: WorldState, tx: Transaction, params: dict[str, Any]) -> dict[str, Any]:
    gov = _gov_params(params)
    target = tx.payload["target_version"]
    target_doc = next(rs for rs in state.rulesets if rs["version"] == target)

    proposal_id = f"p{state.next_proposal_id}"
    state.next_proposal_id += 1

    state.proposals[proposal_id] = {
        "proposal_id": proposal_id,
        "proposer": tx.sender,
        "params": dict(target_doc["params"]),
        "activation_tick": tx.tick + gov["vote_window_ticks"] + 1,
        "opened_tick": tx.tick,
        "closes_tick": tx.tick + gov["vote_window_ticks"],
        "ballots": {},
        "status": "open",
        "is_rollback": True,
        "target_version": target,
        "change_tx_hash": tx.content_hash(),
    }

    return {
        "tick": tx.tick,
        "sender": tx.sender,
        "action": "ROLLBACK",
        "proposal_id": proposal_id,
        "target_version": target,
        "closes_tick": tx.tick + gov["vote_window_ticks"],
    }


def _is_constitutional(proposal_params: dict[str, Any], active_params: dict[str, Any]) -> bool:
    """Constitutional matters: changing the voting rules themselves, the
    oversight council, or the constitution phase. These require 2/3 of
    ALL citizens (Stage 1: blocks majority capture via strategic votes —
    proven necessary by the faction-capture experiment)."""
    if proposal_params.get("governance") != active_params.get("governance"):
        return True
    new_council = (proposal_params.get("oversight") or {}).get("council_members")
    old_council = (active_params.get("oversight") or {}).get("council_members")
    if new_council != old_council:
        return True
    if proposal_params.get("constitution_phase") != active_params.get("constitution_phase"):
        return True
    return False




def _input_advance_phase(state: WorldState, tick: int, params: dict[str, Any]) -> list[dict[str, Any]]:
    """Emergency input advance (Stage 4 insolvency fix).

    A PROVEN producer (has produced before) that cannot afford its
    cheapest runnable recipe's inputs is deadlocked: no inputs -> no
    output -> no income -> never able to buy inputs again (observed:
    dairy/tailors/school frozen broke while citizens went unmet).
    Society advances the shortfall from the surplus pool — social
    investment in production capacity, the model's "surpluses return
    to society" made executable.

    Booked as a pool->treasury transfer: the money invariant stays
    exact. Deterministic: sorted coop ids. Inert without the rule key
    (replay compat).
    """
    cb = params.get("capital_backstop") or {}
    ia = cb.get("input_advance")
    interval = cb.get("interval_ticks", 0)
    if not isinstance(ia, dict) or interval <= 0 or tick % interval != 0:
        return []
    max_per = ia.get("max_per_coop", 0)
    if max_per <= 0:
        return []

    # shared PRODUCE-history cache with the capital backstop
    cache = _state_cache(state)
    scanned, recipe_map = cache[0], cache[1]
    if len(state.applied) > scanned:
        for e in state.applied[scanned:]:
            if e.get("action") == "PRODUCE":
                recipe_map.setdefault(e.get("coop_id"), set()).add(e.get("recipe_id"))
        cache[0] = len(state.applied)

    events: list[dict[str, Any]] = []

    def _advance_rank(cid: str) -> tuple[int, str]:
        # Unproven coops with a DECLARED trade deadlock hardest (no inputs
        # -> no output -> no history -> never proven): they go FIRST when
        # the pool is scarce (bootstrap pool ~0 starved late-alphabet
        # founders; observed: printshop treasury 5, fabric 14cr, zero bids
        # in 300 ticks). Proven producers have income paths — they wait.
        if cid not in recipe_map:
            intent = state.coops[cid].get("recipe_intent")
            if isinstance(intent, str) and intent in state.recipes:
                return (0, cid)
        return (1, cid)

    for coop_id in sorted(state.coops.keys(), key=_advance_rank):
        coop = state.coops[coop_id]
        rids = sorted(recipe_map.get(coop_id, ()))
        if not rids:
            # First-run advance: an unproven coop with a DECLARED trade
            # (recipe_intent at founding) gets its first run's inputs
            # advanced — otherwise it deadlocks before its first harvest.
            intent = coop.get("recipe_intent")
            if isinstance(intent, str) and intent in state.recipes:
                rids = [intent]
            else:
                continue
        # cheapest runnable recipe's input cost. Cost is priced at the
        # CURRENT LISTING FLOORS (what the coop would actually pay on the
        # market), falling back to the book baseline when nothing is
        # listed. A book-baseline-only estimate understated fabric at 4
        # while real floors were 14 — the founder got a 5cr advance it
        # could never spend, then `treasury >= best` skipped it forever
        # (observed: printshop pinned at exactly 5 for 1,000 ticks,
        # books never produced).
        best: int | None = None
        for rid in rids:
            recipe = state.recipes.get(rid)
            if not recipe:
                continue
            # state.recipes entries are plain dicts
            inputs = recipe.get("inputs") if isinstance(recipe, dict) else getattr(recipe, "inputs", None)
            if not inputs:
                continue
            cost = 0
            for g, q in sorted(inputs.items()):
                # The advance must cover the price the bot actually bids
                # (sim.py: baseline + 2). This phase runs AFTER clearing,
                # when listings are stripped, so floor lookups see nothing
                # — pricing at baseline left printshop 5cr vs a 6cr bid,
                # a permanent deadlock (books never produced, 1,000 ticks).
                unit = state.good_cost_baseline.get(g, 1) + 2
                cost += unit * q
            if best is None or cost < best:
                best = cost
        if best is None or best <= 0:
            continue
        treasury = coop.get("treasury", 0)
        if treasury >= best:
            continue
        shortfall = min(best - treasury, max_per)
        if shortfall <= 0 or state.surplus_pool < shortfall:
            continue
        state.surplus_pool -= shortfall
        coop["treasury"] = treasury + shortfall
        events.append({
            "tick": tick,
            "action": "INPUT_ADVANCE",
            "coop_id": coop_id,
            "amount": shortfall,
            "run_cost": best,
        })
    return events


def _state_cache(state: WorldState) -> list:
    """Per-state PRODUCE-history cache: [scanned_len, {coop: rids}, equipped].

    Attached to the state object itself — NOT keyed by id(state): CPython
    reuses ids of garbage-collected states, which gave fresh loaded states
    a stale scanned-count (save/load hash mismatch). Rebuilt lazily from
    applied history after load; deterministic.
    """
    cache = getattr(state, "_backstop_cache", None)
    if cache is None:
        cache = [0, {}, set()]
        try:
            object.__setattr__(state, "_backstop_cache", cache)
        except AttributeError:
            state._backstop_cache = cache
    return cache


def _capital_backstop_phase(state: WorldState, tick: int, params: dict[str, Any]) -> list[dict[str, Any]]:
    """Society's last-resort capital maintenance (Stage 3 deadlock fix).

    A producer co-op that lacks recipe-required tools/machines AND cannot
    afford the market price is structurally deadlocked: no capital -> no
    output -> no income -> never able to buy capital (observed: miners
    frozen at treasury == machine floor forever). Society owns the means
    of production, so the capital fund (earmarked machine/tool rent)
    provides the replacement directly.

    Booked as retirement: credits leave the capital fund and leave supply,
    keeping the money invariant exact. Deterministic: sorted coop ids.
    Inert without the rule param (replay compat).
    """
    cb = params.get("capital_backstop") or {}
    interval = cb.get("interval_ticks", 0)
    if interval <= 0 or tick % interval != 0:
        return []

    # Which recipes has each coop ACTUALLY run? Derived from applied
    # history (deterministic), cached outside state so state hashes and
    # replays stay byte-identical. Only proven production counts: a coop
    # whose recipes never need machines must not receive them free.
    cache = _state_cache(state)
    scanned, recipe_map = cache[0], cache[1]
    if len(state.applied) > scanned:
        for e in state.applied[scanned:]:
            if e.get("action") == "PRODUCE":
                recipe_map.setdefault(e.get("coop_id"), set()).add(e.get("recipe_id"))
        cache[0] = len(state.applied)

    # Founding equipment grant: society owns the means of production,
    # so a worker coop with ZERO production history is equipped ONCE
    # with its trade's capital — otherwise it deadlocks before its
    # first shift (no tools -> no output -> no history -> never proven).
    # Recipe intent is inferred deterministically: the recipe whose
    # NON-capital inputs intersect the coop's held stock (a founded
    # quarry holds water+electricity -> matches sand_extraction).
    # One-time per coop, booked as retirement from the capital fund.
    fe_on = bool(cb.get("founding_equipment"))
    while len(cache) < 3:
        cache.append(set())
    equipped: set[str] = cache[2]

    events: list[dict[str, Any]] = []
    for coop_id in sorted(state.coops.keys()):
        coop = state.coops[coop_id]
        inv = coop.get("inventory", {})
        if fe_on and coop_id not in equipped and not recipe_map.get(coop_id):
            held_goods = {g for g, q in inv.items() if q > 0}
            # declared trade wins; heuristic fallback otherwise
            intent = coop.get("recipe_intent")
            target_rid = intent if intent in state.recipes else None
            if target_rid is None:
                for rid in sorted(state.recipes.keys()):
                    recipe = state.recipes[rid]
                    ins = recipe.get("inputs") if isinstance(recipe, dict) else getattr(recipe, "inputs", None)
                    outs = recipe.get("outputs") if isinstance(recipe, dict) else getattr(recipe, "outputs", None)
                    if not ins or not outs:
                        continue
                    non_capital = {g for g in ins if g not in ("hand_tools", "machines")}
                    if non_capital & held_goods:
                        target_rid = rid
                        break
            if target_rid:
                recipe = state.recipes[target_rid]
                ins = recipe.get("inputs") if isinstance(recipe, dict) else getattr(recipe, "inputs", None)
                gave = False
                for g in sorted(ins):
                    if g not in ("hand_tools", "machines"):
                        continue
                    q = ins[g]
                    book = {"hand_tools": 25, "machines": 150}.get(g, 1)
                    total = book * q
                    cf = getattr(state, "capital_fund", 0)
                    if cf >= total:
                        state.capital_fund -= total
                        state.money_retired += total
                        inv[g] = inv.get(g, 0) + q
                        gave = True
                        events.append({
                            "tick": tick,
                            "action": "FOUNDING_EQUIPMENT",
                            "coop_id": coop_id,
                            "good": g,
                            "qty": q,
                            "book_value": total,
                        })
                if gave:
                    equipped.add(coop_id)
                    continue
        # capital goods required by the recipes THIS coop actually runs
        required: dict[str, int] = {}
        for rid in sorted(recipe_map.get(coop_id, ())):
            recipe = state.recipes.get(rid)
            if not recipe:
                continue
            for good in ("hand_tools", "machines"):
                q = recipe.get("inputs", {}).get(good, 0)
                if q > 0:
                    required[good] = max(required.get(good, 0), q)
        if not required:
            continue
        gave: dict[str, int] = {}
        cost = 0
        for good in sorted(required.keys()):
            need = required[good] - inv.get(good, 0)
            if need <= 0:
                continue
            price = state.good_cost_baseline.get(good, 1) + 1
            # deadlock signature: cannot afford even one unit on the market
            if coop.get("treasury", 0) >= price:
                continue
            while need > 0 and state.capital_fund >= price:
                state.capital_fund -= price
                state.money_retired += price
                inv[good] = inv.get(good, 0) + 1
                cost += price
                need -= 1
                gave[good] = gave.get(good, 0) + 1
        if gave:
            events.append({
                "tick": tick,
                "action": "CAPITAL_BACKSTOP",
                "coop_id": coop_id,
                "gave": gave,
                "cost": cost,
                "fund_after": state.capital_fund,
            })
    return events


def _settle_proposals(state: WorldState, tick: int, params: dict[str, Any], ledger: Ledger) -> list[dict[str, Any]]:
    """End-of-tick proposal tally. Deterministic (spec §6)."""
    events: list[dict[str, Any]] = []
    if not state.proposals:
        return events

    gov = _gov_params(params)
    citizens = len(state.balances)
    quorum_needed = -(-citizens * gov["quorum_bp"] // 10_000)  # ceil
    hardened = params.get("constitution_phase") == "hardened"
    active_version_doc = next(rs for rs in state.rulesets if rs["version"] == max(r["version"] for r in state.rulesets if r["activated_at"] <= tick))
    trial_end = active_version_doc["activated_at"] + gov["trial_period_ticks"]

    for proposal_id in sorted(state.proposals.keys()):
        proposal = state.proposals[proposal_id]
        if proposal["status"] != "open" or tick < proposal["closes_tick"]:
            continue

        ballots = proposal["ballots"]
        if _delegation_enabled(params):
            # A3: delegated citizens vote through their (resolvable) delegate
            ballots = expand_ballots(state, ballots)
        cast = len(ballots)
        votes_for = sum(1 for c in ballots.values() if c == "for")
        votes_against = cast - votes_for

        passed = False
        constitutional = (
            proposal.get("intervention") is None
            and _is_constitutional(proposal["params"], params)
        )
        if cast >= quorum_needed and cast > 0:
            # Asymmetric recovery (§6.3): rollback inside the trial period
            # of the active version needs only a simple majority.
            in_trial_rollback = proposal["is_rollback"] and tick <= trial_end
            if in_trial_rollback:
                passed = votes_for > votes_against
            elif constitutional:
                # 2/3 of ALL citizens — not just cast. Strategic abstention
                # cannot lower the bar for changing the rules of voting.
                passed = votes_for * 3 >= citizens * 2
            elif hardened:
                passed = votes_for * 3 >= cast * 2  # >= 2/3 of cast
            else:
                passed = votes_for > votes_against  # strict majority; tie fails

        if passed:
            proposal["status"] = "passed"
            if proposal.get("intervention") is not None:
                executed = _execute_intervention(state, tick, params, proposal)
                events.append({
                    "tick": tick,
                    "action": "INTERVENTION_EXECUTED",
                    "proposal_id": proposal_id,
                    "votes_for": votes_for,
                    "votes_against": votes_against,
                    "executed": executed,
                })
                continue
            next_version = max(rs["version"] for rs in state.rulesets) + 1
            doc = RuleSetDoc(
                version=next_version,
                params=proposal["params"],
                activated_at=max(proposal["activation_tick"], tick + 1),
                change_tx_hash=proposal["change_tx_hash"],
            )
            state.rulesets.append(doc.to_dict())
            events.append({
                "tick": tick,
                "action": "PROPOSAL_SETTLED",
                "proposal_id": proposal_id,
                "result": "passed",
                "new_version": next_version,
                "activated_at": doc.activated_at,
                "votes_for": votes_for,
                "votes_against": votes_against,
                "is_rollback": proposal["is_rollback"],
                "constitutional": constitutional,
            })
        else:
            proposal["status"] = "failed"
            events.append({
                "tick": tick,
                "action": "PROPOSAL_SETTLED",
                "proposal_id": proposal_id,
                "result": "failed",
                "votes_for": votes_for,
                "votes_against": votes_against,
                "constitutional": constitutional,
            })

    return events



# -------------------------------------------------------------- OVERSIGHT


def _ov_params(params: dict[str, Any]) -> dict[str, Any]:
    ov = params.get("oversight") or {}
    return {
        "hoard_multiplier": ov.get("hoard_multiplier", 3),
        "market_power_share_bp": ov.get("market_power_share_bp", 7_000),
        "free_rider_min_hours": ov.get("free_rider_min_hours", 5),
        "council_members": list(ov.get("council_members", [])),
    }


def _detect_anomalies(state: WorldState, tick: int, params: dict[str, Any], listings_snapshot: dict[str, list[dict[str, Any]]] | None = None) -> list[dict[str, Any]]:
    """Deterministic anomaly detection — spec §6.4. Public, append-only flags.

    MARKET_POWER reads `listings_snapshot` (captured BEFORE clearing) —
    clearing empties state.listings, but dominance must still be detected.
    """
    events: list[dict[str, Any]] = []
    ov = _ov_params(params)
    quotas = params.get("essential_need_quota", {})
    listings = listings_snapshot if listings_snapshot is not None else state.listings
    flagged = {(f["kind"], f["target"], f.get("good", "")) for f in state.flags}

    for citizen in sorted(state.citizen_inventory.keys()):
        for good in sorted(state.citizen_inventory[citizen].keys()):
            quota = quotas.get(good, 0)
            held = state.citizen_inventory[citizen][good]
            if quota > 0 and held > ov["hoard_multiplier"] * quota:
                key = ("HOARD", citizen, good)
                if key not in flagged:
                    flag = {"tick": tick, "kind": "HOARD", "target": citizen, "good": good,
                            "held": held, "threshold": ov["hoard_multiplier"] * quota}
                    state.flags.append(flag)
                    events.append({"tick": tick, "action": "OVERSIGHT_FLAG", **flag})

    for good in sorted(listings.keys()):
        entries = [e for e in listings[good] if e["qty"] > 0]
        total = sum(e["qty"] for e in entries)
        if total <= 0:
            continue
        by_coop: dict[str, int] = {}
        for e in entries:
            by_coop[e["coop_id"]] = by_coop.get(e["coop_id"], 0) + e["qty"]
        # Dominance only means something with competition to dominate:
        # with a single producer per good (baseline structure), 100% share
        # is structural, not abuse. Require >= 2 listing coops.
        if len(by_coop) < 2:
            continue
        # Structural dominance floor (realism pack): with n producers the
        # structural share of the largest is 1/n — flagging a coop near it
        # is noise (a healthy n=2 split is 50/50; a single producer is
        # structural and already skipped above). Behavioral dominance =
        # exceeding the LARGER of the configured share (70% default) or
        # structural + 15pp, so the bar rises as producer count shrinks.
        _n = len(by_coop)
        _structural_bp = 10_000 // _n
        _threshold_bp = max(ov["market_power_share_bp"], _structural_bp + 1_500)
        for coop_id in sorted(by_coop.keys()):
            if by_coop[coop_id] * 10_000 > _threshold_bp * total:
                key = ("MARKET_POWER", coop_id, good)
                if key not in flagged:
                    flag = {"tick": tick, "kind": "MARKET_POWER", "target": coop_id, "good": good,
                            "share_bp": by_coop[coop_id] * 10_000 // total, "threshold_bp": _threshold_bp}
                    state.flags.append(flag)
                    events.append({"tick": tick, "action": "OVERSIGHT_FLAG", **flag})

    for citizen in sorted(state.citizen_inventory.keys()):
        hours = state.labor_hours.get(citizen, 0)
        if hours < ov["free_rider_min_hours"] and state.citizen_inventory[citizen]:
            key = ("FREE_RIDER", citizen, "")
            if key not in flagged:
                flag = {"tick": tick, "kind": "FREE_RIDER", "target": citizen,
                        "hours": hours, "threshold": ov["free_rider_min_hours"]}
                state.flags.append(flag)
                events.append({"tick": tick, "action": "OVERSIGHT_FLAG", **flag})

    return events


def _validate_intervene(state: WorldState, tx: Transaction, params: dict[str, Any]) -> Reason | None:
    payload = tx.payload

    if tx.sender not in state.balances:
        return Reason.UNKNOWN_SENDER

    gov = _gov_params(params)
    if not gov["enabled"]:
        return Reason.GOVERNANCE_DISABLED

    ov = _ov_params(params)
    if tx.sender not in ov["council_members"]:
        return Reason.NOT_COUNCIL_MEMBER

    if not isinstance(payload, dict) or set(payload.keys()) != {"intervention"}:
        return Reason.INVALID_PAYLOAD

    iv = payload.get("intervention")
    if not isinstance(iv, dict) or "type" not in iv:
        return Reason.INVALID_INTERVENTION

    itype = iv["type"]
    if itype == "DISSOLVE_HOARD":
        if set(iv.keys()) != {"type", "target", "good"}:
            return Reason.INVALID_INTERVENTION
        if iv["target"] not in state.balances:
            return Reason.UNKNOWN_CITIZEN
        if iv["good"] not in state.goods:
            return Reason.GOOD_UNKNOWN
    elif itype == "FINE":
        if set(iv.keys()) != {"type", "target", "amount"}:
            return Reason.INVALID_INTERVENTION
        if iv["target"] not in state.balances:
            return Reason.UNKNOWN_CITIZEN
        amount = iv["amount"]
        if not _is_int(amount) or amount <= 0:
            return Reason.INVALID_INTERVENTION
    elif itype == "EMERGENCY_TRIAGE":
        if set(iv.keys()) != {"type", "good"}:
            return Reason.INVALID_INTERVENTION
        if iv["good"] not in state.goods:
            return Reason.GOOD_UNKNOWN
    else:
        return Reason.INTERVENTION_TYPE_UNKNOWN

    return None


def _apply_intervene(state: WorldState, tx: Transaction, params: dict[str, Any]) -> dict[str, Any]:
    gov = _gov_params(params)
    proposal_id = f"p{state.next_proposal_id}"
    state.next_proposal_id += 1

    state.proposals[proposal_id] = {
        "proposal_id": proposal_id,
        "proposer": tx.sender,
        "params": None,
        "intervention": dict(tx.payload["intervention"]),
        "activation_tick": tx.tick + gov["vote_window_ticks"] + 1,
        "opened_tick": tx.tick,
        "closes_tick": tx.tick + gov["vote_window_ticks"],
        "ballots": {},
        "status": "open",
        "is_rollback": False,
        "target_version": None,
        "change_tx_hash": tx.content_hash(),
    }

    return {
        "tick": tx.tick,
        "sender": tx.sender,
        "action": "INTERVENE",
        "proposal_id": proposal_id,
        "intervention": dict(tx.payload["intervention"]),
        "closes_tick": tx.tick + gov["vote_window_ticks"],
    }


def _execute_intervention(state: WorldState, tick: int, params: dict[str, Any], proposal: dict[str, Any]) -> dict[str, Any]:
    """Execute a passed intervention. Exact conservation throughout."""
    iv = proposal["intervention"]
    itype = iv["type"]
    quotas = params.get("essential_need_quota", {})
    ov = _ov_params(params)

    if itype == "DISSOLVE_HOARD":
        target, good = iv["target"], iv["good"]
        held = state.citizen_inventory.get(target, {}).get(good, 0)
        allowed = ov["hoard_multiplier"] * quotas.get(good, 0)
        excess = max(0, held - allowed)
        if excess > 0:
            state.citizen_inventory[target][good] = held - excess
            state.common_pool[good] = state.common_pool.get(good, 0) + excess
        return {"type": itype, "target": target, "good": good, "excess_moved": excess, "to": "common_pool"}

    if itype == "FINE":
        target, amount = iv["target"], iv["amount"]
        payable = min(amount, state.balances.get(target, 0))
        if payable > 0:
            state.balances[target] -= payable
            state.surplus_pool += payable
        return {"type": itype, "target": target, "fined": payable, "to": "surplus_pool"}

    if itype == "EMERGENCY_TRIAGE":
        good = iv["good"]
        next_version = max(rs["version"] for rs in state.rulesets) + 1
        new_params = {}
        for k, v in params.items():
            if isinstance(v, dict):
                new_params[k] = dict(v)
            elif isinstance(v, list):
                new_params[k] = list(v)
            else:
                new_params[k] = v
        new_params["triage_overrides"] = dict(params.get("triage_overrides", {}))
        new_params["triage_overrides"][good] = "emergency"
        doc = RuleSetDoc(
            version=next_version,
            params=new_params,
            activated_at=tick + 1,
            change_tx_hash=proposal["change_tx_hash"],
        )
        state.rulesets.append(doc.to_dict())
        return {"type": itype, "good": good, "new_version": next_version, "activated_at": tick + 1}

    return {"type": itype, "error": "unknown"}


def _validate_crisis_vote(state: WorldState, tx: Transaction, params: dict[str, Any]) -> Reason | None:
    payload = tx.payload
    if tx.sender not in state.balances:
        return Reason.UNKNOWN_SENDER
    if not isinstance(payload, dict) or set(payload.keys()) != {"in_favor"}:
        return Reason.INVALID_PAYLOAD
    if not isinstance(payload["in_favor"], bool):
        return Reason.INVALID_PAYLOAD
    from . import crisis as _crisis
    c = getattr(state, "crisis", None)
    if not c or not c.get("active"):
        return Reason.INVALID_PAYLOAD  # no crisis to vote on
    return None


def _apply_crisis_vote(state: WorldState, tx: Transaction) -> dict[str, Any]:
    from . import crisis as _crisis
    _crisis.tally_crisis_vote(state, tx.sender, bool(tx.payload["in_favor"]))
    return {
        "tick": tx.tick, "sender": tx.sender, "action": "CRISIS_VOTE",
        "in_favor": bool(tx.payload["in_favor"]),
    }


def _research_phase_safe(state: WorldState, tick: int, params: dict[str, Any]) -> list[dict[str, Any]]:
    """Research funding phase (Stage 5). Inert without params['research']."""
    from .research import fund_pool_phase
    return fund_pool_phase(state, tick, params)  # crisis redirection lives in the vote cycle, not the tap


def apply_tick(
    state: WorldState,
    ledger: Ledger,
    actions: list[Transaction],
    *,
    current_tick: int | None = None,
) -> WorldState:
    """Process one tick's action batch deterministically.

    1. Resolve the active rule-set version for this tick (D7 pinning).
    2. Sort actions deterministically.
    3. Validate each under the active rules; accept or reject (both logged).
    4. Apply accepted actions; stamp state with tick + active version.
    """
    tick = state.tick + 1 if current_tick is None else current_tick

    # Ephemeral per-tick WORK counter: fresh every tick (never snapshotted).
    state.worked_hours_tick = {}

    # Version pinning: the version active for THIS tick, resolved from history
    from .rules import active_version

    version_for_tick = active_version(
        [RuleSetDoc.from_dict(rs) for rs in state.rulesets], tick
    )
    params = None
    for rs in state.rulesets:
        if rs["version"] == version_for_tick:
            params = rs["params"]
            break
    if params is None:  # pragma: no cover — defensive
        raise RuntimeError(f"ruleset v{version_for_tick} missing from state")

    # Stage 5 · shock lifecycle (rule-gated; absent => inert, replay-safe)
    from . import shocks as _shocks
    if (params.get("shocks") or {}).get("enabled"):
        seed_cfg = (params.get("shocks") or {}).get("rng_seed", 0)
        _rng = random.Random(f"{seed_cfg}:{tick}")
        _shocks.expire_finished(state, tick)
        _shocks.roll_shock(state, tick, _rng)

    # Stage 5 - demographics lifecycle (rule-gated; absent => inert,
    # replay-safe). Births + aging run before bots validate actions so a
    # newborn is never WORK-eligible in its birth tick, and before market
    # phases so child citizens receive dividends/consume from tick one.
    from . import demographics as _demog
    if (params.get("demographics") or {}).get("enabled"):
        demog_events = _demog.demographics_phase(state, tick, params)
        state.applied.extend(demog_events)

        credit_events = credit_phase(state, tick, params)
        state.applied.extend(credit_events)

    seen: set[str] = set()
    for tx in sorted(actions, key=Transaction.sort_key):
        if tx.tick != tick:
            ledger.reject(tx, Reason.MALFORMED_TRANSACTION)
            continue

        if tx.action not in SUPPORTED_ACTIONS:
            ledger.reject(tx, Reason.INVALID_PAYLOAD)
            continue

        # A transaction must be pinned to the version active for this tick.
        # RULE_CHANGE declares the CURRENT version it amends (it changes rules
        # from a strictly future tick, so it executes under today's rules).
        if tx.action == "RULE_CHANGE":
            if tx.ruleset_version != version_for_tick:
                ledger.reject(tx, Reason.RULESET_MISMATCH)
                continue
        elif tx.ruleset_version != version_for_tick:
            ledger.reject(tx, Reason.RULESET_MISMATCH)
            continue

        content_hash = tx.content_hash()
        if content_hash in seen:
            ledger.reject(tx, Reason.DUPLICATE_TRANSACTION)
            continue

        validator = {
            "TRANSFER": lambda t: _validate_transfer(state, t, params),
            "RULE_CHANGE": lambda t: _validate_rule_change(state, t, params),
            "FOUND_COOP": lambda t: _validate_found_coop(state, t, params),
            "JOIN_COOP": lambda t: _validate_join_coop(state, t, params),
            "LEAVE_COOP": lambda t: _validate_leave_coop(state, t, params),
            "WORK": lambda t: _validate_work(state, t, params),
            "PRODUCE": lambda t: _validate_produce(state, t, params),
            "LIST_GOOD": lambda t: _validate_list_good(state, t, params),
            "BID": lambda t: _validate_bid(state, t, params),
            "BID_FOR_COOP": lambda t: _validate_bid_for_coop(state, t, params),
            "BUY_ESSENTIAL": lambda t: _validate_buy_essential(state, t, params),
            "PROPOSE": lambda t: _validate_propose(state, t, params),
            "VOTE": lambda t: _validate_vote(state, t, params),
            "ROLLBACK": lambda t: _validate_rollback(state, t, params),
            "INTERVENE": lambda t: _validate_intervene(state, t, params),
            "CRISIS_VOTE": lambda t: _validate_crisis_vote(state, t, params),
            "CRISIS_VOTE": lambda t: _validate_crisis_vote(state, t, params),
            "LOAN": lambda t: _validate_loan(state, t, params),
            "REPAY": lambda t: _validate_repay(state, t, params),
            "DELEGATE": lambda t: _validate_delegate(state, t, params),
        }[tx.action]

        reason = validator(tx)
        if reason is not None:
            ledger.reject(tx, reason)
            continue

        seen.add(content_hash)
        ledger.accept(tx)
        if tx.action == "RULE_CHANGE":
            entry = _apply_rule_change(state, tx, ledger)
        elif tx.action == "FOUND_COOP":
            entry = _apply_found_coop(state, tx, params)
        elif tx.action == "WORK":
            entry = _apply_work(state, tx, params)
        elif tx.action == "PRODUCE":
            entry = _apply_produce(state, tx, params)
        elif tx.action == "PROPOSE":
            entry = _apply_propose(state, tx, params)
        elif tx.action == "ROLLBACK":
            entry = _apply_rollback(state, tx, params)
        elif tx.action == "INTERVENE":
            entry = _apply_intervene(state, tx, params)
        elif tx.action == "CRISIS_VOTE":
            entry = _apply_crisis_vote(state, tx)
        elif tx.action == "LOAN":
            entry = _apply_loan(state, tx, params)
        else:
            entry = {
                "TRANSFER": _apply_transfer,
                "JOIN_COOP": _apply_join_coop,
                "LEAVE_COOP": _apply_leave_coop,
                "LIST_GOOD": _apply_list_good,
                "BID": _apply_bid,
                "BID_FOR_COOP": _apply_bid_for_coop,
                "BUY_ESSENTIAL": _apply_buy_essential,
                "VOTE": _apply_vote,
                "REPAY": _apply_repay,
                "DELEGATE": _apply_delegate,
            }[tx.action](state, tx)
        state.applied.append(entry)

    # Listings snapshot for oversight: dominance exists while listed,
    # even though clearing empties state.listings afterwards (§6.4)
    listings_snapshot = {g: [dict(e) for e in ls] for g, ls in state.listings.items()}

    # End-of-tick market clearing (deterministic) — spec §9
    market_events = _clear_markets(state, tick, params, ledger)
    state.applied.extend(market_events)

    # Fixed supply: coops repay wage debt from the day's sales (D14).
    state.applied.extend(_wage_debt_repay_phase(state, tick, params))

    # Emergency input advance runs BEFORE dividends/services: a
    # deadlocked producer (no inputs -> no output -> no income) gets
    # first claim on the fresh pool, because restoring production
    # capacity is what generates future surplus. Running it last let
    # dividends drain the pool to zero first — founders starved on
    # scraps (observed: printshop got one 5cr advance in 600 ticks).
    state.applied.extend(_input_advance_phase(state, tick, params))

    # Circular flow: consumption, capital rent, then surplus spending
    # (deterministic). Inert phases when the ruleset lacks the params.
    consume_events = _consume_phase(state, tick, params)
    state.applied.extend(consume_events)
    spend_events = _surplus_spend_phase(state, tick, params)
    state.applied.extend(spend_events)

    # Stage 5 - research funding: society's innovation pool receives its
    # votable share of surplus each tick (rule-gated; inert by default).
    from . import research as _research
    research_events = _research_phase_safe(state, tick, params)
    state.applied.extend(research_events)

    # Patronage: co-op surplus above a buffer returns to members.
    coop_events = _coop_distribute_phase(state, tick, params)
    state.applied.extend(coop_events)

    # Progressive wealth tax: balances above the threshold pay a rate into
    # the surplus pool (recycled via dividends/services). Caps savings
    # concentration without touching subsistence balances.
    tax_events = _wealth_tax_phase(state, tick, params)
    state.applied.extend(tax_events)

    # Public capital maintenance: society replaces worn-out tools and
    # machines, paying replacement cost from the pool (and retiring it).
    refresh_events = _capital_refresh_phase(state, tick, params)
    state.applied.extend(refresh_events)

    # Capital backstop: society un-deadlocks producer co-ops that burned
    # their last machine and can never afford another (deterministic).
    backstop_events = _capital_backstop_phase(state, tick, params)
    state.applied.extend(backstop_events)

    # End-of-tick governance settlement (deterministic) — spec §6
    gov_events = _settle_proposals(state, tick, params, ledger)
    state.applied.extend(gov_events)

    # Stage 5 - crisis lifecycle: auto-declare on severe shocks, tally
    # ratification votes, enforce ratification window and max duration
    # (rule-gated; inert without params['crisis']).
    from . import crisis as _crisis_mod
    _crisis_mod.crisis_phase(state, tick, params)

    # End-of-tick oversight detection (deterministic) — spec §6.4
    ov_events = _detect_anomalies(state, tick, params, listings_snapshot)
    state.applied.extend(ov_events)

    state.tick = tick
    state.ruleset_version = version_for_tick
    return state
