import pytest

from cryptoquant.risk import (
    CorrelationRiskConfig,
    StrategyPosition,
    calculate_net_exposure,
    evaluate_correlation_risk,
    historical_var_cvar,
)


def test_calculate_net_exposure_across_strategies() -> None:
    snapshot = calculate_net_exposure(
        [
            StrategyPosition(strategy="trend", symbol="BTCUSDT", qty=0.5, price=100_000),
            StrategyPosition(strategy="mr", symbol="BTCUSDT", qty=-0.2, price=100_000),
            StrategyPosition(strategy="carry", symbol="ETHUSDT", qty=3.0, price=2_000),
        ],
        equity=80_000,
    )

    assert snapshot.per_strategy_net_notional["trend"] == 50_000
    assert snapshot.per_strategy_net_notional["mr"] == -20_000
    assert snapshot.per_strategy_net_notional["carry"] == 6_000
    assert snapshot.portfolio_net_notional == 36_000
    assert snapshot.portfolio_gross_notional == 76_000
    assert snapshot.net_exposure_ratio == pytest.approx(0.45)
    assert snapshot.gross_exposure_ratio == pytest.approx(0.95)
    assert snapshot.long_exposure_ratio == pytest.approx(0.70)
    assert snapshot.short_exposure_ratio == pytest.approx(0.25)


def test_calculate_net_exposure_requires_positive_equity() -> None:
    with pytest.raises(ValueError, match="equity must be positive"):
        calculate_net_exposure([], equity=0)


def test_evaluate_correlation_risk_blocks_high_pair_correlation() -> None:
    strategy_returns = {
        "trend": [0.01, 0.015, 0.012, 0.017, 0.013],
        "momentum": [0.011, 0.016, 0.013, 0.018, 0.014],
        "carry": [0.003, -0.004, 0.002, -0.001, 0.001],
    }

    result = evaluate_correlation_risk(
        strategy_returns,
        config=CorrelationRiskConfig(max_abs_pair_corr=0.8, max_avg_abs_corr=0.95),
    )

    assert result.approved is False
    assert result.breached_pairs
    assert any("pair correlation breach" in reason for reason in result.reasons)


def test_evaluate_correlation_risk_blocks_high_average_correlation() -> None:
    strategy_returns = {
        "a": [0.01, 0.02, 0.03, 0.04, 0.05],
        "b": [0.011, 0.021, 0.031, 0.041, 0.051],
        "c": [0.009, 0.019, 0.029, 0.039, 0.049],
    }

    result = evaluate_correlation_risk(
        strategy_returns,
        config=CorrelationRiskConfig(max_abs_pair_corr=0.99999, max_avg_abs_corr=0.7),
    )

    assert result.approved is False
    assert result.avg_abs_correlation > 0.7
    assert any("average absolute correlation breach" in reason for reason in result.reasons)


def test_evaluate_correlation_risk_passes_diversified_returns() -> None:
    strategy_returns = {
        "trend": [0.010, -0.006, 0.011, -0.005, 0.009, -0.004],
        "carry": [0.002, 0.003, 0.001, 0.002, 0.001, 0.002],
        "mean_revert": [0.003, -0.001, -0.004, 0.002, -0.002, 0.001],
    }

    result = evaluate_correlation_risk(
        strategy_returns,
        config=CorrelationRiskConfig(max_abs_pair_corr=0.95, max_avg_abs_corr=0.85),
    )

    assert result.approved is True
    assert result.reasons == []
    assert result.matrix["trend"]["trend"] == 1.0


def test_historical_var_cvar_basics() -> None:
    returns = [0.02, -0.01, 0.005, -0.03, -0.015, 0.01, -0.005, 0.012, -0.02, 0.004]

    result = historical_var_cvar(returns, confidence=0.95, horizon_days=1, portfolio_value=1_000_000)

    assert result.tail_scenarios == 1
    assert result.var == pytest.approx(30_000)
    assert result.cvar == pytest.approx(30_000)


def test_historical_var_cvar_multi_day_scales_by_sqrt_time() -> None:
    returns = [0.01, -0.02, 0.005, -0.03, 0.002, -0.015, 0.012, -0.01]

    one_day = historical_var_cvar(returns, confidence=0.75, horizon_days=1, portfolio_value=500_000)
    four_day = historical_var_cvar(returns, confidence=0.75, horizon_days=4, portfolio_value=500_000)

    assert four_day.var == pytest.approx(one_day.var * 2.0)
    assert four_day.cvar == pytest.approx(one_day.cvar * 2.0)


def test_historical_var_cvar_validates_inputs() -> None:
    with pytest.raises(ValueError, match=r"confidence must be in \(0, 1\)"):
        historical_var_cvar([0.01, -0.01], confidence=1.0)

    with pytest.raises(ValueError, match="horizon_days must be positive"):
        historical_var_cvar([0.01, -0.01], horizon_days=0)

    with pytest.raises(ValueError, match="at least two return observations"):
        historical_var_cvar([0.01])
