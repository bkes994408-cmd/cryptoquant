from __future__ import annotations

import pytest

from cryptoquant.strategy import AdaptationSignal, RegimeBanditParameterTuner, StrategyParameterSet


def test_bandit_prefers_higher_reward_in_same_regime() -> None:
    fast = StrategyParameterSet(fast_window=3, slow_window=9)
    slow = StrategyParameterSet(fast_window=8, slow_window=21)
    tuner = RegimeBanditParameterTuner([fast, slow], epsilon=0.0, seed=7)
    signal = AdaptationSignal(volatility=0.01, trend_strength=0.8)

    # Bootstrap both arms, then make `fast` clearly better.
    tuner.update(signal, fast, reward=0.2)
    tuner.update(signal, slow, reward=-0.1)
    tuner.update(signal, fast, reward=0.4)

    assert tuner.select(signal) == fast


def test_bandit_keeps_independent_tables_per_regime() -> None:
    trend = StrategyParameterSet(fast_window=2, slow_window=5)
    mean_revert = StrategyParameterSet(fast_window=6, slow_window=20)
    tuner = RegimeBanditParameterTuner([trend, mean_revert], epsilon=0.0, seed=3)

    low_vol_trend = AdaptationSignal(volatility=0.01, trend_strength=0.8)
    high_vol_range = AdaptationSignal(volatility=0.05, trend_strength=0.1)

    tuner.update(low_vol_trend, trend, reward=1.0)
    tuner.update(high_vol_range, mean_revert, reward=1.0)

    assert tuner.select(low_vol_trend) == trend
    assert tuner.select(high_vol_range) == mean_revert


def test_bandit_validates_inputs() -> None:
    p = StrategyParameterSet(fast_window=2, slow_window=4)

    with pytest.raises(ValueError, match="at least one candidate"):
        RegimeBanditParameterTuner([])

    with pytest.raises(ValueError, match="epsilon"):
        RegimeBanditParameterTuner([p], epsilon=1.5)

    with pytest.raises(ValueError, match="unique"):
        RegimeBanditParameterTuner([p, p])

    tuner = RegimeBanditParameterTuner([p])
    with pytest.raises(ValueError, match="volatility"):
        tuner.select(AdaptationSignal(volatility=-0.1, trend_strength=0.0))
