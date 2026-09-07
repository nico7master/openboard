"""Unit tests for the top-1% wealth share metric (WP2.2 gate measure).

The WP2.2 gate: >=3 distinct policy paths reach <15% top-1 share (1500 bp)
while needs stay met — this metric must be exact and unambiguous.
"""
from openboard.metrics import SimMetrics, top1_share_bp


def test_unequal_start_is_50pct():
    # Unequal genesis: richest 1% (1 holder) owns 10.5M of 21M -> 5000 bp.
    # The other 99% hold the remaining 10.5M (20 x 525_000 shown).
    values = [10_500_000] + [525_000] * 20
    assert top1_share_bp(values) == 5000


def test_perfect_equality_is_100bp():
    # 100 equal holders: the top 1 holds 1/100 -> 100 bp.
    values = [1_000] * 100
    assert top1_share_bp(values) == 100


def test_small_population_single_richest():
    # ceil(7/100) = 1: only the single richest holder counts.
    assert top1_share_bp([100, 50, 50, 1, 1, 1, 1]) == 100 * 10_000 // 204


def test_gate_threshold_semantics():
    # 15% top-1 share boundary on the 21M supply: gate is < 1500 bp.
    # Integer division floors, so 'fails' must be >= 1501 bp.
    at_gate = [3_146_000] + [892_700] * 20  # total 21M -> 1498 bp
    above_gate = [3_152_100] + [892_395] * 20  # total 21M -> 1501 bp
    assert top1_share_bp(at_gate) == 1498
    assert top1_share_bp(above_gate) == 1501


def test_empty_and_zero():
    assert top1_share_bp([]) == 0
    assert top1_share_bp([0, 0, 0]) == 0


def test_pool_is_not_a_private_holder():
    # The Society Pool is PUBLIC money (the tax's destination): it must not
    # dilute private concentration. Same private wealth -> same share.
    private = [10_500_000] + [525_000] * 20
    assert top1_share_bp(private) == 5000


def test_dividends_shift_private_share():
    # Recycled tax money paid out as equal dividends lowers the top-1 share.
    start = [10_500_000] + [525_000] * 20
    after_dividend = [9_000_000] + [1_075_000] * 20  # 1.5M recycled equally
    assert top1_share_bp(after_dividend) < top1_share_bp(start)


def test_simmetrics_summary_exposes_final_share():
    class FakeCoop:
        def __init__(self, treasury):
            self.treasury = treasury

    class FakeState:
        tick = 0
        balances = {f"c{i}": 525_000 for i in range(99)}
        balances["whale"] = 10_500_000
        coops = {"k1": {"treasury": 0}}
        surplus_pool = 0
        money_minted = 0
        money_retired = 0

    m = SimMetrics()
    m.record_tick(FakeState(), [])
    s = m.summary()
    # PRIVATE holders only (pool excluded): 101 holders (99 citizens +
    # whale + 1 zero treasury) -> k = ceil(101/100) = 2, so top-2 = whale +
    # richest citizen = 11,025,000 of 62,475,000 private money = 1764 bp.
    assert s["final_top1_share_bp"] == 1764
    assert len(m.top1_share_bp) == 1
