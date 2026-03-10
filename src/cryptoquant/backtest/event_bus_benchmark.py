from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from time import perf_counter, perf_counter_ns
from typing import Sequence

from cryptoquant.events.bus import LowLatencyEventBus


@dataclass(frozen=True)
class EventBusBenchmarkConfig:
    total_events: int = 100_000
    warmup_events: int = 10_000
    queue_size: int = 100_000
    worker_count: int = 2
    batch_size: int = 256
    drop_on_full: bool = True


@dataclass(frozen=True)
class EventBusBenchmarkResult:
    published: int
    dispatched: int
    dropped: int
    backpressure_count: int
    queue_high_watermark: int
    duration_sec: float
    throughput_eps: float
    p50_latency_us: float
    p95_latency_us: float
    p99_latency_us: float
    max_latency_us: float


@dataclass(frozen=True)
class _BenchmarkEvent:
    seq: int
    enqueue_ns: int


def _percentile(values: Sequence[float], q: float) -> float:
    if not values:
        return 0.0
    if q <= 0:
        return float(values[0])
    if q >= 1:
        return float(values[-1])

    pos = (len(values) - 1) * q
    lower = int(pos)
    upper = min(lower + 1, len(values) - 1)
    if lower == upper:
        return float(values[lower])
    weight = pos - lower
    return float(values[lower] * (1 - weight) + values[upper] * weight)


def run_event_bus_benchmark(config: EventBusBenchmarkConfig) -> EventBusBenchmarkResult:
    if config.total_events <= 0:
        raise ValueError("total_events must be > 0")
    if config.warmup_events < 0:
        raise ValueError("warmup_events must be >= 0")

    bus = LowLatencyEventBus(
        queue_size=config.queue_size,
        worker_count=config.worker_count,
        batch_size=config.batch_size,
        drop_on_full=config.drop_on_full,
    )
    lock = Lock()
    latencies_us: list[float] = []

    def on_event(event: _BenchmarkEvent) -> None:
        latency_us = (perf_counter_ns() - event.enqueue_ns) / 1_000
        with lock:
            latencies_us.append(latency_us)

    bus.subscribe(_BenchmarkEvent, on_event)
    bus.start()

    try:
        if config.warmup_events:
            for idx in range(config.warmup_events):
                now_ns = perf_counter_ns()
                bus.publish(_BenchmarkEvent(seq=-idx - 1, enqueue_ns=now_ns))
            bus.flush(timeout_sec=5.0)
            with lock:
                latencies_us.clear()

        before = bus.stats()
        start = perf_counter()
        for idx in range(config.total_events):
            now_ns = perf_counter_ns()
            bus.publish(_BenchmarkEvent(seq=idx, enqueue_ns=now_ns))

        drained = bus.flush(timeout_sec=30.0)
        end = perf_counter()
        if not drained:
            raise TimeoutError("event bus flush timed out during benchmark")

        after = bus.stats()
    finally:
        bus.stop()

    with lock:
        samples = sorted(latencies_us)

    published = after.published - before.published
    dispatched = after.dispatched - before.dispatched
    dropped = after.dropped - before.dropped

    duration_sec = max(end - start, 1e-9)
    throughput_eps = dispatched / duration_sec

    return EventBusBenchmarkResult(
        published=published,
        dispatched=dispatched,
        dropped=dropped,
        backpressure_count=after.backpressure_count - before.backpressure_count,
        queue_high_watermark=max(0, after.queue_high_watermark - before.queue_high_watermark),
        duration_sec=duration_sec,
        throughput_eps=throughput_eps,
        p50_latency_us=_percentile(samples, 0.50),
        p95_latency_us=_percentile(samples, 0.95),
        p99_latency_us=_percentile(samples, 0.99),
        max_latency_us=_percentile(samples, 1.0),
    )
