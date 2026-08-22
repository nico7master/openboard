"""Bot archetypes — the D13 cast. Each bot is a deterministic decision
function: (state, params, tick, rng) -> list[Transaction].

Bots see only public state (radical transparency) and never touch engine
internals. Seeded rng keeps every run reproducible.
"""

from __future__ import annotations

import random
from typing import Any, Callable

from .state import WorldState
from .ledger import Transaction

DecisionFn = Callable[[str, WorldState, dict[str, Any], int, random.Random], list[Transaction]]


def _tx(tick: int, sender: str, action: str, payload: dict[str, Any], version: int) -> Transaction:
    return Transaction(tick=tick, sender=sender, action=action, payload=payload, ruleset_version=version)


def _work(tick, who, coop, hours, version):
    return _tx(tick, who, "WORK", {"coop_id": coop, "hours": hours}, version)


def _buy_essential(tick, who, good, qty, version):
    return _tx(tick, who, "BUY_ESSENTIAL", {"good": good, "qty": qty}, version)


def _bid(tick, who, good, max_price, qty, version):
    return _tx(tick, who, "BID", {"good": good, "max_price": max_price, "qty": qty}, version)


def _my_coop(state: WorldState, who: str) -> str | None:
    for cid, c in state.coops.items():
        if who in c["members"]:
            return cid
    return None


def _afford(state: WorldState, who: str, price: int, qty: int) -> bool:
    return state.balances.get(who, 0) >= price * qty


ESSENTIALS = ("bread", "water", "grain")


# ------------------------------------------------------------ archetypes


def honest_worker(who, state, params, tick, rng) -> list[Transaction]:
    """Work, buy essentials, modest market bids on food."""
    v = state.ruleset_version
    coop = _my_coop(state, who)
    out: list[Transaction] = []
    if coop is not None:
        _cap = params.get("labor_pool_cap")
        if _cap is None or state.coops[coop]["labor_pool_hours"] + 6 <= _cap:
            out.append(_work(tick, who, coop, 6, v))
    # modest market bid on food, only when pantry is low (no slow hoarding)
    held_bread = state.citizen_inventory.get(who, {}).get("bread", 0)
    floor = state.good_cost_baseline.get("bread", 3)
    if held_bread < 2 and _afford(state, who, floor + 2, 1) and rng.random() < 0.3:
        out.append(_bid(tick, who, "bread", floor + 2, 1, v))
    out.extend(personal_needs(who, state, params, tick))
    return out


def strategic_producer(who, state, params, tick, rng) -> list[Transaction]:
    """Work hard, produce when inputs allow, list the surplus."""
    v = state.ruleset_version
    coop = _my_coop(state, who)
    if coop is None:
        return []
    out = [_work(tick, who, coop, 8, v)]
    c = state.coops[coop]
    # produce if the coop has inputs and labor for its first recipe
    if c["labor_pool_hours"] >= 2:
        for rid, r in state.recipes.items():
            if all(c["inventory"].get(g, 0) >= q for g, q in r["inputs"].items()) and c["labor_pool_hours"] >= r["labor_hours"] and c["inventory"].get("electricity", 0) >= r["energy"]:
                out.append(_tx(tick, who, "PRODUCE", {"coop_id": coop, "recipe_id": rid, "runs": 1}, v))
                break
    # list surplus outputs (keep 5 units of anything)
    for g in sorted(c["inventory"].keys()):
        if g in ESSENTIALS and c["inventory"][g] > 15:
            out.append(_tx(tick, who, "LIST_GOOD", {"coop_id": coop, "good": g, "qty": c["inventory"][g] - 15}, v))
            break
    return out


def hoarder(who, state, params, tick, rng) -> list[Transaction]:
    """Minimal work, maximal essential buying every tick."""
    v = state.ruleset_version
    coop = _my_coop(state, who)
    out: list[Transaction] = []
    if coop is not None:
        out.append(_work(tick, who, coop, 2, v))
    quotas = params.get("essential_need_quota", {})
    for good in ("grain", "bread"):
        q = quotas.get(good, 0)
        floor = state.good_cost_baseline.get(good, 1)
        if q > 0 and _afford(state, who, floor, q):
            out.append(_buy_essential(tick, who, good, q, v))
    return out


