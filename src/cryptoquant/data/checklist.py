from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class DataQualityIssue:
    row_index: int
    code: str
    message: str


@dataclass(frozen=True)
class DataQualityReport:
    total_rows: int
    issue_count: int
    issues: tuple[DataQualityIssue, ...]

    @property
    def passed(self) -> bool:
        return self.issue_count == 0


class DataQualityChecklist:
    """Basic data quality checks for historical OHLCV rows."""

    def __init__(self, *, allow_duplicate_ts: bool = False) -> None:
        self._allow_duplicate_ts = allow_duplicate_ts

    def validate(
        self,
        rows: list[dict[str, Any]],
        *,
        expected_symbol: str | None = None,
        expected_timeframe: str | None = None,
    ) -> DataQualityReport:
        issues: list[DataQualityIssue] = []
        previous_ts: datetime | None = None
        seen_ts: set[datetime] = set()

        for idx, row in enumerate(rows):
            symbol = str(row.get("symbol", ""))
            timeframe = str(row.get("timeframe", ""))
            ts = row.get("ts")
            open_price = row.get("open")
            high_price = row.get("high")
            low_price = row.get("low")
            close_price = row.get("close")
            volume = row.get("volume", 0.0)

            if not symbol:
                issues.append(DataQualityIssue(idx, "MISSING_SYMBOL", "symbol is required"))
            if not timeframe:
                issues.append(DataQualityIssue(idx, "MISSING_TIMEFRAME", "timeframe is required"))
            if not isinstance(ts, datetime):
                issues.append(DataQualityIssue(idx, "INVALID_TS", "ts must be datetime"))
                continue

            for field_name, field_value in (
                ("open", open_price),
                ("high", high_price),
                ("low", low_price),
                ("close", close_price),
                ("volume", volume),
            ):
                if not isinstance(field_value, (int, float)):
                    issues.append(
                        DataQualityIssue(idx, "INVALID_NUMERIC", f"{field_name} must be numeric")
                    )

            if isinstance(high_price, (int, float)) and isinstance(low_price, (int, float)) and high_price < low_price:
                issues.append(DataQualityIssue(idx, "INVALID_RANGE", "high must be >= low"))

            if all(isinstance(x, (int, float)) for x in (open_price, high_price, low_price, close_price)):
                if not (low_price <= open_price <= high_price):
                    issues.append(DataQualityIssue(idx, "OPEN_OUT_OF_RANGE", "open must be within [low, high]"))
                if not (low_price <= close_price <= high_price):
                    issues.append(DataQualityIssue(idx, "CLOSE_OUT_OF_RANGE", "close must be within [low, high]"))

            if isinstance(volume, (int, float)) and volume < 0:
                issues.append(DataQualityIssue(idx, "NEGATIVE_VOLUME", "volume must be >= 0"))

            if expected_symbol and symbol and symbol != expected_symbol:
                issues.append(
                    DataQualityIssue(idx, "UNEXPECTED_SYMBOL", f"symbol={symbol} expected={expected_symbol}")
                )

            if expected_timeframe and timeframe and timeframe != expected_timeframe:
                issues.append(
                    DataQualityIssue(
                        idx,
                        "UNEXPECTED_TIMEFRAME",
                        f"timeframe={timeframe} expected={expected_timeframe}",
                    )
                )

            if previous_ts and ts < previous_ts:
                issues.append(DataQualityIssue(idx, "NON_MONOTONIC_TS", "timestamp must be non-decreasing"))
            previous_ts = ts

            if ts in seen_ts and not self._allow_duplicate_ts:
                issues.append(DataQualityIssue(idx, "DUPLICATE_TS", "duplicate timestamp found"))
            seen_ts.add(ts)

        return DataQualityReport(total_rows=len(rows), issue_count=len(issues), issues=tuple(issues))
