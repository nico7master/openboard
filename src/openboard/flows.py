"""D9 game-style dashboard: flow data for the two living canvases.

- Living Flow Map: industry nodes (sized by production, colored by health)
  and supply-chain edges (from recipes), plus weather (active shocks).
- Circular Flow Stage: pool-to-pool money flows (wages, dividends,
  services, taxes, market sales) aggregated over a recent window.

Pure computation over state + recorded events; nothing here mutates.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any


def _coop_health(state, coop_id: str, coop: dict[str, Any]) -> str:
    """green = producing-capable; red = starved (declared trade, no hours)."""
    if not coop.get("recipe_intent"):
        return "off"
    if coop.get("labor_pool_hours", 0) > 0:
        return "ok"
    if coop.get("members"):
        return "starved"
    return "off"


def recent_events(run, window: int = 5) -> list[dict[str, Any]]:
    """Events from the last `window` ticks (from the run's batch record)."""
    s = run.state
    out: list[dict[str, Any]] = []
    for t in range(max(s.tick - window + 1, 1), s.tick + 1):
        out.extend(run.batches.get(t, []))
    return out


def industry_nodes(state, events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One node per coop-ish industry: production volume in the window."""
    produced: dict[str, int] = defaultdict(int)
    for ev in events:
        if ev.get("action") == "PRODUCE":
            for _good, qty in (ev.get("outputs") or {}).items():
                produced[ev.get("coop_id", "?")] += qty
    nodes = []
    for cid in sorted(state.coops.keys()):
        coop = state.coops[cid]
        nodes.append({
            "id": cid,
            "industry": coop.get("recipe_intent") or "unassigned",
            "members": len(coop.get("members") or []),
            "produced": produced.get(cid, 0),
            "health": _coop_health(state, cid, coop),
        })
    return nodes


def supply_edges(state) -> list[dict[str, Any]]:
    """Which industries feed which: recipe input -> producing industry."""
    # map good -> industries that produce it
    producers: dict[str, list[str]] = defaultdict(list)
    for cid, coop in sorted(state.coops.items()):
        rid = coop.get("recipe_intent")
        if not rid:
            continue
        rec = state.recipes.get(rid) or {}
        for good in (rec.get("outputs") or {}):
            producers[good].append(cid)
    edges = []
    seen: set[tuple[str, str, str]] = set()
    for cid in sorted(state.coops.keys()):
        coop = state.coops[cid]
        rid = coop.get("recipe_intent")
        if not rid:
            continue
        rec = state.recipes.get(rid) or {}
        for good in sorted((rec.get("inputs") or {}).keys()):
            for src in producers.get(good, []):
                key = (src, cid, good)
                if src != cid and key not in seen:
                    seen.add(key)
                    edges.append({"from": src, "to": cid, "good": good})
    return edges


def pool_flows(state, events: list[dict[str, Any]]) -> dict[str, int]:
    """Money moved per channel in the window (for the Circular Flow Stage)."""
    flows = {"wages": 0, "dividends": 0, "services": 0, "taxes": 0,
             "market_sales": 0, "loans": 0, "production_value": 0}
    for ev in events:
        a = ev.get("action")
        if a == "PRODUCE":
            flows["production_value"] += ev.get("capital_rent_paid", 0) or 0
        elif a == "COOP_DISTRIBUTE":
            flows["dividends"] += ev.get("total", 0) or 0
        elif a == "MARKET_CLEAR_ESSENTIAL":
            flows["market_sales"] += sum(
                (r.get("cost", 0) or 0) for r in (ev.get("buyers") or [])
            )
        elif a == "LOAN":
            flows["loans"] += ev.get("amount", 0) or 0
        elif a == "WEALTH_TAX":
            flows["taxes"] += ev.get("collected", 0) or 0
    return flows


def population_ring(state) -> dict[str, Any]:
    """Citizens' needs satisfaction for the map's population ring."""
    total = len(state.balances)
    unmet = sum(1 for needs in state.unmet_needs.values()
                if any((v or 0) > 0 for v in needs.values()))
    return {"total": total, "unmet": unmet,
            "met_share": 100 - (100 * unmet // max(total, 1))}


def weather(state) -> list[dict[str, Any]]:
    return [{"kind": s.get("kind"), "intensity": s.get("intensity", 0),
             "ticks_left": max(s.get("until_tick", 0) - state.tick, 0)}
            for s in state.active_shocks]


def build_flows(run) -> dict[str, Any]:
    state = run.state
    events = recent_events(run)
    return {
        "tick": state.tick,
        "nodes": industry_nodes(state, events),
        "edges": supply_edges(state),
        "pools": pool_flows(state, events),
        "population": population_ring(state),
    }