def price_manipulator(who, state, params, tick, rng) -> list[Transaction]:
    """Wash-bid on own co-op's listings to inflate the clearing price."""
    v = state.ruleset_version
    coop = _my_coop(state, who)
    if coop is None:
        return []
    out: list[Transaction] = []
    c = state.coops[coop]
    # list something
    for g in sorted(c["inventory"].keys()):
        if c["inventory"][g] > 10:
            out.append(_tx(tick, who, "LIST_GOOD", {"coop_id": coop, "good": g, "qty": min(10, c["inventory"][g])}, v))
            break
    # wash pattern: personally bid far above floor on the good our co-op
    # produces (listings clear each tick, so target the produced good)
    for g in sorted(c["inventory"].keys()):
        floor = state.good_cost_baseline.get(g, 1)
        price = floor * 3
        if _afford(state, who, price, 1):
            out.append(_bid(tick, who, g, price, 1, v))
        break
    return out


def free_rider(who, state, params, tick, rng) -> list[Transaction]:
    """No work; consume essentials to quota."""
    v = state.ruleset_version
    out: list[Transaction] = []
    quotas = params.get("essential_need_quota", {})
    for good in ("bread", "grain", "water"):
        q = quotas.get(good, 0)
        floor = state.good_cost_baseline.get(good, 1)
        if q > 0 and _afford(state, who, floor, q):
            out.append(_buy_essential(tick, who, good, q, v))
    return out


def champion_voter(who, state, params, tick, rng) -> list[Transaction]:
    """Proposes self-serving rules (huge quotas for own benefit)."""
    v = state.ruleset_version
    gov = params.get("governance", {})
    if not gov.get("enabled") or tick % 20 != 0:
        return []
    new_params = {k: (dict(val) if isinstance(val, dict) else (list(val) if isinstance(val, list) else val)) for k, val in params.items()}
    quota = dict(params.get("essential_need_quota", {}))
    quota["bread"] = quota.get("bread", 4) * 10  # self-serving: inflate quotas
    quota["grain"] = quota.get("grain", 10) * 10
    new_params["essential_need_quota"] = quota
    return [_tx(tick, who, "PROPOSE", {"params": new_params, "activation_tick": tick + 6}, v)]


def crisis_turtle(who, state, params, tick, rng) -> list[Transaction]:
    """Panics when prices spike above 2x baseline; hoards broadly."""
    v = state.ruleset_version
    out: list[Transaction] = []
    last_bread_price = state.last_clearing.get("bread", state.good_cost_baseline.get("bread", 3))
    last_grain_price = state.last_clearing.get("grain", state.good_cost_baseline.get("grain", 3))
    spike = any(
        price > 2 * state.good_cost_baseline.get(good, 1)
        for good, price in (("bread", last_bread_price), ("grain", last_grain_price))
    )
    quotas = params.get("essential_need_quota", {})
    if spike:
        for good in ("bread", "grain", "water"):
            q = quotas.get(good, 0)
            floor = state.good_cost_baseline.get(good, 1)
            if q > 0 and _afford(state, who, floor, q):
                out.append(_buy_essential(tick, who, good, q, v))
    else:
        floor = state.good_cost_baseline.get("bread", 3)
        if _afford(state, who, floor + 1, 1):
            out.append(_buy_essential(tick, who, "bread", 1, v))
    return out


