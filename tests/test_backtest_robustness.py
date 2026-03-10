from __future__ import annotations

from datetime import datetime, timedelta, timezone

from cryptoquant.backtest import (
    RegimeSplitConfig,
    WalkForwardConfig,
    evaluate_strategy_metrics,
    run_regime_split_validation,
    run_walk_forward_validation,
)
from cryptoquant.events.market import MarketEvent


def _make_events(closes: list[float]) -> list[MarketEvent]:
    start = datetime(2026, 3, 1, 0, 0, tzinfo=timezone.utc)
    return [
        MarketEvent("BTCUSDT", "1m", close, start + timedelta(minutes=idx), "test")
        for idx, close in enumerate(closes)
    ]


def _trend_follow_target(event: MarketEvent) -> float:
    return 1.0 if event.close >= 100.0 else -1.0


def test_evaluate_strategy_metrics_returns_basic_fields() -> None:
    events = _make_events([99.0, 100.5, 101.0, 98.0, 102.0])

    result = evaluate_strategy_metrics(
        events,
        symbol="BTCUSDT",
        target_qty_fn=_trend_follow_target,
        fee_bps=0.0,
        slippage_bps=0.0,
    )

    assert result.trades > 0
    assert result.turnover > 0
    assert isinstance(result.pnl, float)
    assert -100.0 <= result.return_pct <= 100.0
    assert 0.0 <= result.win_rate <= 1.0


def test_walk_forward_validation_generates_expected_slices() -> None:
    events = _make_events([95.0, 96.0, 97.0, 98.0, 99.0, 100.0, 101.0, 102.0, 103.0, 104.0])

    report = run_walk_forward_validation(
        events,
        symbol="BTCUSDT",
        target_qty_fn=_trend_follow_target,
        config=WalkForwardConfig(train_size=4, test_size=2, step_size=2, fee_bps=0.0, slippage_bps=0.0),
    )

    assert len(report.slices) == 3
    assert report.slices[0].train_start < report.slices[0].train_end
    assert report.slices[0].test_start < report.slices[0].test_end
    assert isinstance(report.avg_test_return_pct, float)
    assert 0.0 <= report.positive_test_ratio <= 1.0


def test_regime_split_validation_returns_regime_reports() -> None:
    events = _make_events([100.0, 101.0, 100.9, 99.0, 99.2, 101.5, 101.6, 98.8])

    report = run_regime_split_validation(
        events,
        symbol="BTCUSDT",
        target_qty_fn=_trend_follow_target,
        config=RegimeSplitConfig(return_threshold=0.005, fee_bps=0.0, slippage_bps=0.0),
    )

    assert report.bull is not None
    assert report.sideways is not None
    assert report.bear is not None
    assert report.bull.trades >= 0
    assert report.sideways.trades >= 0
    assert report.bear.trades >= 0
