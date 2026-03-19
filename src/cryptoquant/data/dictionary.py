from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from math import isfinite
from typing import Any


@dataclass(frozen=True)
class FieldSpec:
    name: str
    python_type: type
    required: bool = True
    aliases: tuple[str, ...] = ()
    description: str = ""
    default: Any = None


@dataclass(frozen=True)
class DataDictionary:
    """Canonical schema definition and row normalizer."""

    schema_name: str
    schema_version: str
    fields: tuple[FieldSpec, ...] = field(default_factory=tuple)

    def alias_map(self) -> dict[str, str]:
        mapping: dict[str, str] = {}
        for spec in self.fields:
            mapping[spec.name] = spec.name
            for alias in spec.aliases:
                mapping[alias] = spec.name
        return mapping

    def normalize(self, row: dict[str, Any]) -> dict[str, Any]:
        remapped = self._remap_aliases(row)
        out: dict[str, Any] = {}
        for spec in self.fields:
            raw = remapped.get(spec.name)
            if raw in (None, ""):
                if spec.required and spec.default is None:
                    raise ValueError(f"missing required field: {spec.name}")
                out[spec.name] = spec.default
                continue
            out[spec.name] = _coerce_value(spec.python_type, raw, field_name=spec.name)
        return out

    def _remap_aliases(self, row: dict[str, Any]) -> dict[str, Any]:
        mapping = self.alias_map()
        out: dict[str, Any] = {}
        for key, value in row.items():
            canonical = mapping.get(key)
            if canonical is None:
                continue
            out[canonical] = value
        return out


BAR_V1_DICTIONARY = DataDictionary(
    schema_name="ohlcv_bar",
    schema_version="bar.v1",
    fields=(
        FieldSpec(name="symbol", python_type=str, required=True, aliases=("asset", "pair")),
        FieldSpec(name="timeframe", python_type=str, required=True, aliases=("tf", "interval")),
        FieldSpec(name="ts", python_type=datetime, required=True, aliases=("timestamp", "open_time", "time")),
        FieldSpec(name="open", python_type=float, required=True, aliases=("o",)),
        FieldSpec(name="high", python_type=float, required=True, aliases=("h",)),
        FieldSpec(name="low", python_type=float, required=True, aliases=("l",)),
        FieldSpec(name="close", python_type=float, required=True, aliases=("c", "last_price")),
        FieldSpec(name="volume", python_type=float, required=False, aliases=("v",), default=0.0),
    ),
)


def _coerce_value(expected_type: type, raw: Any, *, field_name: str) -> Any:
    if expected_type is str:
        return str(raw)

    if expected_type is float:
        value = float(raw)
        if not isfinite(value):
            raise ValueError(f"{field_name} must be finite")
        return value

    if expected_type is datetime:
        return _parse_datetime(raw)

    return raw


def _parse_datetime(raw: Any) -> datetime:
    value = str(raw).strip()

    if value.isdigit():
        if len(value) >= 13:
            return datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc)
        return datetime.fromtimestamp(int(value), tz=timezone.utc)

    normalized = value.replace("Z", "+00:00")
    ts = datetime.fromisoformat(normalized)
    if ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts
