#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json

from cryptoquant.backtest import EventBusBenchmarkConfig, run_event_bus_benchmark


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark backtest event bus latency/throughput")
    parser.add_argument("--events", type=int, default=100_000, help="Measured events")
    parser.add_argument("--warmup-events", type=int, default=10_000, help="Warmup events")
    parser.add_argument("--queue-size", type=int, default=100_000)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument(
        "--block-on-full",
        action="store_true",
        help="Block publisher instead of dropping events when queue is full",
    )
    args = parser.parse_args()

    result = run_event_bus_benchmark(
        EventBusBenchmarkConfig(
            total_events=args.events,
            warmup_events=args.warmup_events,
            queue_size=args.queue_size,
            worker_count=args.workers,
            batch_size=args.batch_size,
            drop_on_full=not args.block_on_full,
        )
    )

    print(
        json.dumps(
            {
                "published": result.published,
                "dispatched": result.dispatched,
                "dropped": result.dropped,
                "duration_sec": round(result.duration_sec, 6),
                "throughput_eps": round(result.throughput_eps, 2),
                "p50_latency_us": round(result.p50_latency_us, 2),
                "p95_latency_us": round(result.p95_latency_us, 2),
                "p99_latency_us": round(result.p99_latency_us, 2),
                "max_latency_us": round(result.max_latency_us, 2),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
