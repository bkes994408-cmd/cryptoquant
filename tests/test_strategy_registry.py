from __future__ import annotations

from cryptoquant.strategy import StrategyLifecycle, StrategyRegistry, StrategyVersionStatus


def test_strategy_registry_generates_unique_strategy_ids() -> None:
    registry = StrategyRegistry()

    first = registry.register_strategy(name="Trend Alpha")
    second = registry.register_strategy(name="Trend Alpha")

    assert first.startswith("strat-trend-alpha-")
    assert second.startswith("strat-trend-alpha-")
    assert first != second


def test_strategy_registry_rejects_invalid_or_duplicate_strategy_id() -> None:
    registry = StrategyRegistry()

    try:
        registry.register_strategy(name="x", strategy_id="trend-001")
    except ValueError as exc:
        assert "must start" in str(exc)
    else:
        raise AssertionError("expected ValueError")

    strategy_id = registry.register_strategy(name="x", strategy_id="strat-trend-001")
    assert strategy_id == "strat-trend-001"

    try:
        registry.register_strategy(name="y", strategy_id="strat-trend-001")
    except ValueError as exc:
        assert "already registered" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_strategy_registry_validates_lifecycle_transition_and_activation_guard() -> None:
    registry = StrategyRegistry()
    strategy_id = registry.register_strategy(name="Momentum")

    try:
        registry.set_lifecycle(strategy_id, StrategyLifecycle.ACTIVE)
    except ValueError as exc:
        assert "without an active version" in str(exc)
    else:
        raise AssertionError("expected ValueError")

    registry.add_version(strategy_id, version="1.0.0", activate=True)
    registry.set_lifecycle(strategy_id, StrategyLifecycle.ACTIVE)
    registry.set_lifecycle(strategy_id, StrategyLifecycle.PAUSED)
    registry.set_lifecycle(strategy_id, StrategyLifecycle.DEPRECATED)
    registry.set_lifecycle(strategy_id, StrategyLifecycle.ARCHIVED)

    detail = registry.get(strategy_id)
    assert detail.lifecycle == StrategyLifecycle.ARCHIVED


def test_strategy_registry_manages_feature_dependencies_with_version_requirements() -> None:
    registry = StrategyRegistry()
    strategy_id = registry.register_strategy(name="CrossAsset")

    registry.register_feature(name="orderbook_imbalance", schema_version="2.1.0")
    registry.add_feature_dependency(
        strategy_id,
        feature_name="orderbook_imbalance",
        required=True,
        min_schema_version="2.0.0",
    )

    detail = registry.get(strategy_id)
    assert len(detail.dependencies) == 1
    assert detail.dependencies[0].feature_name == "orderbook_imbalance"
    assert detail.dependencies[0].min_schema_version == "2.0.0"

    registry.register_feature(name="vwap_deviation", schema_version="1.1.0")
    try:
        registry.add_feature_dependency(
            strategy_id,
            feature_name="vwap_deviation",
            min_schema_version="1.2.0",
        )
    except ValueError as exc:
        assert "does not meet" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_strategy_registry_centralizes_version_status_and_switches_active_version() -> None:
    registry = StrategyRegistry()
    strategy_id = registry.register_strategy(name="Mean Reversion")

    registry.add_version(strategy_id, version="1.0.0", changelog="bootstrap", activate=True)
    registry.add_version(strategy_id, version="1.1.0", changelog="improved filters")
    registry.activate_version(strategy_id, "1.1.0")

    detail = registry.get(strategy_id)
    versions = {item.version: item.status for item in detail.versions}

    assert detail.active_version == "1.1.0"
    assert versions["1.0.0"] == StrategyVersionStatus.DEPRECATED
    assert versions["1.1.0"] == StrategyVersionStatus.ACTIVE

    registry.deprecate_version(strategy_id, "1.1.0")
    detail2 = registry.get(strategy_id)
    assert detail2.active_version is None
    latest = {item.version: item.status for item in detail2.versions}
    assert latest["1.1.0"] == StrategyVersionStatus.DEPRECATED


def test_strategy_registry_resolves_regime_routes_with_normalized_weights() -> None:
    registry = StrategyRegistry()

    trend_id = registry.register_strategy(name="Trend")
    mean_id = registry.register_strategy(name="MeanRevert")

    registry.add_version(trend_id, version="1.0.0", activate=True)
    registry.add_version(mean_id, version="1.0.0", activate=True)
    registry.set_lifecycle(trend_id, StrategyLifecycle.ACTIVE)
    registry.set_lifecycle(mean_id, StrategyLifecycle.ACTIVE)

    registry.configure_regime_route("trend", strategy_id=trend_id, weight=3.0)
    registry.configure_regime_route("trend", strategy_id=mean_id, weight=1.0)

    bindings = registry.resolve_regime_bindings("trend")
    by_id = {item.strategy_id: item for item in bindings}

    assert len(bindings) == 2
    assert abs(by_id[trend_id].weight - 0.75) < 1e-9
    assert abs(by_id[mean_id].weight - 0.25) < 1e-9
    assert by_id[trend_id].version == "1.0.0"


def test_strategy_registry_regime_routes_skip_non_active_when_required() -> None:
    registry = StrategyRegistry()
    strategy_id = registry.register_strategy(name="EventDrive")
    registry.add_version(strategy_id, version="2.0.0", activate=True)
    registry.configure_regime_route("event", strategy_id=strategy_id, weight=1.0)

    assert registry.resolve_regime_bindings("event") == ()

    registry.set_lifecycle(strategy_id, StrategyLifecycle.ACTIVE)
    bindings = registry.resolve_regime_bindings("event")
    assert len(bindings) == 1
    assert bindings[0].strategy_id == strategy_id
