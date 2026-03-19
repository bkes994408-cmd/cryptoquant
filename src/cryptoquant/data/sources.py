from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterable, Protocol

from cryptoquant.aggregation import Bar
from cryptoquant.data.checklist import DataQualityChecklist
from cryptoquant.data.dictionary import BAR_V1_DICTIONARY, DataDictionary
from cryptoquant.data.versioning import DatasetVersionStore, build_dataset_version


class DataSource(Protocol):
    """資料源抽象層：回傳指定區間的 K 線資料。"""

    def fetch_bars(
        self,
        *,
        symbol: str,
        timeframe: str,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[Bar]: ...


@dataclass(frozen=True)
class CsvBarSchema:
    symbol_col: str = "symbol"
    timeframe_col: str = "timeframe"
    ts_col: str = "ts"
    open_col: str = "open"
    high_col: str = "high"
    low_col: str = "low"
    close_col: str = "close"
    volume_col: str = "volume"


@dataclass
class InMemoryBarDataSource:
    bars: list[Bar]

    def fetch_bars(
        self,
        *,
        symbol: str,
        timeframe: str,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[Bar]:
        out: list[Bar] = []
        for bar in self.bars:
            if bar.symbol != symbol or bar.timeframe != timeframe:
                continue
            if start and bar.ts < start:
                continue
            if end and bar.ts > end:
                continue
            out.append(bar)
        return sorted(out, key=lambda b: b.ts)


@dataclass
class CsvBarDataSource:
    path: Path
    schema: CsvBarSchema = CsvBarSchema()
    dictionary: DataDictionary = BAR_V1_DICTIONARY
    quality_checklist: DataQualityChecklist | None = field(default_factory=DataQualityChecklist)
    version_store: DatasetVersionStore | None = None
    dataset_name: str = "historical-bars"

    def fetch_bars(
        self,
        *,
        symbol: str,
        timeframe: str,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[Bar]:
        normalized_rows: list[dict[str, object]] = []
        with self.path.open("r", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                raw = {
                    "symbol": row.get(self.schema.symbol_col),
                    "timeframe": row.get(self.schema.timeframe_col),
                    "ts": row.get(self.schema.ts_col),
                    "open": row.get(self.schema.open_col),
                    "high": row.get(self.schema.high_col),
                    "low": row.get(self.schema.low_col),
                    "close": row.get(self.schema.close_col),
                    "volume": row.get(self.schema.volume_col, 0.0),
                }
                normalized = self.dictionary.normalize(raw)
                if normalized["symbol"] != symbol or normalized["timeframe"] != timeframe:
                    continue
                ts = normalized["ts"]
                if isinstance(ts, datetime):
                    if start and ts < start:
                        continue
                    if end and ts > end:
                        continue
                normalized_rows.append(normalized)

        if self.quality_checklist is not None:
            report = self.quality_checklist.validate(
                normalized_rows,
                expected_symbol=symbol,
                expected_timeframe=timeframe,
            )
            if not report.passed:
                head = ", ".join(f"{i.code}@{i.row_index}" for i in report.issues[:5])
                raise ValueError(f"data quality check failed ({report.issue_count} issues): {head}")

        if self.version_store is not None:
            version = build_dataset_version(
                dataset=self.dataset_name,
                schema_version=self.dictionary.schema_version,
                rows=normalized_rows,
            )
            self.version_store.save(version)

        bars = [
            Bar(
                symbol=str(row["symbol"]),
                timeframe=str(row["timeframe"]),
                ts=row["ts"],
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=float(row["volume"]),
            )
            for row in normalized_rows
        ]
        return sorted(bars, key=lambda b: b.ts)


@dataclass
class CompositeBarDataSource:
    sources: list[DataSource]

    def fetch_bars(
        self,
        *,
        symbol: str,
        timeframe: str,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[Bar]:
        merged: list[Bar] = []
        for source in self.sources:
            merged.extend(source.fetch_bars(symbol=symbol, timeframe=timeframe, start=start, end=end))

        dedup: dict[datetime, Bar] = {}
        for bar in merged:
            dedup[bar.ts] = bar
        return [dedup[ts] for ts in sorted(dedup.keys())]


def ensure_data_source(source: DataSource | Iterable[Bar]) -> DataSource:
    if hasattr(source, "fetch_bars"):
        return source  # type: ignore[return-value]
    return InMemoryBarDataSource(list(source))
