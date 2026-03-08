from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from cryptoquant.events.market import MarketEvent


@dataclass(frozen=True)
class CSVDataSourceConfig:
    """CSV data source schema configuration.

    Supports common variants found in exchange export/history files.
    """

    ts_col: str = "timestamp"
    close_col: str = "close"
    symbol_col: str | None = "symbol"
    timeframe_col: str | None = "timeframe"
    source: str = "csv"
    default_symbol: str = "BTCUSDT"
    default_timeframe: str = "1m"


class CSVMarketEventSource:
    """Load backtest `MarketEvent` from CSV files."""

    def __init__(self, config: CSVDataSourceConfig | None = None) -> None:
        self._config = config or CSVDataSourceConfig()

    def load(self, file_path: str | Path) -> list[MarketEvent]:
        path = Path(file_path)
        with path.open("r", newline="", encoding="utf-8") as f:
            rows = csv.DictReader(f)
            out: list[MarketEvent] = []
            for row in rows:
                ts = _parse_ts(row[self._config.ts_col])
                close = float(row[self._config.close_col])
                symbol = row[self._config.symbol_col] if self._config.symbol_col else self._config.default_symbol
                timeframe = (
                    row[self._config.timeframe_col] if self._config.timeframe_col else self._config.default_timeframe
                )
                out.append(
                    MarketEvent(
                        symbol=(symbol or self._config.default_symbol),
                        timeframe=(timeframe or self._config.default_timeframe),
                        close=close,
                        ts=ts,
                        source=self._config.source,
                    )
                )

        return sorted(out, key=lambda x: x.ts)


class MultiSourceEventLoader:
    """Merge multiple event iterables into one deterministic stream."""

    @staticmethod
    def merge(*event_streams: Iterable[MarketEvent]) -> list[MarketEvent]:
        merged: list[MarketEvent] = []
        for stream in event_streams:
            merged.extend(stream)

        merged.sort(key=lambda e: (e.ts, e.symbol, e.timeframe, e.source))

        # De-duplicate exact event identity if overlapped data sources are provided.
        deduped: list[MarketEvent] = []
        seen: set[tuple[str, str, datetime, float, str]] = set()
        for event in merged:
            key = (event.symbol, event.timeframe, event.ts, event.close, event.source)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(event)

        return deduped


def _parse_ts(raw: str) -> datetime:
    value = raw.strip()
    if value.isdigit():
        if len(value) >= 13:
            return datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc)
        return datetime.fromtimestamp(int(value), tz=timezone.utc)

    # ISO-8601, with optional trailing Z.
    normalized = value.replace("Z", "+00:00")
    ts = datetime.fromisoformat(normalized)
    if ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts
