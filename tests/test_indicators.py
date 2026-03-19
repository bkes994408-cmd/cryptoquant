from __future__ import annotations

from datetime import datetime, timedelta, timezone

from cryptoquant.aggregation import Bar
from cryptoquant.indicators import IndicatorContext, IndicatorRegistry, SMAIndicator


def _bars() -> list[Bar]:
    base = datetime(2026, 3, 1, tzinfo=timezone.utc)
    return [
        Bar("BTCUSDT", "1m", base + timedelta(minutes=i), i + 1, i + 1, i + 1, i + 1, 1)
        for i in range(5)
    ]


def test_indicator_registry_register_and_get() -> None:
    registry = IndicatorRegistry()
    registry.register(SMAIndicator(window=3))

    plugin = registry.get("sma")
    values = plugin.compute(IndicatorContext(bars=_bars()))

    assert values[:2] == [None, None]
    assert values[2] == 2.0


def test_indicator_registry_list_names_sorted() -> None:
    registry = IndicatorRegistry()
    registry.register(SMAIndicator(name="zeta"))
    registry.register(SMAIndicator(name="alpha"))

    assert registry.list_names() == ["alpha", "zeta"]


def test_indicator_registry_create_with_param_coercion() -> None:
    registry = IndicatorRegistry()
    registry.register(SMAIndicator())

    plugin = registry.create("sma", window="3")
    values = plugin.compute(IndicatorContext(bars=_bars()))

    assert values[2] == 2.0


def test_indicator_registry_factory_allows_custom_plugin() -> None:
    registry = IndicatorRegistry()
    registry.register_factory("const", lambda value=10: SMAIndicator(window=int(value), name="const"))

    plugin = registry.create("const", value="3")
    values = plugin.compute(IndicatorContext(bars=_bars()))

    assert values[2] == 2.0
