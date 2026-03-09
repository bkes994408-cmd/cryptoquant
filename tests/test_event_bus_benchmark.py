from __future__ import annotations

from cryptoquant.backtest.event_bus_benchmark import (
    EventBusBenchmarkConfig,
    run_event_bus_benchmark,
)


def test_run_event_bus_benchmark_returns_expected_fields() -> None:
    result = run_event_bus_benchmark(
        EventBusBenchmarkConfig(
            total_events=2_000,
            warmup_events=200,
            queue_size=256,
            worker_count=1,
            batch_size=64,
            drop_on_full=False,
        )
    )

    assert result.published == 2_000
    assert result.dispatched == 2_000
    assert result.dropped == 0
    assert result.throughput_eps > 0
    assert result.p95_latency_us >= result.p50_latency_us
    assert result.max_latency_us >= result.p99_latency_us
    assert result.queue_high_watermark > 0


def test_run_event_bus_benchmark_handles_backpressure_drop_mode() -> None:
    result = run_event_bus_benchmark(
        EventBusBenchmarkConfig(
            total_events=20_000,
            warmup_events=0,
            queue_size=8,
            worker_count=1,
            batch_size=16,
            drop_on_full=True,
        )
    )

    assert result.published + result.dropped == 20_000
    assert result.dispatched == result.published
    assert result.backpressure_count >= result.dropped
