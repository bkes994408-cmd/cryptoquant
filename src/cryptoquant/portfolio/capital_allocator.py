from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Mapping


@dataclass(frozen=True)
class AllocationSignal:
    """Inputs that are decoupled from strategy implementation details."""

    confidence: float
    recent_stability: float
    drawdown: float
    volatility: float
    trading_cost: float


@dataclass(frozen=True)
class CapitalAllocatorConfig:
    """Scoring and portfolio constraints for dynamic capital allocation."""

    cash_reserve_ratio: float = 0.05
    max_drawdown_limit: float = 0.30
    target_volatility: float = 0.02
    cost_budget: float = 0.0015
    min_weight: float = 0.05
    max_weight: float = 0.65

    confidence_weight: float = 0.30
    stability_weight: float = 0.25
    drawdown_weight: float = 0.20
    volatility_weight: float = 0.15
    trading_cost_weight: float = 0.10

    def __post_init__(self) -> None:
        if not (0 <= self.cash_reserve_ratio < 1):
            raise ValueError("cash_reserve_ratio must be in [0, 1)")
        if self.max_drawdown_limit <= 0:
            raise ValueError("max_drawdown_limit must be > 0")
        if self.target_volatility <= 0:
            raise ValueError("target_volatility must be > 0")
        if self.cost_budget <= 0:
            raise ValueError("cost_budget must be > 0")
        if not (0 <= self.min_weight <= self.max_weight <= 1):
            raise ValueError("weight bounds must satisfy 0 <= min_weight <= max_weight <= 1")

        weights = [
            self.confidence_weight,
            self.stability_weight,
            self.drawdown_weight,
            self.volatility_weight,
            self.trading_cost_weight,
        ]
        if any(weight < 0 for weight in weights):
            raise ValueError("factor weights must be >= 0")
        if sum(weights) <= 0:
            raise ValueError("sum of factor weights must be > 0")


@dataclass(frozen=True)
class AllocationBreakdown:
    confidence_component: float
    stability_component: float
    drawdown_component: float
    volatility_component: float
    trading_cost_component: float
    composite_score: float


@dataclass(frozen=True)
class CapitalAllocationResult:
    total_capital: float
    investable_capital: float
    reserve_capital: float
    strategy_weights: dict[str, float]
    strategy_capital: dict[str, float]
    strategy_scores: dict[str, float]
    breakdown: dict[str, AllocationBreakdown]


def allocate_capital(
    signals: Mapping[str, AllocationSignal],
    *,
    total_capital: float,
    config: CapitalAllocatorConfig = CapitalAllocatorConfig(),
) -> CapitalAllocationResult:
    if total_capital <= 0:
        raise ValueError("total_capital must be positive")
    if len(signals) < 1:
        raise ValueError("at least one strategy signal is required")

    reserve = total_capital * config.cash_reserve_ratio
    investable = total_capital - reserve

    raw_scores: dict[str, float] = {}
    breakdown: dict[str, AllocationBreakdown] = {}

    for name, signal in signals.items():
        _validate_signal(name, signal)

        confidence_component = _clamp01(signal.confidence)
        stability_component = _clamp01(signal.recent_stability)
        drawdown_component = 1.0 - _clamp01(signal.drawdown / config.max_drawdown_limit)
        volatility_component = config.target_volatility / (signal.volatility + config.target_volatility)
        trading_cost_component = config.cost_budget / (signal.trading_cost + config.cost_budget)

        composite = _weighted_mean(
            [
                confidence_component,
                stability_component,
                drawdown_component,
                volatility_component,
                trading_cost_component,
            ],
            [
                config.confidence_weight,
                config.stability_weight,
                config.drawdown_weight,
                config.volatility_weight,
                config.trading_cost_weight,
            ],
        )

        floor_bias = max(config.min_weight * 0.5, 0.01)
        score = max(composite, floor_bias)

        raw_scores[name] = score
        breakdown[name] = AllocationBreakdown(
            confidence_component=confidence_component,
            stability_component=stability_component,
            drawdown_component=drawdown_component,
            volatility_component=volatility_component,
            trading_cost_component=trading_cost_component,
            composite_score=composite,
        )

    weights = _project_weights(
        raw_scores,
        total=1.0,
        min_weight=config.min_weight,
        max_weight=config.max_weight,
    )

    strategy_capital = {name: investable * w for name, w in weights.items()}

    return CapitalAllocationResult(
        total_capital=total_capital,
        investable_capital=investable,
        reserve_capital=reserve,
        strategy_weights=weights,
        strategy_capital=strategy_capital,
        strategy_scores=raw_scores,
        breakdown=breakdown,
    )


