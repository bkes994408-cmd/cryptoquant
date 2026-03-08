from __future__ import annotations

from datetime import datetime, timezone

from cryptoquant.backtest import CSVDataSourceConfig, CSVMarketEventSource, MultiSourceEventLoader
from cryptoquant.events.market import MarketEvent


def test_csv_market_event_source_supports_iso_timestamp_and_defaults(tmp_path) -> None:
    file_path = tmp_path / "events.csv"
    file_path.write_text(
        "timestamp,close\n"
        "2026-03-01T00:00:00Z,100\n"
        "2026-03-01T00:01:00Z,101\n",
        encoding="utf-8",
    )

    source = CSVMarketEventSource(
        CSVDataSourceConfig(
            ts_col="timestamp",
            close_col="close",
            symbol_col=None,
            timeframe_col=None,
            default_symbol="ETHUSDT",
            default_timeframe="1m",
            source="csv-iso",
        )
    )

    events = source.load(file_path)
    assert len(events) == 2
    assert events[0].symbol == "ETHUSDT"
    assert events[0].timeframe == "1m"
    assert events[0].close == 100.0
    assert events[0].source == "csv-iso"


def test_csv_market_event_source_supports_epoch_millis_with_explicit_columns(tmp_path) -> None:
    file_path = tmp_path / "events_ms.csv"
    file_path.write_text(
        "open_time,last_price,symbol,tf\n"
        "1772323200000,200.5,BTCUSDT,5m\n"
        "1772323500000,199.0,BTCUSDT,5m\n",
        encoding="utf-8",
    )

    source = CSVMarketEventSource(
        CSVDataSourceConfig(
            ts_col="open_time",
            close_col="last_price",
            symbol_col="symbol",
            timeframe_col="tf",
            source="exchange-csv",
        )
    )

    events = source.load(file_path)
    assert events[0].ts == datetime.fromtimestamp(1772323200, tz=timezone.utc)
    assert events[0].close == 200.5
    assert events[1].timeframe == "5m"


def test_multi_source_event_loader_merge_sorts_and_dedupes() -> None:
    a = [
        MarketEvent("BTCUSDT", "1m", 100.0, datetime(2026, 3, 1, 0, 1, tzinfo=timezone.utc), "csv"),
        MarketEvent("BTCUSDT", "1m", 99.0, datetime(2026, 3, 1, 0, 0, tzinfo=timezone.utc), "csv"),
    ]
    b = [
        MarketEvent("BTCUSDT", "1m", 100.0, datetime(2026, 3, 1, 0, 1, tzinfo=timezone.utc), "csv"),
        MarketEvent("ETHUSDT", "1m", 50.0, datetime(2026, 3, 1, 0, 1, tzinfo=timezone.utc), "alt"),
    ]

    merged = MultiSourceEventLoader.merge(a, b)
    assert len(merged) == 3
    assert [(e.symbol, e.close) for e in merged] == [
        ("BTCUSDT", 99.0),
        ("BTCUSDT", 100.0),
        ("ETHUSDT", 50.0),
    ]
