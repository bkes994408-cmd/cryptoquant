from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from cryptoquant.events.market import MarketEvent
from cryptoquant.strategy import (
    AdaptiveParameterController,
    AdaptiveStrategyConfig,
    EpsilonGreedyParameterBandit,
    StrategyParameterSet,
)


def _events(closes: list[float]) -> list[MarketEvent]:
    base = datetime(2026, 3, 1, 0, 0, tzinfo=timezone.utc)
    return [
        MarketEvent(
            symbol="BTCUSDT",
            timeframe="1m",
            close=close,
            ts=base + timedelta(minutes=i),
            source="test",
        )
        for i, close in enumerate(closes)
    ]


def test_bandit_prefers_higher_mean_reward_when_epsilon_zero() -> None:
    p1 = StrategyParameterSet(fast_window=2, slow_window=4)
    p2 = StrategyParameterSet(fast_window=3, slow_window=8)
    bandit = EpsilonGreedyParameterBandit([p1, p2], epsilon=0.0)

    bandit.update(p1, 1.0)
    bandit.update(p2, 2.0)

    assert bandit.select() == p2


def test_adaptive_controller_retune_then_hold() -> None:
    params = [
        StrategyParameterSet(fast_window=2, slow_window=3),
        StrategyParameterSet(fast_window=4, slow_window=8),
    ]
    cfg = AdaptiveStrategyConfig(lookback_events=30, retune_interval_events=3, epsilon=0.0)
    controller = AdaptiveParameterController(symbol="BTCUSDT", candidates=params, config=cfg)

    history = _events([float(v) for v in range(100, 170)])

    decision1 = controller.step(history)
    assert decision1.mode == "retune"

    decision2 = controller.step(history)
    assert decision2.mode == "hold"
    assert decision2.selected_params == decision1.selected_params

    decision3 = controller.step(history)
    assert decision3.mode == "retune"


def test_adaptive_controller_requires_sufficient_history() -> None:
    controller = AdaptiveParameterController(
        symbol="BTCUSDT",
        candidates=[StrategyParameterSet(fast_window=2, slow_window=3)],
        config=AdaptiveStrategyConfig(lookback_events=25, retune_interval_events=5),
    )

    with pytest.raises(ValueError, match="insufficient history"):
        controller.step(_events([100.0] * 24))
