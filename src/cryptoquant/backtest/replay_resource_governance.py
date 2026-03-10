from __future__ import annotations

import tracemalloc
from dataclasses import dataclass
from typing import Sequence

from cryptoquant.events.bus import LowLatencyEventBus
from cryptoquant.events.market import MarketEvent


@dataclass(frozen=True)
class ReplayGovernanceConfig:
    queue_size: int = 50_000
    worker_count: int = 2
    batch_size: int = 512
    drop_on_full: bool = True
    snapshot_interval: int = 5_000


@dataclass(frozen=True)
class ResourceSnapshot:
    published: int
    dropped: int
    dispatched: int
    queue_size: int
    queue_utilization: float
    backpressure_count: int
    current_memory_kb: float
    peak_memory_kb: float


@dataclass(frozen=True)
class ReplayGovernanceReport:
    total_input: int
    published: int
    dropped: int
    dispatched: int
    backpressure_count: int
    queue_high_watermark: int
    max_queue_utilization: float
    peak_memory_kb: float
    snapshots: list[ResourceSnapshot]


def run_large_sample_replay_governance(
    events: Sequence[MarketEvent],
    *,
    symbol: str,
    config: ReplayGovernanceConfig,
) -> ReplayGovernanceReport:
    if config.snapshot_interval <= 0:
        raise ValueError("snapshot_interval must be > 0")

    bus = LowLatencyEventBus(
        queue_size=config.queue_size,
        worker_count=config.worker_count,
        batch_size=config.batch_size,
        drop_on_full=config.drop_on_full,
    )
    snapshots: list[ResourceSnapshot] = []
    consumed = 0

    def _handler(event: MarketEvent) -> None:
        nonlocal consumed
        if event.symbol == symbol:
            consumed += 1

    def _capture_snapshot() -> None:
        current_bytes, peak_bytes = tracemalloc.get_traced_memory()
        stats = bus.stats()
        utilization = stats.queue_size / max(stats.queue_capacity, 1)
        snapshots.append(
            ResourceSnapshot(
                published=stats.published,
                dropped=stats.dropped,
                dispatched=stats.dispatched,
                queue_size=stats.queue_size,
                queue_utilization=utilization,
                backpressure_count=stats.backpressure_count,
                current_memory_kb=current_bytes / 1024,
                peak_memory_kb=peak_bytes / 1024,
            )
        )

    bus.subscribe(MarketEvent, _handler)
    bus.start()
    tracemalloc.start()

    try:
        for idx, event in enumerate(events, start=1):
            bus.publish(event)
            if idx % config.snapshot_interval == 0:
                _capture_snapshot()

        drained = bus.flush(timeout_sec=30.0)
        if not drained:
            raise TimeoutError("replay queue did not drain before timeout")

        _capture_snapshot()
        final = bus.stats()
        _, peak_bytes = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
        bus.stop()

    max_queue_utilization = max((s.queue_utilization for s in snapshots), default=0.0)

    return ReplayGovernanceReport(
        total_input=len(events),
        published=final.published,
        dropped=final.dropped,
        dispatched=final.dispatched,
        backpressure_count=final.backpressure_count,
        queue_high_watermark=final.queue_high_watermark,
        max_queue_utilization=max_queue_utilization,
        peak_memory_kb=peak_bytes / 1024,
        snapshots=snapshots,
    )
