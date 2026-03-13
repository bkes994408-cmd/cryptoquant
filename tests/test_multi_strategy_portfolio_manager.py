from __future__ import annotations

from datetime import datetime, timedelta, timezone

from cryptoquant.aggregation import Bar
from cryptoquant.portfolio import MultiStrategyConfig, MultiStrategyPortfolioManager, OptimizationConfig
from cryptoquant.strategy.engine import Strategy


class ConstantStrategy(Strategy):
    def __init__(self, *, strategy_name: str, qty: float) -> None:
        self._name = strategy_name
        self._qty = qty

    @property
    def name(self) -> str:
        return self._name

    def target_qty(self, bars: list[Bar]) -> float:
        return self._qty


def _bars(size: int = 8) -> list[Bar]:
    base = datetime(2026, 3, 14, 0, 0, tzinfo=timezone.utc)
    out: list[Bar] = []
    for i in range(size):
        close = 100 + i
        out.append(
            Bar(
                symbol="BTCUSDT",
                timeframe="15m",
                ts=base + timedelta(minutes=15 * i),
                open=close,
                high=close,
                low=close,
                close=close,
                volume=1.0,
            )
        )
    return out


def test_multi_strategy_manager_runs_strategies_concurrently_with_equal_weight_default() -> None:
    manager = MultiStrategyPortfolioManager(
        [
            ConstantStrategy(strategy_name="trend", qty=2.0),
            ConstantStrategy(strategy_name="carry", qty=0.0),
            ConstantStrategy(strategy_name="mean_revert", qty=-1.0),
        ],
        config=MultiStrategyConfig(min_history=3, rebalance_interval=2),
    )

    decision = manager.on_bars(_bars())

    assert decision.rebalanced is False
    assert decision.strategy_decisions["trend"].target_qty == 2.0
    assert decision.strategy_decisions["mean_revert"].target_qty == -1.0
    assert abs(decision.target_qty - (2.0 / 3.0 - 1.0 / 3.0)) < 1e-9
    assert abs(sum(decision.weights.values()) - 1.0) < 1e-9


def test_multi_strategy_manager_rebalances_from_realized_returns() -> None:
    manager = MultiStrategyPortfolioManager(
        [
            ConstantStrategy(strategy_name="trend", qty=1.0),
            ConstantStrategy(strategy_name="carry", qty=1.0),
            ConstantStrategy(strategy_name="mean_revert", qty=1.0),
        ],
        config=MultiStrategyConfig(
            min_history=4,
            rebalance_interval=1,
            optimizer_config=OptimizationConfig(risk_aversion=4.0, max_weight=0.8, iterations=600),
        ),
    )

    returns_window = [
        {"trend": 0.012, "carry": 0.006, "mean_revert": -0.004},
        {"trend": 0.013, "carry": 0.007, "mean_revert": 0.005},
        {"trend": 0.011, "carry": 0.006, "mean_revert": -0.006},
        {"trend": 0.012, "carry": 0.005, "mean_revert": 0.004},
    ]

    latest = None
    for period_ret in returns_window:
        latest = manager.on_bars(_bars(), realized_returns=period_ret)

    assert latest is not None
    assert latest.rebalanced is True
    assert latest.weights["trend"] > latest.weights["mean_revert"]
    assert all(0.0 <= weight <= 0.8 for weight in latest.weights.values())
    assert manager.last_optimization is not None


def test_multi_strategy_manager_validates_return_names() -> None:
    manager = MultiStrategyPortfolioManager(
        [
            ConstantStrategy(strategy_name="a", qty=1.0),
            ConstantStrategy(strategy_name="b", qty=1.0),
        ]
    )

    try:
        manager.on_bars(_bars(), realized_returns={"a": 0.01})
    except ValueError as exc:
        assert "same strategy names" in str(exc)
    else:
        raise AssertionError("expected ValueError")
