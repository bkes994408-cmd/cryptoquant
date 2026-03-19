from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, Protocol

from cryptoquant.aggregation import Bar


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

    def fetch_bars(
        self,
        *,
        symbol: str,
        timeframe: str,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[Bar]:
        import csv

        rows: list[Bar] = []
        with self.path.open("r", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                if row["symbol"] != symbol or row["timeframe"] != timeframe:
                    continue
                ts = datetime.fromisoformat(row["ts"])
                if start and ts < start:
                    continue
                if end and ts > end:
                    continue
                rows.append(
                    Bar(
                        symbol=row["symbol"],
                        timeframe=row["timeframe"],
                        ts=ts,
                        open=float(row["open"]),
                        high=float(row["high"]),
                        low=float(row["low"]),
                        close=float(row["close"]),
                        volume=float(row.get("volume", 0.0)),
                    )
                )
        return sorted(rows, key=lambda b: b.ts)


def ensure_data_source(source: DataSource | Iterable[Bar]) -> DataSource:
    if hasattr(source, "fetch_bars"):
        return source  # type: ignore[return-value]
    return InMemoryBarDataSource(list(source))
