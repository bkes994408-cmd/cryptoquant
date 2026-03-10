from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from cryptoquant.events.market import MarketEvent
from cryptoquant.strategy import AutomatedStrategyOptimizer, StrategyParameterSet


def _events(closes: list[float]) -> list[MarketEvent]:
    base = datetime(2026, 3, 1, 0, 0, tzinfo=timezone.utc)
    out: list[MarketEvent] = []
    for i, close in enumerate(closes):
        out.append(
            MarketEvent(
                symbol="BTCUSDT",
                timeframe="1m",
                close=close,
                ts=base + timedelta(minutes=i),
                source="test",
            )
        )
    return out


def test_automated_optimizer_picks_best_params_for_trend_dataset() -> None:
    events = _events([float(v) for v in range(100, 121)])
    optimizer = AutomatedStrategyOptimizer(symbol="BTCUSDT", base_qty=1.0, objective="net_pnl")

    result = optimizer.optimize(
        events,
        param_grid=[
            StrategyParameterSet(fast_window=2, slow_window=3),
            StrategyParameterSet(fast_window=4, slow_window=8),
        ],
    )

    # Faster MA should enter long earlier in persistent up-trend.
    assert result.best.params == StrategyParameterSet(fast_window=2, slow_window=3)
    assert result.best.metrics.net_pnl > 0
    assert result.leaderboard[0].score >= result.leaderboard[1].score


def test_automated_optimizer_ignores_invalid_pairs_and_errors_when_none_left() -> None:
    events = _events([100, 101, 102, 103, 104])
    optimizer = AutomatedStrategyOptimizer(symbol="BTCUSDT")

    with pytest.raises(ValueError, match="no valid parameter set"):
        optimizer.optimize(
            events,
            param_grid=[
                StrategyParameterSet(fast_window=5, slow_window=3),
                StrategyParameterSet(fast_window=2, slow_window=2),
            ],
        )


def test_automated_optimizer_supports_win_rate_objective() -> None:
    events = _events([100, 101, 99, 102, 98, 103, 97, 104, 96, 105])
    optimizer = AutomatedStrategyOptimizer(symbol="BTCUSDT", objective="win_rate")

    result = optimizer.optimize(
        events,
        param_grid=[
            StrategyParameterSet(fast_window=2, slow_window=3),
            StrategyParameterSet(fast_window=3, slow_window=5),
        ],
    )

    assert len(result.leaderboard) == 2
    assert result.best.score == result.best.metrics.win_rate
