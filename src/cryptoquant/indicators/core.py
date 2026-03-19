from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from cryptoquant.aggregation import Bar


@dataclass(frozen=True)
class IndicatorContext:
    bars: list[Bar]


class IndicatorPlugin(Protocol):
    name: str

    def compute(self, ctx: IndicatorContext) -> list[float | None]: ...


class IndicatorRegistry:
    def __init__(self) -> None:
        self._plugins: dict[str, IndicatorPlugin] = {}

    def register(self, plugin: IndicatorPlugin) -> None:
        key = plugin.name.strip().lower()
        if not key:
            raise ValueError("indicator name cannot be empty")
        self._plugins[key] = plugin

    def get(self, name: str) -> IndicatorPlugin:
        key = name.strip().lower()
        if key not in self._plugins:
            raise KeyError(f"indicator not found: {name}")
        return self._plugins[key]

    def list_names(self) -> list[str]:
        return sorted(self._plugins.keys())
