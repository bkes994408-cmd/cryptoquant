from __future__ import annotations

from datetime import datetime, timezone

from cryptoquant.events.bus import EventBus
from cryptoquant.events.market import MarketEvent


def test_event_bus_publish_delivers_to_subscribers_in_order() -> None:
    bus = EventBus()
    calls: list[str] = []

    def h1(e: MarketEvent) -> None:
        calls.append(f"h1:{e.symbol}")

    def h2(e: MarketEvent) -> None:
        calls.append(f"h2:{e.symbol}")

    bus.subscribe(MarketEvent, h1)
    bus.subscribe(MarketEvent, h2)

    bus.publish(
        MarketEvent(
            symbol="BTCUSDT",
            timeframe="1m",
            close=50000.0,
            ts=datetime(2026, 2, 14, tzinfo=timezone.utc),
        )
    )

    assert calls == ["h1:BTCUSDT", "h2:BTCUSDT"]


def test_event_bus_unsubscribe_stops_delivery() -> None:
    bus = EventBus()
    calls: list[str] = []

    def h(e: MarketEvent) -> None:
        calls.append(e.symbol)

    sub = bus.subscribe(MarketEvent, h)
    bus.publish(
        MarketEvent(
            symbol="ETHUSDT",
            timeframe="1m",
            close=3000.0,
            ts=datetime(2026, 2, 14, tzinfo=timezone.utc),
        )
    )

    bus.unsubscribe(sub)
    bus.publish(
        MarketEvent(
            symbol="SOLUSDT",
            timeframe="1m",
            close=100.0,
            ts=datetime(2026, 2, 14, tzinfo=timezone.utc),
        )
    )

    assert calls == ["ETHUSDT"]
