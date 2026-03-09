from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence


@dataclass(frozen=True)
class RebalanceScheduleConfig:
    cadence_days: int = 7
    drift_threshold: float = 0.08
    min_trade_weight: float = 0.0


@dataclass(frozen=True)
class RebalanceEvent:
    day_index: int
    turnover: float
    max_drift: float
    estimated_cost_rate: float


@dataclass(frozen=True)
class CostSensitivityPoint:
    cost_rate: float
    total_turnover: float
    estimated_cost: float
    net_return: float


@dataclass(frozen=True)
class CostSensitivityResult:
    gross_return: float
    points: list[CostSensitivityPoint]


def build_rebalance_schedule(
    weight_history: Mapping[str, Sequence[float]],
    target_weights: Mapping[str, float],
    *,
    cost_rate: float,
    config: RebalanceScheduleConfig = RebalanceScheduleConfig(),
) -> list[RebalanceEvent]:
    names = sorted(target_weights.keys())
    if len(names) < 2:
        raise ValueError("at least two strategy targets are required")
    if set(weight_history.keys()) != set(names):
        raise ValueError("weight_history and target_weights must contain same strategy names")

    length_set = {len(weight_history[name]) for name in names}
    if len(length_set) != 1:
        raise ValueError("all strategy weight series must have the same length")
    length = next(iter(length_set))
    if length == 0:
        return []

    _validate_weight_vector([target_weights[name] for name in names], label="target_weights")

    if config.cadence_days <= 0:
        raise ValueError("cadence_days must be > 0")
    if config.drift_threshold < 0:
        raise ValueError("drift_threshold must be >= 0")
    if config.min_trade_weight < 0:
        raise ValueError("min_trade_weight must be >= 0")
    if cost_rate < 0:
        raise ValueError("cost_rate must be >= 0")

    target_vec = [float(target_weights[name]) for name in names]
    events: list[RebalanceEvent] = []

    for day_index in range(length):
        if day_index == 0 or day_index % config.cadence_days != 0:
            continue

        current = [float(weight_history[name][day_index]) for name in names]
        _validate_weight_vector(current, label=f"weight_history(day_index={day_index})")

        diffs = [target_vec[i] - current[i] for i in range(len(names))]
        max_drift = max(abs(diff) for diff in diffs)
        turnover = 0.5 * sum(abs(diff) for diff in diffs)

        if max_drift < config.drift_threshold:
            continue
        if turnover < config.min_trade_weight:
            continue

        events.append(
            RebalanceEvent(
                day_index=day_index,
                turnover=turnover,
                max_drift=max_drift,
                estimated_cost_rate=turnover * cost_rate,
            )
        )

    return events


def analyze_transaction_cost_sensitivity(
    *,
    gross_return: float,
    rebalances: Sequence[RebalanceEvent],
    cost_rates: Sequence[float],
) -> CostSensitivityResult:
    if any(rate < 0 for rate in cost_rates):
        raise ValueError("cost_rates must be >= 0")

    sorted_rates = sorted(float(rate) for rate in cost_rates)
    total_turnover = sum(event.turnover for event in rebalances)

    points = [
        CostSensitivityPoint(
            cost_rate=rate,
            total_turnover=total_turnover,
            estimated_cost=total_turnover * rate,
            net_return=gross_return - (total_turnover * rate),
        )
        for rate in sorted_rates
    ]

    return CostSensitivityResult(gross_return=gross_return, points=points)


def _validate_weight_vector(weights: Sequence[float], *, label: str) -> None:
    if not all(0.0 <= weight <= 1.0 for weight in weights):
        raise ValueError(f"{label} must be within [0, 1]")
    if abs(sum(weights) - 1.0) > 1e-6:
        raise ValueError(f"{label} must sum to 1")
