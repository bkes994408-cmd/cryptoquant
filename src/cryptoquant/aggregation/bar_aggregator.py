from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Iterable, Iterator, Literal

TargetTimeframe = Literal["15m", "1h"]

_BUCKET_MINUTES: dict[TargetTimeframe, int] = {"15m": 15, "1h": 60}


@dataclass(frozen=True)
class Bar:
    symbol: str
    timeframe: str
    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


class BarAggregator:
    """Aggregate 1m bars into larger timeframes with optional gap fill."""

    def __init__(self, *, gap_fill: bool = True) -> None:
        self._gap_fill = gap_fill

    def aggregate(
        self,
        bars_1m: Iterable[Bar],
        target: TargetTimeframe,
    ) -> list[Bar]:
        bucket_minutes = _BUCKET_MINUTES[target]
        normalized = sorted(bars_1m, key=lambda b: b.ts)
        if not normalized:
            return []

        self._validate_1m_bars(normalized)
        stream = self._fill_gaps(normalized) if self._gap_fill else iter(normalized)
        return self._aggregate_stream(stream, bucket_minutes, target)

    def _validate_1m_bars(self, bars: list[Bar]) -> None:
        first = bars[0]
        for bar in bars:
            if bar.timeframe != "1m":
                raise ValueError("BarAggregator only accepts 1m bars as input")
            if bar.symbol != first.symbol:
                raise ValueError("All bars must be for the same symbol")

    def _fill_gaps(self, bars: list[Bar]) -> Iterator[Bar]:
        prev: Bar | None = None
        for bar in bars:
            if prev is not None:
                missing = int((bar.ts - prev.ts).total_seconds() // 60) - 1
                for i in range(missing):
                    ts = prev.ts + timedelta(minutes=i + 1)
                    px = prev.close
                    yield Bar(
                        symbol=prev.symbol,
                        timeframe="1m",
                        ts=ts,
                        open=px,
                        high=px,
                        low=px,
                        close=px,
                        volume=0.0,
                    )
            yield bar
            prev = bar

    def _aggregate_stream(
        self,
        stream: Iterable[Bar],
        bucket_minutes: int,
        target: TargetTimeframe,
    ) -> list[Bar]:
        out: list[Bar] = []

        current_start: datetime | None = None
        current_symbol: str | None = None
        o = h = low = c = v = 0.0

        for bar in stream:
            bucket_start = self._floor_to_bucket(bar.ts, bucket_minutes)

            if current_start is None:
                current_start = bucket_start
                current_symbol = bar.symbol
                o = h = low = c = bar.open
                h = max(h, bar.high)
                low = min(low, bar.low)
                c = bar.close
                v = bar.volume
                continue

            if bucket_start != current_start:
                out.append(
                    Bar(
                        symbol=current_symbol or bar.symbol,
                        timeframe=target,
                        ts=current_start,
                        open=o,
                        high=h,
                        low=low,
                        close=c,
                        volume=v,
                    )
                )
                current_start = bucket_start
                current_symbol = bar.symbol
                o = h = low = c = bar.open
                h = max(h, bar.high)
                low = min(low, bar.low)
                c = bar.close
                v = bar.volume
            else:
                h = max(h, bar.high)
                low = min(low, bar.low)
                c = bar.close
                v += bar.volume

        if current_start is not None:
            out.append(
                Bar(
                    symbol=current_symbol or "",
                    timeframe=target,
                    ts=current_start,
                    open=o,
                    high=h,
                    low=low,
                    close=c,
                    volume=v,
                )
            )

        return out

    @staticmethod
    def _floor_to_bucket(ts: datetime, bucket_minutes: int) -> datetime:
        minute = (ts.minute // bucket_minutes) * bucket_minutes
        return ts.replace(minute=minute, second=0, microsecond=0)
