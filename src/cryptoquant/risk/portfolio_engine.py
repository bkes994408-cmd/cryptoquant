from __future__ import annotations

from dataclasses import dataclass
from math import ceil, isfinite, sqrt
from typing import Mapping, Sequence


@dataclass(frozen=True)
class StrategyPosition:
    strategy: str
    symbol: str
    qty: float
    price: float


@dataclass(frozen=True)
class ExposureSnapshot:
    per_strategy_net_notional: dict[str, float]
    portfolio_net_notional: float
    portfolio_gross_notional: float
    net_exposure_ratio: float
    gross_exposure_ratio: float
    long_exposure_ratio: float
    short_exposure_ratio: float


@dataclass(frozen=True)
class CorrelationRiskConfig:
    max_abs_pair_corr: float = 0.85
    max_avg_abs_corr: float = 0.65

    def __post_init__(self) -> None:
        if not (0 < self.max_abs_pair_corr <= 1):
            raise ValueError("max_abs_pair_corr must be in (0, 1]")
        if not (0 < self.max_avg_abs_corr <= 1):
            raise ValueError("max_avg_abs_corr must be in (0, 1]")


@dataclass(frozen=True)
class CorrelationRiskResult:
    approved: bool
    matrix: dict[str, dict[str, float]]
    avg_abs_correlation: float
    breached_pairs: list[tuple[str, str, float]]
    reasons: list[str]


@dataclass(frozen=True)
class VarCvarResult:
    confidence: float
    horizon_days: int
    portfolio_value: float
    var: float
    cvar: float
    tail_scenarios: int


def calculate_net_exposure(positions: Sequence[StrategyPosition], *, equity: float) -> ExposureSnapshot:
    if equity <= 0:
        raise ValueError("equity must be positive")

    per_strategy_net: dict[str, float] = {}
    total_signed = 0.0
    total_abs = 0.0
    total_long = 0.0
    total_short = 0.0

    for p in positions:
        if p.price <= 0:
            raise ValueError(f"price must be positive: {p.symbol}")
        signed_notional = p.qty * p.price
        if not isfinite(signed_notional):
            raise ValueError(f"non-finite notional: {p.strategy}/{p.symbol}")

        per_strategy_net[p.strategy] = per_strategy_net.get(p.strategy, 0.0) + signed_notional
        total_signed += signed_notional

        abs_notional = abs(signed_notional)
        total_abs += abs_notional
        if signed_notional >= 0:
            total_long += signed_notional
        else:
            total_short += abs(signed_notional)

    return ExposureSnapshot(
        per_strategy_net_notional=per_strategy_net,
        portfolio_net_notional=total_signed,
        portfolio_gross_notional=total_abs,
        net_exposure_ratio=total_signed / equity,
        gross_exposure_ratio=total_abs / equity,
        long_exposure_ratio=total_long / equity,
        short_exposure_ratio=total_short / equity,
    )


def evaluate_correlation_risk(
    strategy_returns: Mapping[str, Sequence[float]],
    *,
    config: CorrelationRiskConfig = CorrelationRiskConfig(),
) -> CorrelationRiskResult:
    names = sorted(strategy_returns.keys())
    if len(names) < 2:
        raise ValueError("at least two strategies are required")

    lengths = {len(strategy_returns[name]) for name in names}
    if len(lengths) != 1:
        raise ValueError("all strategy return series must have same length")

    sample_size = next(iter(lengths))
    if sample_size < 2:
        raise ValueError("at least two observations are required")

    means = {name: _mean(strategy_returns[name]) for name in names}
    matrix: dict[str, dict[str, float]] = {name: {} for name in names}

    abs_corr_values: list[float] = []
    breached_pairs: list[tuple[str, str, float]] = []

    for i, left in enumerate(names):
        for j, right in enumerate(names):
            if i == j:
                matrix[left][right] = 1.0
                continue

            corr = _pearson(strategy_returns[left], strategy_returns[right], means[left], means[right])
            matrix[left][right] = corr

            if i < j:
                abs_corr = abs(corr)
                abs_corr_values.append(abs_corr)
                if abs_corr > config.max_abs_pair_corr:
                    breached_pairs.append((left, right, corr))

    avg_abs = _mean(abs_corr_values)
    reasons: list[str] = []

    if breached_pairs:
        pair_summary = ", ".join(
            f"{left}/{right}={corr:.3f}" for left, right, corr in breached_pairs
        )
        reasons.append(
            f"pair correlation breach (limit={config.max_abs_pair_corr:.2f}): {pair_summary}"
        )

    if avg_abs > config.max_avg_abs_corr:
        reasons.append(
            f"average absolute correlation breach: {avg_abs:.3f} > {config.max_avg_abs_corr:.3f}"
        )

    return CorrelationRiskResult(
        approved=len(reasons) == 0,
        matrix=matrix,
        avg_abs_correlation=avg_abs,
        breached_pairs=breached_pairs,
        reasons=reasons,
    )


def historical_var_cvar(
    returns: Sequence[float],
    *,
    confidence: float = 0.95,
    horizon_days: int = 1,
    portfolio_value: float = 1.0,
) -> VarCvarResult:
    if not (0 < confidence < 1):
        raise ValueError("confidence must be in (0, 1)")
    if horizon_days <= 0:
        raise ValueError("horizon_days must be positive")
    if portfolio_value <= 0:
        raise ValueError("portfolio_value must be positive")
    if len(returns) < 2:
        raise ValueError("at least two return observations are required")

    horizon_scale = sqrt(horizon_days)
    losses: list[float] = []
    for r in returns:
        value = float(r)
        if not isfinite(value):
            raise ValueError("returns must be finite numbers")
        losses.append(-value * horizon_scale * portfolio_value)

    losses.sort(reverse=True)
    alpha = 1.0 - confidence
    tail_count = max(1, ceil(alpha * len(losses)))

    var = losses[tail_count - 1]
    cvar = _mean(losses[:tail_count])

    return VarCvarResult(
        confidence=confidence,
        horizon_days=horizon_days,
        portfolio_value=portfolio_value,
        var=var,
        cvar=cvar,
        tail_scenarios=tail_count,
    )


def _mean(values: Sequence[float]) -> float:
    if not values:
        raise ValueError("cannot compute mean of empty values")
    return sum(values) / len(values)


def _pearson(x: Sequence[float], y: Sequence[float], x_mean: float, y_mean: float) -> float:
    num = 0.0
    den_x = 0.0
    den_y = 0.0

    for xi, yi in zip(x, y):
        dx = xi - x_mean
        dy = yi - y_mean
        num += dx * dy
        den_x += dx * dx
        den_y += dy * dy

    denom = (den_x * den_y) ** 0.5
    if denom == 0:
        return 0.0
    return num / denom
