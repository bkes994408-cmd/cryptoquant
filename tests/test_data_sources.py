from __future__ import annotations

from datetime import datetime, timezone

from cryptoquant.aggregation import Bar
from cryptoquant.data import InMemoryBarDataSource


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