def collusive_faction(who, state, params, tick, rng, faction: set[str] | None = None) -> list[Transaction]:
    """Bloc-votes for faction proposals and corners a market."""
    v = state.ruleset_version
    out: list[Transaction] = []
    # bloc-vote: vote FOR every open proposal (faction discipline)
    for pid, pr in sorted(state.proposals.items()):
        if pr["status"] == "open" and who not in pr["ballots"] and tick <= pr["closes_tick"]:
            out.append(_tx(tick, who, "VOTE", {"proposal_id": pid, "choice": "for"}, v))
            break  # one vote per tick is enough
    # corner the bread market occasionally
    floor = state.good_cost_baseline.get("bread", 3)
    if tick % 7 == 0 and _afford(state, who, floor * 4, 4):
        out.append(_bid(tick, who, "bread", floor * 4, 4, v))
    return out


def gray_market_smuggler(who, state, params, tick, rng) -> list[Transaction]:
    """Abstains while prices exceed cost+50%; participates when fair."""
    v = state.ruleset_version
    floor = state.good_cost_baseline.get("bread", 3)
    # observe the last known market situation via listings presence
    bread_listed = bool(state.listings.get("bread"))
    if not bread_listed:
        return []
    if _afford(state, who, floor + 1, 1):
        return [_bid(tick, who, "bread", floor + 1, 1, v)]
    return []


def innovator(who, state, params, tick, rng) -> list[Transaction]:
    """Proposes efficiency rules; votes against capture."""
    v = state.ruleset_version
    gov = params.get("governance", {})
    out: list[Transaction] = []
    if gov.get("enabled"):
        for pid, pr in sorted(state.proposals.items()):
            if pr["status"] == "open" and who not in pr["ballots"] and tick <= pr["closes_tick"]:
                # vote against proposals that inflate quotas 5x (capture heuristic)
                quota = pr.get("params", {}) or {}
                inflating = quota.get("essential_need_quota", {}).get("bread", 0) > params.get("essential_need_quota", {}).get("bread", 4) * 5
                choice = "against" if inflating else "for"
                out.append(_tx(tick, who, "VOTE", {"proposal_id": pid, "choice": choice}, v))
                break
    if tick % 30 == 0 and gov.get("enabled"):
        new_params = {k: (dict(val) if isinstance(val, dict) else (list(val) if isinstance(val, list) else val)) for k, val in params.items()}
        new_params["energy_price"] = max(1, params.get("energy_price", 2) - 1)  # efficiency push
        out.append(_tx(tick, who, "PROPOSE", {"params": new_params, "activation_tick": tick + 6}, v))
    return out


ARCHETYPES: dict[str, DecisionFn] = {
    "honest_worker": honest_worker,
    "strategic_producer": strategic_producer,
    "hoarder": hoarder,
    "price_manipulator": price_manipulator,
    "free_rider": free_rider,
    "champion_voter": champion_voter,
    "crisis_turtle": crisis_turtle,
    "collusive_faction": collusive_faction,
    "gray_market_smuggler": gray_market_smuggler,
    "innovator": innovator,
}


def personal_needs(who, state, params, tick):
    """Buy this citizen's daily needs (circular flow): essentials via
    BUY_ESSENTIAL (quota-bounded), market goods via BID at floor+1.
    Buys only when holdings are below 2x the daily quota."""
    v = state.ruleset_version
    out = []
    needs = params.get("needs", {})
    inv = state.citizen_inventory.get(who, {})
    balance = state.balances.get(who, 0)
    for good in sorted(needs.keys()):
        quota = needs[good]
        if quota <= 0:
            continue
        held = inv.get(good, 0)
        if held >= 2 * quota:
            continue
        want = min(quota, 2 * quota - held)
        floor = state.good_cost_baseline.get(good, 1)
        triage = state.effective_triage(good) if good in state.goods else "market"
        if triage in ("essential", "emergency"):
            eq = params.get("essential_need_quota", {}).get(good, 0)
            qty = min(want, eq) if eq > 0 else 0
            if qty > 0 and balance >= floor * qty:
                out.append(_tx(tick, who, "BUY_ESSENTIAL", {"good": good, "qty": qty}, v))
        else:
            price = floor + 1
            if balance >= price * want:
                out.append(_tx(tick, who, "BID", {
                    "good": good, "max_price": price, "qty": want,
                }, v))
    return out
