from __future__ import annotations

from datetime import datetime, timedelta, timezone

from cryptoquant.aggregation import Bar, BarAggregator


def _bar(minute_offset: int, *, base: datetime, close: float, volume: float = 1.0) -> Bar:
    ts = base + timedelta(minutes=minute_offset)
    return Bar(
        symbol="BTCUSDT",
        timeframe="1m",
        ts=ts,
        open=close - 1,
        high=close + 2,
        low=close - 3,
        close=close,
        volume=volume,
    )


def test_aggregate_1m_to_15m() -> None:
    base = datetime(2026, 2, 14, 0, 0, tzinfo=timezone.utc)
    bars = [_bar(i, base=base, close=100 + i) for i in range(16)]

    agg = BarAggregator(gap_fill=False)
    out = agg.aggregate(bars, "15m")

    assert len(out) == 2

    first = out[0]
    assert first.ts == base
    assert first.timeframe == "15m"
    assert first.open == 99
    assert first.close == 114
    assert first.volume == 15.0

    second = out[1]
    assert second.ts == base + timedelta(minutes=15)
    assert second.open == 114
    assert second.close == 115
    assert second.volume == 1.0


def test_gap_fill_generates_flat_1m_bars_before_15m_aggregation() -> None:
    base = datetime(2026, 2, 14, 0, 0, tzinfo=timezone.utc)
    bars = [
        _bar(0, base=base, close=100, volume=2),
        _bar(2, base=base, close=103, volume=3),
    ]

    agg = BarAggregator(gap_fill=True)
    out = agg.aggregate(bars, "15m")

    assert len(out) == 1
    only = out[0]
    assert only.ts == base
    assert only.open == 99
    assert only.close == 103
    assert only.high == 105
    # low from first real bar, plus one synthetic flat bar at close=100
    assert only.low == 97
    # synthetic gap-filled bar has zero volume
    assert only.volume == 5


def test_aggregate_1m_to_1h() -> None:
    base = datetime(2026, 2, 14, 0, 0, tzinfo=timezone.utc)
    bars = [_bar(i, base=base, close=200 + i, volume=0.5) for i in range(60)]

    agg = BarAggregator(gap_fill=False)
    out = agg.aggregate(bars, "1h")

    assert len(out) == 1
    only = out[0]
    assert only.ts == base
    assert only.timeframe == "1h"
    assert only.open == 199
    assert only.close == 259
    assert only.volume == 30.0
