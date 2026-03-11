from __future__ import annotations

from datetime import datetime, timezone

from cryptoquant.market.microstructure import (
    OrderBookLevel,
    OrderBookMicrostructureAnalyzer,
    OrderBookSnapshot,
)


def _snapshot(*, bid_px: float, bid_sz: float, ask_px: float, ask_sz: float) -> OrderBookSnapshot:
    return OrderBookSnapshot(
        symbol="BTCUSDT",
        ts=datetime(2026, 3, 11, 8, 0, tzinfo=timezone.utc),
        bids=(
            OrderBookLevel(price=bid_px, size=bid_sz),
            OrderBookLevel(price=bid_px - 1.0, size=2.0),
        ),
        asks=(
            OrderBookLevel(price=ask_px, size=ask_sz),
            OrderBookLevel(price=ask_px + 1.0, size=1.5),
        ),
        source="test",
    )


def test_analyze_depth_and_spread_metrics() -> None:
    analyzer = OrderBookMicrostructureAnalyzer()
    snap = _snapshot(bid_px=100.0, bid_sz=3.0, ask_px=101.0, ask_sz=1.0)

    m = analyzer.analyze(snap, depth_levels=2)

    assert m.best_bid == 100.0
    assert m.best_ask == 101.0
    assert m.spread == 1.0
    assert m.mid_price == 100.5
    assert m.spread_bps > 99.0
    assert m.bid_depth == 5.0
    assert m.ask_depth == 2.5
    assert m.depth_imbalance == (5.0 - 2.5) / 7.5


def test_micro_price_is_top_size_weighted() -> None:
    analyzer = OrderBookMicrostructureAnalyzer()
    snap = _snapshot(bid_px=100.0, bid_sz=4.0, ask_px=101.0, ask_sz=1.0)

    m = analyzer.analyze(snap)

    expected = (101.0 * 4.0 + 100.0 * 1.0) / 5.0
    assert m.micro_price == expected


def test_ofi_changes_with_top_of_book_update() -> None:
    analyzer = OrderBookMicrostructureAnalyzer()

    first = _snapshot(bid_px=100.0, bid_sz=2.0, ask_px=101.0, ask_sz=2.0)
    second = _snapshot(bid_px=100.0, bid_sz=5.0, ask_px=101.0, ask_sz=1.0)

    m1 = analyzer.analyze(first)
    m2 = analyzer.analyze(second)

    assert m1.order_flow_imbalance == 0.0
    # bid strengthens (size up), ask thins (size down) => positive OFI
    assert m2.order_flow_imbalance > 0.0


def test_invalid_depth_levels_raise() -> None:
    analyzer = OrderBookMicrostructureAnalyzer()
    snap = _snapshot(bid_px=100.0, bid_sz=1.0, ask_px=101.0, ask_sz=1.0)

    try:
        analyzer.analyze(snap, depth_levels=0)
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "depth_levels" in str(exc)
