from __future__ import annotations

from datetime import datetime, timezone
from threading import Event

from cryptoquant.events.bus import LowLatencyEventBus
from cryptoquant.events.market import MarketEvent


def _mk_event(symbol: str) -> MarketEvent:
    return MarketEvent(
        symbol=symbol,
        timeframe="1m",
        close=1.0,
        ts=datetime(2026, 3, 8, tzinfo=timezone.utc),
    )


def test_low_latency_event_bus_dispatches_batched_events() -> None:
    bus = LowLatencyEventBus(queue_size=1024, worker_count=1, batch_size=64)
    got: list[str] = []
    done = Event()

    def h(e: MarketEvent) -> None:
        got.append(e.symbol)
        if len(got) >= 200:
            done.set()

    bus.subscribe(MarketEvent, h)
    bus.start()
    bus.publish_many(_mk_event(f"S{i}") for i in range(200))

    assert done.wait(timeout=2.0)
    bus.stop()

    assert len(got) == 200
    assert got[0] == "S0"
    assert got[-1] == "S199"

    stats = bus.stats()
    assert stats.published == 200
    assert stats.dispatched == 200
    assert stats.dropped == 0


def test_low_latency_event_bus_can_drop_on_backpressure() -> None:
    bus = LowLatencyEventBus(queue_size=10, worker_count=1, batch_size=8, drop_on_full=True)
    processed: list[str] = []

    def h(e: MarketEvent) -> None:
        processed.append(e.symbol)

    bus.subscribe(MarketEvent, h)
    bus.start()
    bus.publish_many(_mk_event(f"D{i}") for i in range(5000))
    bus.stop()

    stats = bus.stats()
    assert stats.published + stats.dropped == 5000
    assert stats.dispatched == stats.published
    assert stats.dropped > 0
    assert stats.backpressure_count >= stats.dropped
    assert len(processed) == stats.dispatched
    assert stats.batches > 0


def test_low_latency_event_bus_flush_waits_until_drained() -> None:
    bus = LowLatencyEventBus(queue_size=512, worker_count=1, batch_size=32)
    processed: list[str] = []

    def h(e: MarketEvent) -> None:
        processed.append(e.symbol)

    bus.subscribe(MarketEvent, h)
    bus.start()
    bus.publish_many(_mk_event(f"F{i}") for i in range(300))

    assert bus.flush(timeout_sec=2.0)
    bus.stop()

    assert len(processed) == 300
    stats = bus.stats()
    assert stats.queue_size == 0
    assert stats.handler_errors == 0


def test_low_latency_event_bus_is_resilient_to_handler_errors() -> None:
    bus = LowLatencyEventBus(queue_size=256, worker_count=1, batch_size=16)
    processed: list[str] = []

    def flaky_handler(e: MarketEvent) -> None:
        if e.symbol.endswith("7"):
            raise RuntimeError("boom")
        processed.append(e.symbol)

    bus.subscribe(MarketEvent, flaky_handler)
    bus.start()
    bus.publish_many(_mk_event(f"E{i}") for i in range(100))
    bus.stop()

    stats = bus.stats()
    assert stats.published == 100
    assert stats.dispatched == 100
    assert stats.handler_errors == 10
    assert len(processed) == 90