def _validate_signal(name: str, signal: AllocationSignal) -> None:
    values = {
        "confidence": signal.confidence,
        "recent_stability": signal.recent_stability,
        "drawdown": signal.drawdown,
        "volatility": signal.volatility,
        "trading_cost": signal.trading_cost,
    }
    for key, value in values.items():
        if not isfinite(value):
            raise ValueError(f"non-finite {key} for strategy: {name}")

    if signal.volatility < 0:
        raise ValueError(f"volatility must be >= 0 for strategy: {name}")
    if signal.trading_cost < 0:
        raise ValueError(f"trading_cost must be >= 0 for strategy: {name}")
    if signal.drawdown < 0:
        raise ValueError(f"drawdown must be >= 0 for strategy: {name}")


def _weighted_mean(values: list[float], weights: list[float]) -> float:
    total_weight = sum(weights)
    if total_weight <= 0:
        raise ValueError("sum(weights) must be > 0")
    return sum(v * w for v, w in zip(values, weights)) / total_weight


def _project_weights(
    raw_scores: Mapping[str, float],
    *,
    total: float,
    min_weight: float,
    max_weight: float,
) -> dict[str, float]:
    names = sorted(raw_scores.keys())
    n = len(names)

    if n * min_weight > total + 1e-12:
        raise ValueError("infeasible bounds: min_weight * n exceeds total")
    if n * max_weight < total - 1e-12:
        raise ValueError("infeasible bounds: max_weight * n below total")

    raw_sum = sum(max(raw_scores[name], 0.0) for name in names)
    if raw_sum <= 0:
        base = {name: total / n for name in names}
    else:
        base = {name: total * max(raw_scores[name], 0.0) / raw_sum for name in names}

    projected = dict(base)
    for _ in range(16):
        clamped_high = [name for name, value in projected.items() if value > max_weight]
        clamped_low = [name for name, value in projected.items() if value < min_weight]
        if not clamped_high and not clamped_low:
            break

        fixed = set(clamped_high + clamped_low)
        for name in clamped_high:
            projected[name] = max_weight
        for name in clamped_low:
            projected[name] = min_weight

        remain = total - sum(projected[name] for name in fixed)
        free = [name for name in names if name not in fixed]
        if not free:
            break

        free_base = sum(base[name] for name in free)
        if free_base <= 0:
            even = remain / len(free)
            for name in free:
                projected[name] = even
        else:
            for name in free:
                projected[name] = remain * base[name] / free_base

    final_sum = sum(projected.values())
    if final_sum <= 0:
        raise ValueError("projected weights sum must be > 0")

    residual = total - final_sum
    if abs(residual) > 1e-12:
        if residual > 0:
            adjustable = sorted(names, key=lambda n: projected[n])
            for name in adjustable:
                room = max_weight - projected[name]
                if room <= 0:
                    continue
                delta = min(room, residual)
                projected[name] += delta
                residual -= delta
                if residual <= 1e-12:
                    break
        else:
            adjustable = sorted(names, key=lambda n: projected[n], reverse=True)
            needed = -residual
            for name in adjustable:
                room = projected[name] - min_weight
                if room <= 0:
                    continue
                delta = min(room, needed)
                projected[name] -= delta
                needed -= delta
                if needed <= 1e-12:
                    break

    return projected


def _clamp01(value: float) -> float:
    if value < 0:
        return 0.0
    if value > 1:
        return 1.0
    return value
