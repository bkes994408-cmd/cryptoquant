from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from cryptoquant.data import (
    BAR_V1_DICTIONARY,
    CsvBarDataSource,
    CsvBarSchema,
    DataQualityChecklist,
    DatasetVersionStore,
    build_dataset_version,
)


def test_data_dictionary_normalizes_aliases_and_timestamp() -> None:
    row = {
        "pair": "BTCUSDT",
        "interval": "1m",
        "timestamp": "1772323200000",
        "o": "100",
        "h": "101",
        "l": "99",
        "last_price": "100.5",
        "v": "2.5",
    }

    normalized = BAR_V1_DICTIONARY.normalize(row)
    assert normalized["symbol"] == "BTCUSDT"
    assert normalized["timeframe"] == "1m"
    assert normalized["ts"] == datetime.fromtimestamp(1772323200, tz=timezone.utc)
    assert normalized["close"] == 100.5


def test_quality_checklist_detects_duplicate_and_non_monotonic_ts() -> None:
    rows = [
        {
            "symbol": "BTCUSDT",
            "timeframe": "1m",
            "ts": datetime(2026, 3, 1, 0, 1, tzinfo=timezone.utc),
            "open": 100.0,
            "high": 101.0,
            "low": 99.0,
            "close": 100.5,
            "volume": 1.0,
        },
        {
            "symbol": "BTCUSDT",
            "timeframe": "1m",
            "ts": datetime(2026, 3, 1, 0, 1, tzinfo=timezone.utc),
            "open": 100.0,
            "high": 101.0,
            "low": 99.0,
            "close": 100.5,
            "volume": 1.0,
        },
        {
            "symbol": "BTCUSDT",
            "timeframe": "1m",
            "ts": datetime(2026, 3, 1, 0, 0, tzinfo=timezone.utc),
            "open": 100.0,
            "high": 101.0,
            "low": 99.0,
            "close": 100.5,
            "volume": 1.0,
        },
    ]

    report = DataQualityChecklist().validate(rows, expected_symbol="BTCUSDT", expected_timeframe="1m")
    assert not report.passed
    assert {issue.code for issue in report.issues} >= {"DUPLICATE_TS", "NON_MONOTONIC_TS"}


def test_dataset_version_can_be_persisted(tmp_path) -> None:
    rows = [
        {
            "symbol": "BTCUSDT",
            "timeframe": "1m",
            "ts": datetime(2026, 3, 1, 0, 0, tzinfo=timezone.utc),
            "open": 100.0,
            "high": 101.0,
            "low": 99.0,
            "close": 100.5,
            "volume": 1.0,
        },
        {
            "symbol": "BTCUSDT",
            "timeframe": "1m",
            "ts": datetime(2026, 3, 1, 0, 1, tzinfo=timezone.utc),
            "open": 101.0,
            "high": 102.0,
            "low": 100.0,
            "close": 101.5,
            "volume": 2.0,
        },
    ]

    version = build_dataset_version(dataset="btcusdt-1m", schema_version="bar.v1", rows=rows)
    store = DatasetVersionStore(tmp_path)
    manifest = store.save(version)

    payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert payload["dataset"] == "btcusdt-1m"
    assert payload["schema_version"] == "bar.v1"
    assert payload["row_count"] == 2
    assert len(payload["checksum_sha256"]) == 64


def test_csv_data_source_quality_check_and_versioning(tmp_path) -> None:
    csv_file = tmp_path / "bars.csv"
    csv_file.write_text(
        "symbol,timeframe,ts,open,high,low,close,volume\n"
        "BTCUSDT,1m,2026-03-01T00:00:00+00:00,100,101,99,100.5,1\n"
        "BTCUSDT,1m,2026-03-01T00:01:00+00:00,101,102,100,101.5,2\n",
        encoding="utf-8",
    )

    source = CsvBarDataSource(
        path=csv_file,
        schema=CsvBarSchema(),
        quality_checklist=DataQualityChecklist(),
        version_store=DatasetVersionStore(tmp_path / "versions"),
        dataset_name="btcusdt-1m",
    )

    bars = source.fetch_bars(symbol="BTCUSDT", timeframe="1m")
    assert len(bars) == 2
    manifests = list((tmp_path / "versions").glob("*.json"))
    assert len(manifests) == 1


def test_csv_data_source_raises_on_quality_issue(tmp_path) -> None:
    csv_file = tmp_path / "bad.csv"
    csv_file.write_text(
        "symbol,timeframe,ts,open,high,low,close,volume\n"
        "BTCUSDT,1m,2026-03-01T00:00:00+00:00,100,101,99,100.5,1\n"
        "BTCUSDT,1m,2026-03-01T00:00:00+00:00,101,102,100,101.5,2\n",
        encoding="utf-8",
    )

    source = CsvBarDataSource(path=csv_file)
    with pytest.raises(ValueError, match="data quality check failed"):
        source.fetch_bars(symbol="BTCUSDT", timeframe="1m")
