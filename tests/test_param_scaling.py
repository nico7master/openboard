"""C2: absolute-denominator param regression -- per-capita dividend cap.

Legacy `max_dividend_per_tick` is a TOTAL shared by all citizens; at 1k
citizens it throttled dividends to ~0.2 cr/citizen/tick. The optional
`max_dividend_per_citizen_tick` caps per head and takes precedence when
present. Old worlds without the key must replay unchanged (legacy cap
path still exact).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from openboard.engine import _surplus_spend_phase
from openboard.state import genesis_state


def _params(**ss):
    base = {"dividend_share_bp": 10_000, "services_share_bp": 0,
            "min_pool_buffer": 0}
    base.update(**ss)
    return {"surplus_spending": base}


def test_per_capita_cap_pays_at_scale():
    """986 citizens, pool 10,000, share 100%, cap 2/head -> 1,972 paid."""
    citizens = {f"c{i}": 500 for i in range(986)}
    s = genesis_state(citizens, ruleset_params=_params(max_dividend_per_citizen_tick=2))
    s.surplus_pool = 10_000
    ev = _surplus_spend_phase(s, 1, s.active_ruleset_params())
    assert len(ev) == 1 and ev[0]["kind"] == "dividend"
    assert ev[0]["total"] == 986 * 2
    assert all(b == 502 for b in s.balances.values())
    assert s.dividends_paid == 986 * 2


def test_legacy_total_cap_without_new_key():
    """No per-capita key -> legacy TOTAL cap applies (old worlds unchanged)."""
    citizens = {f"c{i}": 500 for i in range(986)}
    s = genesis_state(citizens, ruleset_params=_params(max_dividend_per_tick=200))
    s.surplus_pool = 10_000
    ev = _surplus_spend_phase(s, 1, s.active_ruleset_params())
    # 200 cr TOTAL // 986 citizens = 0 per citizen -> NOTHING is paid and
    # no event fires. This is the legacy mis-scale faithfully preserved:
    # old worlds replay byte-identically (this 0-dividend behavior IS the
    # bug the per-capita key fixes).
    assert ev == []
    assert s.dividends_paid == 0


def test_per_capita_cap_precedence_over_legacy():
    """Both keys present -> per-capita wins (2*3 > legacy 5 -> 6 paid)."""
    citizens = {f"c{i}": 500 for i in range(3)}
    s = genesis_state(citizens, ruleset_params=_params(
        max_dividend_per_tick=5, max_dividend_per_citizen_tick=2))
    s.surplus_pool = 10_000
    ev = _surplus_spend_phase(s, 1, s.active_ruleset_params())
    assert ev[0]["total"] == 6


def test_small_pool_pays_floor_division():
    """Budget < n: integer split leaves remainder in pool, nothing lost."""
    citizens = {f"c{i}": 500 for i in range(3)}
    s = genesis_state(citizens, ruleset_params=_params(max_dividend_per_citizen_tick=2))
    s.surplus_pool = 4
    ev = _surplus_spend_phase(s, 1, s.active_ruleset_params())
    assert s.dividends_paid == 3  # budget 4 -> per=1, total=3, 1 stays in pool
    assert s.surplus_pool == 1
