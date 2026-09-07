"""Stability metrics for simulations — spec §10.

All measures are computed from public state and events: same data any
external verifier sees. Exact integer arithmetic throughout.
"""

from __future__ import annotations

from typing import Any

from .state import WorldState


def gini(values: list[int]) -> int:
    """Exact Gini coefficient x 10,000 (bp). 0 = perfect equality.

    Classic formula on integer sums — no floats.
    """
    n = len(values)
    if n == 0:
        return 0
    if n == 1:
        return 0
    vs = sorted(values)
    total = sum(vs)
    if total == 0:
        return 0
    # sum of absolute differences over all pairs, divided by 2*n*total
    diff_sum = 0
    for i, vi in enumerate(vs):
        diff_sum += (2 * i - n + 1) * vi  # rank-weighted shortcut, exact
    # gini = diff_sum / (n * total); scale to bp
    return abs(diff_sum) * 10_000 // (n * total)


def top1_share_bp(values: list[int]) -> int:
    """Wealth share of the richest 1% x 10,000 (bp), exact integers.

    The richest 1% = the top max(1, ceil(n/100)) entries; for small
    populations this degrades to the single richest holder (the unequal
    scenario's 1-in-100 case). The Society Pool counts as a holder.
    """
    n = len(values)
    if n == 0:
        return 0
    vs = sorted(values, reverse=True)
    total = sum(vs)
    if total <= 0:
        return 0
    k = max(1, -(-n // 100))  # ceil(n/100)
    return sum(vs[:k]) * 10_000 // total


class SimMetrics:
    """Collects per-tick stability metrics from public state and events."""

    def __init__(self) -> None:
        self.ticks: list[int] = []
        self.gini_bp: list[int] = []
        self.top1_share_bp: list[int] = []
        self.clearing_prices: dict[str, list[int]] = {}  # good -> prices
        self.unmet_essential_demand: list[int] = []
        self.flags_by_kind: dict[str, int] = {}
        self.rejected_by_reason: dict[str, int] = {}
        self.money_minted: list[int] = []
        self.money_retired: list[int] = []
        self.proposals_passed = 0
        self.proposals_failed = 0

    def record_tick(self, state: WorldState, tick_events: list[dict[str, Any]]) -> None:
        self.ticks.append(state.tick)
        balances = list(state.balances.values())
        treasuries = [c.get("treasury", 0) for c in state.coops.values()]
        self.gini_bp.append(gini(balances + treasuries + [state.surplus_pool]))
        # Top-1 share measures PRIVATE concentration: the Society Pool is
        # public money (the wealth tax's destination), not a private holder.
        # Counting it would mask exactly the redistribution the WP2.2 gate
        # measures (unequal scenario: top 1% owns 50% of PRIVATE money).
        self.top1_share_bp.append(
            top1_share_bp(balances + treasuries)
        )
        self.money_minted.append(state.money_minted)
        self.money_retired.append(state.money_retired)

        for e in tick_events:
            act = e.get("action", "")
            if act == "MARKET_CLEAR_AUCTION" and e.get("clearing_price") is not None:
                self.clearing_prices.setdefault(e["good"], []).append(e["clearing_price"])
            elif act == "OVERSIGHT_FLAG":
                kind = e.get("kind", "?")
                self.flags_by_kind[kind] = self.flags_by_kind.get(kind, 0) + 1

    def record_rejections(self, ledger) -> None:
        for r in ledger.records:
            if not r.accepted and r.reason:
                self.rejected_by_reason[r.reason] = self.rejected_by_reason.get(r.reason, 0) + 1

    def price_variance_bp(self, good: str, baseline: int) -> int:
        """Mean |price - baseline| / baseline x 10,000 (bp), integer."""
        prices = self.clearing_prices.get(good, [])
        if not prices or baseline <= 0:
            return 0
        total_dev = sum(abs(p - baseline) for p in prices)
        return total_dev * 10_000 // (len(prices) * baseline)

    def summary(self) -> dict[str, Any]:
        return {
            "ticks": len(self.ticks),
            "final_gini_bp": self.gini_bp[-1] if self.gini_bp else 0,
            "final_top1_share_bp": self.top1_share_bp[-1] if self.top1_share_bp else 0,
            "flags": dict(self.flags_by_kind),
            "rejections": dict(self.rejected_by_reason),
            "price_variance_bp": {
                good: self.price_variance_bp(good, 1) for good in self.clearing_prices
            },
            "proposals_passed": self.proposals_passed,
            "proposals_failed": self.proposals_failed,
        }
