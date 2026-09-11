"""Realism contract L6 - Regional markets (spec 2026-09-11-...bundle.md).

Real economies are local markets under global law: essential clearing is
regional, so scarcity is REGIONAL before it is global (one district can
starve while the city average looks fine). Determinism: region id is a
pure function of the citizen/coop id (no rng, no wall clock); passes run
in sorted region order with a tick-rotated start so no region is
permanently served first.

Rule-gated via params['regional_markets']: absent => city-wide clearing
exactly as before (byte-identical old worlds).
"""
from __future__ import annotations

import hashlib
from typing import Any


def region_count(params: dict[str, Any], population: int) -> int:
    cfg = params.get("regional_markets") or {}
    if not cfg.get("enabled"):
        return 1
    base = max(1, int(cfg.get("regions", 0)) or min(16, max(4, population // 100)))
    return max(1, base)


def region_of(owner: str, n_regions: int, salt: str = "ob-region") -> int:
    """Stable hash bucket of a citizen/coop id into [0, n_regions)."""
    if n_regions <= 1:
        return 0
    h = hashlib.sha256(f"{salt}|{owner}".encode("utf-8")).hexdigest()
    return int(h[:16], 16) % n_regions


def region_order(n_regions: int, tick: int) -> list[int]:
    """Tick-rotated sorted order: fair serving across ticks, deterministic."""
    ids = list(range(n_regions))
    if n_regions <= 1:
        return ids
    off = tick % n_regions
    return ids[off:] + ids[:off]
