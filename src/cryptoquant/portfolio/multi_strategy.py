from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from math import isfinite
from typing import Mapping, Sequence

from cryptoquant.aggregation import Bar
from cryptoquant.portfolio.optimizer import (
    OptimizationConfig,
    OptimizationResult,
    optimize_strategy_weights,
)
from cryptoquant.strategy.engine import Strategy, StrategyDecision, StrategyEngine


@dataclass(frozen=True)
class MultiStrategyConfig:
    min_history: int = 20
    rebalance_interval: int = 10
    optimizer_config: OptimizationConfig = field(default_factory=OptimizationConfig)


@dataclass(frozen=True)
class MultiStrategyDecision:
    target_qty: float
    signal: str
    strategy_decisions: dict[str, StrategyDecision]
    weights: dict[str, float]
    rebalanced: bool
    diversification_score: float


class MultiStrategyPortfolioManager:
    """Run multiple strategies concurrently and allocate capital by optimized weights."""

    def __init__(self, strategies: Sequence[Strategy], *, config: MultiStrategyConfig = MultiStrategyConfig()) -> None:
        if len(strategies) < 2:
            raise ValueError("at least two strategies are required")
        if config.min_history < 2:
            raise ValueError("min_history must be >= 2")
        if config.rebalance_interval <= 0:
            raise ValueError("rebalance_interval must be > 0")

        names = [strategy.name for strategy in strategies]
        if len(set(names)) != len(names):
            raise ValueError("strategy names must be unique")

        self._config = config
        self._engines = {strategy.name: StrategyEngine(strategy) for strategy in strategies}
        self._returns: dict[str, deque[float]] = {
            name: deque(maxlen=max(2000, config.min_history * 5)) for name in sorted(self._engines.keys())
        }
        n = len(self._engines)
        self._weights = {name: 1.0 / n for name in sorted(self._engines.keys())}
        self._steps_since_rebalance = 0
        self._last_optimization: OptimizationResult | None = None

    @property
    def weights(self) -> dict[str, float]:
        return dict(self._weights)

    @property
    def last_optimization(self) -> OptimizationResult | None:
        return self._last_optimization

    def update_strategy_returns(self, realized_returns: Mapping[str, float]) -> None:
        expected_names = set(self._returns.keys())
        if set(realized_returns.keys()) != expected_names:
            raise ValueError("realized_returns must contain exactly the same strategy names")

        for name, value in realized_returns.items():
            ret = float(value)
            if not isfinite(ret):
                raise ValueError(f"non-finite return for strategy: {name}")
            self._returns[name].append(ret)

    def on_bars(
        self,
        bars: Sequence[Bar],
        *,
        realized_returns: Mapping[str, float] | None = None,
    ) -> MultiStrategyDecision:
        strategy_decisions = {
            name: engine.on_bars(bars) for name, engine in self._engines.items()
        }

        if realized_returns is not None:
            self.update_strategy_returns(realized_returns)

        rebalanced = self._maybe_rebalance_weights()
        weighted_target = sum(
            self._weights[name] * strategy_decisions[name].target_qty
            for name in self._weights.keys()
        )

        active_signals = [
            f"{name}:{decision.signal}"
            for name, decision in sorted(strategy_decisions.items())
            if abs(decision.target_qty) > 0.0
        ]
        signal = "portfolio(" + (", ".join(active_signals) if active_signals else "flat") + ")"

        return MultiStrategyDecision(
            target_qty=weighted_target,
            signal=signal,
            strategy_decisions=dict(strategy_decisions),
            weights=dict(self._weights),
            rebalanced=rebalanced,
            diversification_score=1.0 - sum(weight * weight for weight in self._weights.values()),
        )

    def _maybe_rebalance_weights(self) -> bool:
        self._steps_since_rebalance += 1
        if self._steps_since_rebalance < self._config.rebalance_interval:
            return False

        lengths = {len(series) for series in self._returns.values()}
        if len(lengths) != 1:
            return False

        history_len = next(iter(lengths))
        if history_len < self._config.min_history:
            return False

        optimization = optimize_strategy_weights(
            {name: list(series) for name, series in self._returns.items()},
            config=self._config.optimizer_config,
        )
        self._weights = optimization.weights
        self._last_optimization = optimization
        self._steps_since_rebalance = 0
        return True
