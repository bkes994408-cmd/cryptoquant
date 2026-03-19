import pytest

from cryptoquant.portfolio import (
    AllocationSignal,
    CapitalAllocatorConfig,
    allocate_capital,
)


def test_allocate_capital_prefers_high_quality_strategy() -> None:
    result = allocate_capital(
        {
            "trend": AllocationSignal(
                confidence=0.88,
                recent_stability=0.82,
                drawdown=0.06,
                volatility=0.012,
                trading_cost=0.0005,
            ),
            "mean_revert": AllocationSignal(
                confidence=0.61,
                recent_stability=0.57,
                drawdown=0.18,
                volatility=0.032,
                trading_cost=0.0024,
            ),
            "carry": AllocationSignal(
                confidence=0.72,
                recent_stability=0.73,
                drawdown=0.10,
                volatility=0.018,
                trading_cost=0.0010,
            ),
        },
        total_capital=1_000_000,
        config=CapitalAllocatorConfig(cash_reserve_ratio=0.1),
    )

    assert result.reserve_capital == pytest.approx(100_000)
    assert result.investable_capital == pytest.approx(900_000)
    assert sum(result.strategy_weights.values()) == pytest.approx(1.0)
    assert sum(result.strategy_capital.values()) == pytest.approx(result.investable_capital)

    assert result.strategy_weights["trend"] > result.strategy_weights["carry"]
    assert result.strategy_weights["carry"] > result.strategy_weights["mean_revert"]


def test_allocate_capital_penalizes_drawdown_and_volatility() -> None:
    result = allocate_capital(
        {
            "stable": AllocationSignal(
                confidence=0.7,
                recent_stability=0.8,
                drawdown=0.05,
                volatility=0.01,
                trading_cost=0.0008,
            ),
            "stressed": AllocationSignal(
                confidence=0.95,
                recent_stability=0.8,
                drawdown=0.45,
                volatility=0.08,
                trading_cost=0.0008,
            ),
        },
        total_capital=500_000,
        config=CapitalAllocatorConfig(max_drawdown_limit=0.30),
    )

    assert result.breakdown["stressed"].drawdown_component == pytest.approx(0.0)
    assert result.breakdown["stressed"].volatility_component < result.breakdown["stable"].volatility_component
    assert result.strategy_weights["stable"] > result.strategy_weights["stressed"]


def test_allocate_capital_respects_weight_bounds() -> None:
    result = allocate_capital(
        {
            "alpha": AllocationSignal(1.0, 1.0, 0.0, 0.001, 0.0001),
            "beta": AllocationSignal(0.01, 0.05, 0.35, 0.09, 0.009),
            "gamma": AllocationSignal(0.01, 0.05, 0.35, 0.09, 0.009),
        },
        total_capital=100_000,
        config=CapitalAllocatorConfig(min_weight=0.1, max_weight=0.6),
    )

    assert all(weight >= 0.1 for weight in result.strategy_weights.values())
    assert all(weight <= 0.6 for weight in result.strategy_weights.values())
    assert result.strategy_weights["alpha"] == pytest.approx(0.6)


def test_allocate_capital_validates_inputs() -> None:
    with pytest.raises(ValueError, match="total_capital must be positive"):
        allocate_capital({"s": AllocationSignal(0.5, 0.5, 0.1, 0.02, 0.001)}, total_capital=0)

    with pytest.raises(ValueError, match="volatility must be >= 0"):
        allocate_capital(
            {"s": AllocationSignal(0.5, 0.5, 0.1, -0.01, 0.001)},
            total_capital=10_000,
        )

    with pytest.raises(ValueError, match="infeasible bounds"):
        allocate_capital(
            {
                "a": AllocationSignal(0.6, 0.6, 0.1, 0.02, 0.001),
                "b": AllocationSignal(0.6, 0.6, 0.1, 0.02, 0.001),
            },
            total_capital=10_000,
            config=CapitalAllocatorConfig(min_weight=0.6, max_weight=0.8),
        )
