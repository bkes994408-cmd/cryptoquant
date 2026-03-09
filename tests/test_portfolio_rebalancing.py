from cryptoquant.portfolio import (
    RebalanceScheduleConfig,
    analyze_transaction_cost_sensitivity,
    build_rebalance_schedule,
)


def test_build_rebalance_schedule_respects_cadence_and_drift_threshold() -> None:
    target_weights = {"trend": 0.5, "carry": 0.3, "mean_revert": 0.2}
    weight_history = {
        "trend": [0.5, 0.52, 0.62, 0.54, 0.66, 0.50, 0.60],
        "carry": [0.3, 0.29, 0.23, 0.28, 0.18, 0.30, 0.24],
        "mean_revert": [0.2, 0.19, 0.15, 0.18, 0.16, 0.20, 0.16],
    }

    events = build_rebalance_schedule(
        weight_history,
        target_weights,
        cost_rate=0.001,
        config=RebalanceScheduleConfig(cadence_days=2, drift_threshold=0.1),
    )

    assert [event.day_index for event in events] == [2, 4]
    assert all(event.max_drift >= 0.1 for event in events)
    assert all(event.turnover > 0 for event in events)


def test_build_rebalance_schedule_rejects_invalid_weights() -> None:
    target_weights = {"a": 0.7, "b": 0.4}
    weight_history = {"a": [0.6, 0.6], "b": [0.4, 0.4]}

    try:
        build_rebalance_schedule(weight_history, target_weights, cost_rate=0.001)
    except ValueError as exc:
        assert "sum to 1" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_analyze_transaction_cost_sensitivity_monotonic_net_return() -> None:
    target_weights = {"trend": 0.5, "carry": 0.3, "mean_revert": 0.2}
    weight_history = {
        "trend": [0.5, 0.55, 0.65],
        "carry": [0.3, 0.27, 0.20],
        "mean_revert": [0.2, 0.18, 0.15],
    }

    events = build_rebalance_schedule(
        weight_history,
        target_weights,
        cost_rate=0.0,
        config=RebalanceScheduleConfig(cadence_days=1, drift_threshold=0.05),
    )

    result = analyze_transaction_cost_sensitivity(
        gross_return=0.18,
        rebalances=events,
        cost_rates=[0.002, 0.0, 0.001],
    )

    net_returns = [point.net_return for point in result.points]
    assert net_returns[0] >= net_returns[1] >= net_returns[2]
    assert result.points[0].cost_rate == 0.0
    assert result.points[-1].cost_rate == 0.002
