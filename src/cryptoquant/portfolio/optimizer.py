from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from statistics import fmean
from typing import Mapping, Sequence


@dataclass(frozen=True)
class StrategyStats:
    name: str
    mean_return: float
    volatility: float


@dataclass(frozen=True)
class OptimizationConfig:
    risk_aversion: float = 2.0
    max_weight: float = 0.7
    min_weight: float = 0.0
    learning_rate: float = 0.08
    iterations: int = 500
    annualization_factor: float = 365.0


@dataclass(frozen=True)
class OptimizationResult:
    weights: dict[str, float]
    expected_return: float
    expected_volatility: float
    sharpe_like: float
    strategy_stats: list[StrategyStats]


def optimize_strategy_weights(
    strategy_returns: Mapping[str, Sequence[float]],
    *,
    config: OptimizationConfig = OptimizationConfig(),
) -> OptimizationResult:
    names = sorted(strategy_returns.keys())
    if len(names) < 2:
        raise ValueError("at least two strategies are required")

    lengths = {len(strategy_returns[name]) for name in names}
    if len(lengths) != 1 or next(iter(lengths)) < 2:
        raise ValueError("all strategies must have same length >= 2")

    if config.iterations <= 0:
        raise ValueError("iterations must be > 0")
    if config.learning_rate <= 0:
        raise ValueError("learning_rate must be > 0")
    if not (0.0 <= config.min_weight <= config.max_weight <= 1.0):
        raise ValueError("weight bounds must satisfy 0 <= min_weight <= max_weight <= 1")

    matrix = [list(map(float, strategy_returns[name])) for name in names]
    n = len(names)
    means = [_mean(row) for row in matrix]
    cov = _covariance_matrix(matrix)

    weights = [1.0 / n] * n
    for _ in range(config.iterations):
        gradient = _objective_gradient(weights, means, cov, config.risk_aversion)
        candidate = [w + config.learning_rate * g for w, g in zip(weights, gradient)]
        weights = _project_weights(candidate, min_w=config.min_weight, max_w=config.max_weight)

    expected_return = _dot(weights, means)
    portfolio_var = _quadratic(weights, cov)
    expected_volatility = sqrt(max(portfolio_var, 0.0))
    sharpe_like = expected_return / expected_volatility if expected_volatility > 0 else 0.0

    strategy_stats = [
        StrategyStats(
            name=name,
            mean_return=means[idx],
            volatility=sqrt(max(cov[idx][idx], 0.0)),
        )
        for idx, name in enumerate(names)
    ]

    annual_scale = sqrt(config.annualization_factor)
    return OptimizationResult(
        weights={name: weights[idx] for idx, name in enumerate(names)},
        expected_return=expected_return * config.annualization_factor,
        expected_volatility=expected_volatility * annual_scale,
        sharpe_like=sharpe_like * annual_scale,
        strategy_stats=strategy_stats,
    )


def _mean(values: Sequence[float]) -> float:
    return fmean(values)


def _covariance_matrix(matrix: Sequence[Sequence[float]]) -> list[list[float]]:
    n = len(matrix)
    length = len(matrix[0])
    means = [_mean(row) for row in matrix]

    cov = [[0.0 for _ in range(n)] for _ in range(n)]
    denom = max(length - 1, 1)
    for i in range(n):
        for j in range(n):
            accum = 0.0
            for k in range(length):
                accum += (matrix[i][k] - means[i]) * (matrix[j][k] - means[j])
            cov[i][j] = accum / denom
    return cov


def _objective_gradient(weights: Sequence[float], means: Sequence[float], cov: Sequence[Sequence[float]], risk_aversion: float) -> list[float]:
    cov_w = [sum(cov_row[j] * weights[j] for j in range(len(weights))) for cov_row in cov]
    return [means[i] - 2.0 * risk_aversion * cov_w[i] for i in range(len(weights))]


def _project_weights(weights: Sequence[float], *, min_w: float, max_w: float) -> list[float]:
    clipped = [min(max(w, min_w), max_w) for w in weights]
    total = sum(clipped)
    if total <= 0:
        return [1.0 / len(clipped) for _ in clipped]
    normalized = [w / total for w in clipped]

    for _ in range(8):
        over = [idx for idx, w in enumerate(normalized) if w > max_w]
        under = [idx for idx, w in enumerate(normalized) if w < min_w]
        if not over and not under:
            break

        fixed = set(over + under)
        for idx in over:
            normalized[idx] = max_w
        for idx in under:
            normalized[idx] = min_w

        remainder = 1.0 - sum(normalized[idx] for idx in fixed)
        free = [idx for idx in range(len(normalized)) if idx not in fixed]
        if not free:
            break
        free_total = sum(normalized[idx] for idx in free)
        if free_total <= 0:
            even = remainder / len(free)
            for idx in free:
                normalized[idx] = even
        else:
            scale = remainder / free_total
            for idx in free:
                normalized[idx] *= scale

    total = sum(normalized)
    return [w / total for w in normalized]


def _dot(a: Sequence[float], b: Sequence[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def _quadratic(w: Sequence[float], cov: Sequence[Sequence[float]]) -> float:
    return sum(w[i] * sum(cov[i][j] * w[j] for j in range(len(w))) for i in range(len(w)))
