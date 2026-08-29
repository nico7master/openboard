"""D9 game-style dashboard: the story brain.

Turns live engine state into plain-language story cards with chart series.
Pure presentation logic: reads state, never mutates it. Severity classes
drive color: good / watch / bad / info.
"""
from __future__ import annotations

from typing import Any


def _trend(series: list, lookback: int = 4) -> str:
    if len(series) < 4:
        return "→"
    recent = series[-lookback:]
    avg_old = sum(recent[:2]) / 2
    avg_new = sum(recent[2:]) / 2
    if avg_old == 0:
        return "→"
    if avg_new > avg_old * 1.02:
        return "▲"
    if avg_new < avg_old * 0.98:
        return "▼"
    return "→"


def _trend_word(arrow: str) -> str:
    return {"▲": "rising", "▼": "falling", "→": "steady"}.get(arrow, "steady")


def _gini_bp(values: list[int]) -> int:
    from .metrics import gini
    return gini(values)


def economy_health_card(state, timeline) -> dict:
    """How well are everyone's needs being met today?"""
    unmet_citizens = sum(
        1 for needs in state.unmet_needs.values()
        if any((v or 0) > 0 for v in needs.values())
    )
    total = max(len(state.balances), 1)
    met_share = 100 - (100 * unmet_citizens // total)
    unmet_series = [x or 0 for x in (timeline.get("unmet") or [])]
    if met_share >= 95:
        sev, icon, word = "good", "🟢", "healthy"
    elif met_share >= 80:
        sev, icon, word = "watch", "🟡", "straining"
    else:
        sev, icon, word = "bad", "🔴", "hurting"
    return {
        "id": "economy_health", "icon": icon, "severity": sev,
        "sentence": f"The economy is {word}: {met_share}% of people got everything they needed today.",
        "series": unmet_series_of(timeline),
        "series_label": "people with unmet needs (lower is better)",
        "trend": _trend(unmet_series_of(timeline)),
        "detail": "needs",
    }


def unmet_series_of(timeline) -> list:
    return [x or 0 for x in (timeline.get("unmet") or [])]


def shortage_card(state, timeline) -> dict:
    """The worst chronic shortage, in human terms."""
    per_good_n: dict[str, int] = {}
    per_good_streak: dict[str, int] = {}
    for _cit, streaks in state.unmet_needs.items():
        for good, t in streaks.items():
            if (t or 0) > 0:
                per_good_n[good] = per_good_n.get(good, 0) + 1
                per_good_streak[good] = max(per_good_streak.get(good, 0), int(t or 0))
    if not per_good_streak:
        worst_good, worst_n, worst_streak = None, 0, 0
    else:
        worst_good = max(sorted(per_good_streak),
                         key=lambda g: (per_good_streak[g], per_good_n.get(g, 0)))
        worst_n = per_good_n.get(worst_good, 0)
        worst_streak = per_good_streak[worst_good]
    if worst_good is None:
        return {"id": "shortage", "icon": "🛒", "severity": "good",
                "sentence": "Shop shelves are stocked — everyone could buy what they needed.",
                "series": unmet_series_of(timeline)[-60:], "series_label": "unmet purchases"}
    sev = "bad" if worst_streak >= 20 else "watch"
    return {"id": "shortage", "icon": "⚠️", "severity": sev,
            "sentence": f"{worst_n} people couldn't buy {worst_good} — going on {worst_streak} ticks",
            "series": unmet_series_of(timeline)[-60:],
            "series_label": f"unmet {worst_good}",
            "detail": f"good:{worst_good}"}


def inequality_card(state, timeline) -> dict:
    g = [x or 0 for x in (timeline.get("gini") or [])]
    arrow = _trend(g)
    g_bp = _gini_bp(list(state.balances.values()))
    if g_bp < 2500:
        sev, icon = "good", "⚖️"
    elif g_bp < 4000:
        sev, icon = "watch", "⚖️"
    else:
        sev, icon = "bad", "🚨"
    if g_bp >= 2500:
        sentence = f"Inequality is {_trend_word(arrow)} — wealth is concentrating ({g_bp / 100:.1f}% of maximum)"
    else:
        sentence = f"Wealth is shared quite evenly ({_trend_word(arrow)})."
    return {"id": "inequality", "icon": icon, "severity": sev,
            "sentence": sentence, "series": g[-60:],
            "series_label": "inequality over time"}


def idle_production_card(state) -> dict:
    """Coops that declared a trade but have no members working (starved)."""
    idle = []
    for cid, coop in sorted(state.coops.items()):
        if not coop.get("recipe_intent"):
            continue
        if coop.get("labor_pool_hours", 0) <= 0 and coop.get("members"):
            idle.append((cid, coop["recipe_intent"]))
    if not idle:
        return {"id": "idle", "icon": "🏭", "severity": "good",
                "sentence": "Every workshop has what it needs to produce."}
    names = ", ".join(f"{t}" for _c, t in idle[:3])
    more = f" and {len(idle) - 3} more" if len(idle) > 3 else ""
    return {"id": "idle", "icon": "🏭", "severity": "watch",
            "sentence": f"{len(idle)} workshops are idle — waiting on inputs: {names}",
            "detail": "idle"}


def votes_card(state) -> dict:
    open_props = [(pid, p) for pid, p in sorted(state.proposals.items())
                  if p.get("status") == "open"]
    if not open_props:
        return {"id": "votes", "icon": "🗳️", "severity": "info",
                "sentence": "No votes are open right now — the republic is calm."}
    left = max(max(p.get("closes_tick", state.tick) - state.tick, 0) for _pid, p in open_props)
    return {"id": "votes", "icon": "🗳️", "severity": "info",
            "sentence": f"{len(open_props)} vote{'s' if len(open_props) > 1 else ''} open — closing in {left} ticks",
            "detail": "votes"}


def shock_card(state) -> dict | None:
    if not state.active_shocks:
        return None
    worst = max(state.active_shocks, key=lambda s: s.get("intensity", 0))
    kind = str(worst.get("kind", "shock")).replace("_", " ").title()
    return {"id": "shock", "icon": "🌩️", "severity": "bad",
            "sentence": f"{kind} is hitting the economy", "detail": "shocks"}


def population_card(state, timeline) -> dict:
    n = len(state.balances)
    children = sum(1 for m in state.citizens_meta.values() if m.get("child"))
    if children:
        return {"id": "population", "icon": "👨‍👩‍👧", "severity": "info",
                "sentence": f"{n} people live here — {children} still growing up",
                "series": (timeline.get("pop") or [])[-60:],
                "series_label": "population"}
    return {"id": "population", "icon": "👥", "severity": "info",
            "sentence": f"{n} people live in this economy"}


def build_story(state, timeline) -> dict:
    """The full front page: severity-sorted story cards."""
    cards: list[dict] = [
        economy_health_card(state, timeline),
        shortage_card(state, timeline),
        inequality_card(state, timeline),
        idle_production_card(state),
        votes_card(state),
        population_card(state, timeline),
    ]
    if (shock := shock_card(state)) is not None:
        cards.append(shock)
    order = {"bad": 0, "watch": 1, "info": 2, "good": 3}
    cards.sort(key=lambda c: order.get(c.get("severity", "info"), 9))
    return {"tick": state.tick, "cards": cards}
