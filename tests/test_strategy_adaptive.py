from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from cryptoquant.aggregation import Bar
from cryptoquant.events.market import MarketEvent
from cryptoquant.sentiment import InMemorySentimentAdapter, SentimentItem, SentimentPipeline
from cryptoquant.strategy import (
    AdaptiveParameterController,
    AdaptiveStrategyConfig,
    EpsilonGreedyParameterBandit,
    MovingAverageCrossoverStrategy,
    StrategyEngine,
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


def _bars(events: list[MarketEvent]) -> list[Bar]:
    return [
        Bar(
            symbol=e.symbol,
            timeframe=e.timeframe,
            ts=e.ts,
            open=e.close,
            high=e.close,
            low=e.close,
            close=e.close,
            volume=0.0,
        )
        for e in events
    ]


def test_bandit_prefers_higher_mean_reward_when_epsilon_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    p1 = StrategyParameterSet(fast_window=2, slow_window=4)
    p2 = StrategyParameterSet(fast_window=3, slow_window=8)
    bandit = EpsilonGreedyParameterBandit([p1, p2], epsilon=0.0)

    bandit.update(p1, 1.0)
    bandit.update(p2, 2.0)

    # Force deterministic tie/exploit selection path for test stability.
    monkeypatch.setattr(bandit._rng, "choice", lambda seq: seq[-1])
    assert bandit.select() == p2


def test_bandit_validates_epsilon_bounds() -> None:
    p = StrategyParameterSet(fast_window=2, slow_window=4)
    with pytest.raises(ValueError, match="epsilon"):
        EpsilonGreedyParameterBandit([p], epsilon=-0.01)
    with pytest.raises(ValueError, match="epsilon"):
        EpsilonGreedyParameterBandit([p], epsilon=1.01)


def test_bandit_accepts_non_typical_epsilon_value() -> None:
    p = StrategyParameterSet(fast_window=2, slow_window=4)
    bandit = EpsilonGreedyParameterBandit([p], epsilon=0.37)
    assert bandit.select() == p


def test_bandit_epsilon_one_always_explores(monkeypatch: pytest.MonkeyPatch) -> None:
    p1 = StrategyParameterSet(fast_window=2, slow_window=4)
    p2 = StrategyParameterSet(fast_window=3, slow_window=8)
    bandit = EpsilonGreedyParameterBandit([p1, p2], epsilon=1.0)

    monkeypatch.setattr(bandit._rng, "random", lambda: 0.999)
    monkeypatch.setattr(bandit._rng, "choice", lambda seq: seq[1])

    assert bandit.select() == p2


def test_bandit_exploit_tie_break_is_not_stuck_on_first_candidate(monkeypatch: pytest.MonkeyPatch) -> None:
    p1 = StrategyParameterSet(fast_window=2, slow_window=4)
    p2 = StrategyParameterSet(fast_window=3, slow_window=8)
    bandit = EpsilonGreedyParameterBandit([p1, p2], epsilon=0.0)

    # Equal means -> tie in exploit path.
    bandit.update(p1, 1.0)
    bandit.update(p2, 1.0)

    monkeypatch.setattr(bandit._rng, "choice", lambda seq: seq[-1])
    assert bandit.select() == p2


def test_bandit_update_rejects_non_finite_reward() -> None:
    p = StrategyParameterSet(fast_window=2, slow_window=4)
    bandit = EpsilonGreedyParameterBandit([p], epsilon=0.1)

    with pytest.raises(ValueError, match="finite"):
        bandit.update(p, float("nan"))
    with pytest.raises(ValueError, match="finite"):
        bandit.update(p, float("inf"))


def test_adaptive_controller_retune_then_hold_without_reoptimizing_each_hold(monkeypatch: pytest.MonkeyPatch) -> None:
    params = [
        StrategyParameterSet(fast_window=2, slow_window=3),
        StrategyParameterSet(fast_window=4, slow_window=8),
    ]
    cfg = AdaptiveStrategyConfig(lookback_events=30, retune_interval_events=3, epsilon=0.0)
    controller = AdaptiveParameterController(symbol="BTCUSDT", candidates=params, config=cfg)

    history = _events([float(v) for v in range(100, 170)])

    optimize_calls = 0
    original_optimize = controller._optimizer.optimize

    def wrapped_optimize(*args, **kwargs):
        nonlocal optimize_calls
        optimize_calls += 1
        return original_optimize(*args, **kwargs)

    monkeypatch.setattr(controller._optimizer, "optimize", wrapped_optimize)

    decision1 = controller.step(history)
    assert decision1.mode == "retune"

    decision2 = controller.step(history)
    assert decision2.mode == "hold"
    assert decision2.selected_params == decision1.selected_params

    decision3 = controller.step(history)
    assert decision3.mode == "retune"

    # Retune on step 1 and 3 only; hold step reuses cached optimization.
    assert optimize_calls == 2


def test_adaptive_controller_strategy_engine_integration() -> None:
    params = [
        StrategyParameterSet(fast_window=2, slow_window=4),
        StrategyParameterSet(fast_window=3, slow_window=6),
    ]
    controller = AdaptiveParameterController(
        symbol="BTCUSDT",
        candidates=params,
        config=AdaptiveStrategyConfig(lookback_events=30, retune_interval_events=5, epsilon=0.0),
    )

    history = _events([float(v) for v in range(100, 150)])
    decision = controller.step(history)

    strategy = MovingAverageCrossoverStrategy(
        fast_window=decision.selected_params.fast_window,
        slow_window=decision.selected_params.slow_window,
        base_qty=1.0,
    )
    engine = StrategyEngine(strategy)
    engine_decision = engine.on_bars(_bars(history[-30:]))

    assert decision.mode == "retune"
    assert engine_decision.signal == strategy.name
    assert engine_decision.target_qty in {-1.0, 0.0, 1.0}


def test_adaptive_controller_requires_sufficient_history() -> None:
    controller = AdaptiveParameterController(
        symbol="BTCUSDT",
        candidates=[StrategyParameterSet(fast_window=2, slow_window=3)],
        config=AdaptiveStrategyConfig(lookback_events=25, retune_interval_events=5),
    )

    with pytest.raises(ValueError, match="insufficient history"):
        controller.step(_events([100.0] * 24))


def test_adaptive_controller_ml_mode_outputs_prediction_and_dynamic_epsilon() -> None:
    controller = AdaptiveParameterController(
        symbol="BTCUSDT",
        candidates=[
            StrategyParameterSet(fast_window=2, slow_window=4),
            StrategyParameterSet(fast_window=5, slow_window=10),
        ],
        config=AdaptiveStrategyConfig(
            lookback_events=40,
            retune_interval_events=2,
            epsilon=0.1,
            enable_ml_adaptation=True,
            ml_feature_window=8,
            epsilon_min=0.05,
            epsilon_max=0.25,
        ),
    )

    history = _events([100 + (i * 0.3) + ((-1) ** i) * 0.2 for i in range(80)])
    decision = controller.step(history)

    assert decision.predicted_return is not None
    assert decision.dynamic_epsilon is not None
    assert 0.05 <= decision.dynamic_epsilon <= 0.25


def test_adaptive_controller_without_ml_keeps_ml_fields_empty() -> None:
    controller = AdaptiveParameterController(
        symbol="BTCUSDT",
        candidates=[StrategyParameterSet(fast_window=2, slow_window=4)],
        config=AdaptiveStrategyConfig(
            lookback_events=30,
            retune_interval_events=3,
            enable_ml_adaptation=False,
        ),
    )

    history = _events([100.0 + i for i in range(40)])
    decision = controller.step(history)

    assert decision.predicted_return is None
    assert decision.dynamic_epsilon is None
    assert decision.sentiment_score is None
    assert decision.sentiment_confidence is None


def test_adaptive_controller_sentiment_overlay_outputs_snapshot() -> None:
    now = datetime.now(timezone.utc)
    pipeline = SentimentPipeline(
        InMemorySentimentAdapter(
            [
                SentimentItem(
                    source="news",
                    text="bullish breakout and strong adoption",
                    ts=now - timedelta(hours=1),
                ),
                SentimentItem(
                    source="social",
                    text="bearish liquidation risk",
                    ts=now - timedelta(hours=2),
                ),
            ]
        )
    )

    controller = AdaptiveParameterController(
        symbol="BTCUSDT",
        candidates=[
            StrategyParameterSet(fast_window=2, slow_window=4),
            StrategyParameterSet(fast_window=6, slow_window=12),
        ],
        config=AdaptiveStrategyConfig(
            lookback_events=30,
            retune_interval_events=2,
            enable_sentiment_overlay=True,
            sentiment_weight=0.2,
            sentiment_lookback_hours=24,
        ),
        sentiment_pipeline=pipeline,
    )

    history = _events([100.0 + i for i in range(45)])
    decision = controller.step(history)

    assert decision.sentiment_score is not None
    assert decision.sentiment_confidence is not None
    assert -1.0 <= decision.sentiment_score <= 1.0
    assert 0.0 <= decision.sentiment_confidence <= 1.0
