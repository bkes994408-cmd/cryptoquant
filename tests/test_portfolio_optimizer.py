from cryptoquant.portfolio import OptimizationConfig, optimize_strategy_weights


def test_optimize_strategy_weights_prefers_better_risk_adjusted_strategy() -> None:
    returns = {
        "trend": [0.015, 0.012, 0.013, 0.011, 0.014, 0.012],
        "carry": [0.009, 0.007, 0.011, 0.005, 0.01, 0.006],
        "mean_revert": [0.02, -0.015, 0.018, -0.012, 0.022, -0.01],
    }

    result = optimize_strategy_weights(
        returns,
        config=OptimizationConfig(risk_aversion=3.0, max_weight=0.8, iterations=700),
    )

    assert abs(sum(result.weights.values()) - 1.0) < 1e-9
    assert all(0.0 <= w <= 0.8 for w in result.weights.values())
    assert result.weights["trend"] > result.weights["mean_revert"]
    assert result.sharpe_like > 0


def test_optimize_strategy_weights_validates_input_shape() -> None:
    returns = {
        "a": [0.01, 0.02, 0.01],
        "b": [0.01],
    }

    try:
        optimize_strategy_weights(returns)
    except ValueError as exc:
        assert "same length" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_optimize_strategy_weights_respects_min_weight_constraint() -> None:
    returns = {
        "a": [0.01, 0.011, 0.012, 0.01, 0.013],
        "b": [0.005, 0.004, 0.006, 0.004, 0.005],
        "c": [0.0, -0.001, 0.001, 0.0, 0.0],
    }

    result = optimize_strategy_weights(
        returns,
        config=OptimizationConfig(min_weight=0.1, max_weight=0.75, iterations=600),
    )

    assert all(weight >= 0.1 - 1e-9 for weight in result.weights.values())
    assert all(weight <= 0.75 + 1e-9 for weight in result.weights.values())
