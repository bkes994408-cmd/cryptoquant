from __future__ import annotations

from datetime import datetime, timedelta, timezone

from cryptoquant.backtest.replay_resource_governance import (
    ReplayGovernanceConfig,
    run_large_sample_replay_governance,
)
from cryptoquant.events.market import MarketEvent


def _mk_events(n: int, symbol: str = "BTCUSDT") -> list[MarketEvent]:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    out: list[MarketEvent] = []
    for i in range(n):
        out.append(
            MarketEvent(
                symbol=symbol,
                timeframe="1m",
                close=10_000 + i,
                ts=start + timedelta(minutes=i),
            )
        )
    return out


def test_large_sample_replay_governance_reports_memory_and_queue_stats() -> None:
    events = _mk_events(5_000)
    report = run_large_sample_replay_governance(
        events,
        symbol="BTCUSDT",
        config=ReplayGovernanceConfig(
            queue_size=128,
            worker_count=1,
            batch_size=64,
            drop_on_full=False,
            snapshot_interval=1_000,
        ),
    )

    assert report.total_input == 5_000
    assert report.published == 5_000
    assert report.dispatched == 5_000
    assert report.dropped == 0
    assert report.peak_memory_kb > 0
    assert report.queue_high_watermark > 0
    assert report.max_queue_utilization > 0
    assert len(report.snapshots) >= 5


def test_large_sample_replay_governance_observes_backpressure_when_dropping() -> None:
    events = _mk_events(10_000)
    report = run_large_sample_replay_governance(
        events,
        symbol="BTCUSDT",
        config=ReplayGovernanceConfig(
            queue_size=8,
            worker_count=1,
            batch_size=8,
            drop_on_full=True,
            snapshot_interval=2_000,
        ),
    )

    assert report.published + report.dropped == 10_000
    assert report.dispatched == report.published
    assert report.dropped > 0
    assert report.backpressure_count >= report.dropped
