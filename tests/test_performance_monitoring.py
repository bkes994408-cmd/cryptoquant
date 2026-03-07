from __future__ import annotations

from cryptoquant.monitoring import RealTimePerformanceMonitor


def test_monitor_tracks_unrealized_pnl_for_open_position() -> None:
    mon = RealTimePerformanceMonitor()
    mon.record_fill(symbol="BTCUSDT", qty=1.0, fill_price=100.0)

    snap = mon.record_mark_price(symbol="BTCUSDT", mark_price=110.0)

    assert snap.realized_pnl == 0.0
    assert snap.unrealized_pnl == 10.0
    assert snap.net_pnl == 10.0
    assert snap.by_symbol["BTCUSDT"].notional_exposure == 110.0


def test_monitor_tracks_realized_pnl_when_closing() -> None:
    mon = RealTimePerformanceMonitor()
    mon.record_fill(symbol="BTCUSDT", qty=2.0, fill_price=100.0)

    snap = mon.record_fill(symbol="BTCUSDT", qty=-1.0, fill_price=110.0)

    assert snap.realized_pnl == 10.0
    assert snap.by_symbol["BTCUSDT"].qty == 1.0
    assert snap.close_trades == 1
    assert snap.win_rate == 1.0


def test_monitor_handles_flip_position_correctly() -> None:
    mon = RealTimePerformanceMonitor()
    mon.record_fill(symbol="ETHUSDT", qty=1.0, fill_price=100.0)

    snap = mon.record_fill(symbol="ETHUSDT", qty=-3.0, fill_price=90.0)

    assert snap.realized_pnl == -10.0
    assert snap.by_symbol["ETHUSDT"].qty == -2.0
    assert snap.by_symbol["ETHUSDT"].avg_entry_price == 90.0


def test_monitor_net_pnl_includes_fee_and_slippage() -> None:
    mon = RealTimePerformanceMonitor()
    mon.record_fill(symbol="BTCUSDT", qty=1.0, fill_price=100.0, fee=1.0, slippage_cost=0.5)

    snap = mon.record_mark_price(symbol="BTCUSDT", mark_price=100.0)

    assert snap.fee_total == 1.0
    assert snap.slippage_total == 0.5
    assert snap.net_pnl == -1.5


def test_monitor_tracks_max_drawdown_from_equity_curve() -> None:
    mon = RealTimePerformanceMonitor()
    mon.record_fill(symbol="BTCUSDT", qty=1.0, fill_price=100.0)
    mon.record_mark_price(symbol="BTCUSDT", mark_price=120.0)

    snap = mon.record_mark_price(symbol="BTCUSDT", mark_price=90.0)

    assert snap.net_pnl == -10.0
    assert snap.max_drawdown == 30.0
