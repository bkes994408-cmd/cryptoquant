from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Protocol

from cryptoquant.aggregation import Bar


@dataclass(frozen=True)
class IndicatorContext:
    bars: list[Bar]


class IndicatorPlugin(Protocol):
    name: str

    def compute(self, ctx: IndicatorContext) -> list[float | None]: ...


IndicatorFactory = Callable[..., IndicatorPlugin]


class IndicatorRegistry:
    def __init__(self) -> None:
        self._plugins: dict[str, IndicatorPlugin] = {}
        self._factories: dict[str, IndicatorFactory] = {}

    def register(self, plugin: IndicatorPlugin) -> None:
        key = plugin.name.strip().lower()
        if not key:
            raise ValueError("indicator name cannot be empty")
        self._plugins[key] = plugin

    def register_factory(self, name: str, factory: IndicatorFactory) -> None:
        key = name.strip().lower()
        if not key:
            raise ValueError("indicator name cannot be empty")
        self._factories[key] = factory

    def get(self, name: str) -> IndicatorPlugin:
        key = name.strip().lower()
        if key not in self._plugins:
            raise KeyError(f"indicator not found: {name}")
        return self._plugins[key]

    def create(self, name: str, **params: str) -> IndicatorPlugin:
        key = name.strip().lower()
        values: dict[str, Any] = {k: _coerce(v) for k, v in params.items()}

        if key in self._factories:
            return self._factories[key](**values)

        plugin = self.get(name)
        if not values:
            return plugin
        return type(plugin)(**values)

    def list_names(self) -> list[str]:
        return sorted(set(self._plugins.keys()) | set(self._factories.keys()))


def _coerce(value: str) -> Any:
    lowered = value.strip().lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        pass
    return value
