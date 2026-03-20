from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from cryptoquant.monitoring import OperationalDashboard, PerformanceSnapshot


def _sample(ts: datetime, *, net: float, realized: float = 0.0, unrealized: float = 0.0) -> PerformanceSnapshot:
    return PerformanceSnapshot(
        ts=ts,
        realized_pnl=realized,
        unrealized_pnl=unrealized,
        fee_total=0.0,
        slippage_total=0.0,
        net_pnl=net,
        max_drawdown=12.0,
        close_trades=2,
        win_rate=0.5,
        sharpe_like=1.1,
        by_symbol={},
    )


def test_live_view_contains_realtime_pnl_risk_and_health() -> None:
    now = datetime.now(timezone.utc)
    dash = OperationalDashboard()
    dash.record_performance(_sample(now, net=120.0, realized=100.0, unrealized=20.0))

    dash.record_risk_event(level="warn", code="risk.latency", message="latency high", ts=now)
    dash.record_risk_event(level="critical", code="risk.reject", message="reject spike", ts=now)

    dash.record_strategy_health(
        strategy_id="mean-revert",
        healthy=True,
        latency_ms=35.0,
        error_rate=0.01,
        ts=now,
    )

    view = dash.live_view()
    assert view.pnl.net_pnl == 120.0
    assert view.pnl.realized_pnl == 100.0
    assert view.risk_event_total == 2
    assert view.risk_event_by_level["WARN"] == 1
    assert view.risk_event_by_level["CRITICAL"] == 1
    assert view.strategy_health["mean-revert"].latest_healthy is True


def test_daily_summary_aggregates_windowed_performance() -> None:
    now = datetime(2026, 3, 20, 3, 0, tzinfo=timezone.utc)
    dash = OperationalDashboard()

    dash.record_performance(_sample(now - timedelta(hours=20), net=10.0))
    dash.record_performance(_sample(now - timedelta(hours=4), net=30.0))
    dash.record_performance(_sample(now - timedelta(hours=1), net=25.0))

    dash.record_risk_event(level="warn", code="risk.latency", message="latency", ts=now - timedelta(hours=2))
    dash.record_strategy_health(
        strategy_id="trend",
        healthy=True,
        latency_ms=20.0,
        error_rate=0.0,
        ts=now - timedelta(hours=3),
    )
    dash.record_strategy_health(
        strategy_id="trend",
        healthy=False,
        latency_ms=60.0,
        error_rate=0.2,
        ts=now - timedelta(hours=1),
    )

    summary = dash.summarize(period="daily", as_of=now)
    assert summary.samples == 3
    assert summary.net_pnl_open == 10.0
    assert summary.net_pnl_close == 25.0
    assert summary.net_pnl_change == 15.0
    assert summary.net_pnl_max == 30.0
    assert summary.risk_event_count == 1
    assert summary.strategy_health["trend"].uptime_ratio == 0.5


def test_weekly_summary_excludes_older_samples() -> None:
    now = datetime(2026, 3, 20, 3, 0, tzinfo=timezone.utc)
    dash = OperationalDashboard()

    dash.record_performance(_sample(now - timedelta(days=9), net=5.0))
    dash.record_performance(_sample(now - timedelta(days=6), net=12.0))
    dash.record_performance(_sample(now - timedelta(days=1), net=18.0))

    summary = dash.summarize(period="weekly", as_of=now)
    assert summary.samples == 2
    assert summary.net_pnl_open == 12.0
    assert summary.net_pnl_close == 18.0


def test_dashboard_validation() -> None:
    dash = OperationalDashboard()
    with pytest.raises(ValueError, match="no performance"):
        dash.live_view()

    with pytest.raises(ValueError, match="period"):
        dash.summarize(period="monthly")

    with pytest.raises(ValueError, match="non-negative"):
        dash.record_strategy_health(strategy_id="s1", healthy=True, latency_ms=-1, error_rate=0.1)

    with pytest.raises(ValueError, match=r"\[0, 1\]"):
        dash.record_strategy_health(strategy_id="s1", healthy=True, latency_ms=1, error_rate=1.1)
