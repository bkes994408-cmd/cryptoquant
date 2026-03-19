from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from cryptoquant.aggregation import Bar
from cryptoquant.data import CompositeBarDataSource, InMemoryBarDataSource, ParquetBarDataSource


def test_inmemory_data_source_filters_symbol_timeframe_and_range() -> None:
    base = datetime(2026, 3, 1, tzinfo=timezone.utc)
    ds = InMemoryBarDataSource(
        bars=[
            Bar("BTCUSDT", "1m", base, 1, 1, 1, 1, 1),
            Bar("BTCUSDT", "1m", base.replace(minute=1), 2, 2, 2, 2, 2),
            Bar("ETHUSDT", "1m", base.replace(minute=2), 3, 3, 3, 3, 3),
        ]
    )

    out = ds.fetch_bars(
        symbol="BTCUSDT",
        timeframe="1m",
        start=base.replace(minute=1),
    )

    assert len(out) == 1
    assert out[0].close == 2


def test_composite_data_source_merge_and_dedup() -> None:
    base = datetime(2026, 3, 1, tzinfo=timezone.utc)
    left = InMemoryBarDataSource(
        bars=[
            Bar("BTCUSDT", "1m", base, 1, 1, 1, 1, 1),
            Bar("BTCUSDT", "1m", base.replace(minute=1), 2, 2, 2, 2, 2),
        ]
    )
    right = InMemoryBarDataSource(
        bars=[
            Bar("BTCUSDT", "1m", base.replace(minute=1), 20, 20, 20, 20, 20),
            Bar("BTCUSDT", "1m", base.replace(minute=2), 3, 3, 3, 3, 3),
        ]
    )

    merged = CompositeBarDataSource([left, right]).fetch_bars(symbol="BTCUSDT", timeframe="1m")

    assert [bar.ts.minute for bar in merged] == [0, 1, 2]
    # duplicate timestamp keeps later source value
    assert merged[1].close == 20


def test_parquet_data_source_supports_row_loader() -> None:
    base = datetime(2026, 3, 1, tzinfo=timezone.utc)

    def _loader(_):
        return [
            {
                "symbol": "BTCUSDT",
                "timeframe": "1m",
                "ts": base.isoformat(),
                "open": 100,
                "high": 101,
                "low": 99,
                "close": 100,
                "volume": 1,
            },
            {
                "symbol": "BTCUSDT",
                "timeframe": "1m",
                "ts": base.replace(minute=1).isoformat(),
                "open": 101,
                "high": 102,
                "low": 100,
                "close": 101,
                "volume": 1,
            },
        ]

    ds = ParquetBarDataSource(path=Path("dummy.parquet"), row_loader=_loader)
    bars = ds.fetch_bars(symbol="BTCUSDT", timeframe="1m")

    assert len(bars) == 2
    assert bars[1].close == 101
