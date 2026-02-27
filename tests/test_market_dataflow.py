from __future__ import annotations

from datetime import datetime, timezone

from cryptoquant.aggregation import Bar, BarAggregator
from cryptoquant.events.bus import EventBus
from cryptoquant.events.market import MarketEvent


def test_event_bus_market_event_to_15m_aggregation_flow() -> None:
    bus = EventBus()
    agg = BarAggregator(gap_fill=True)
    captured_1m: list[Bar] = []

    def on_market(event: MarketEvent) -> None:
        captured_1m.append(
            Bar(
                symbol=event.symbol,
                timeframe="1m",
                ts=event.ts,
                open=event.close,
                high=event.close,
                low=event.close,
                close=event.close,
                volume=1.0,
            )
        )

    bus.subscribe(MarketEvent, on_market)

    bus.publish(
        MarketEvent(
            symbol="BTCUSDT",
            timeframe="1m",
            close=100,
            ts=datetime(2026, 2, 27, 0, 0, tzinfo=timezone.utc),
            source="test",
        )
    )
    # 故意跳過 00:01，驗證 gap fill
    bus.publish(
        MarketEvent(
            symbol="BTCUSDT",
            timeframe="1m",
            close=103,
            ts=datetime(2026, 2, 27, 0, 2, tzinfo=timezone.utc),
            source="test",
        )
    )

    out = agg.aggregate(captured_1m, "15m")

    assert len(out) == 1
    only = out[0]
    assert only.ts == datetime(2026, 2, 27, 0, 0, tzinfo=timezone.utc)
    assert only.open == 100
    assert only.close == 103
    assert only.high == 103
    assert only.low == 100
    assert only.volume == 2.0
