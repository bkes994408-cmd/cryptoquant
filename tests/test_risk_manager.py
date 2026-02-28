from __future__ import annotations

from datetime import datetime, timezone

from cryptoquant.risk import RiskInput, RiskLimits, RiskManager


def test_risk_manager_allows_within_caps() -> None:
    mgr = RiskManager(RiskLimits(notional_cap=5000, leverage_cap=2))
    result = mgr.apply(RiskInput(price=100, equity=2000, current_qty=0, target_qty=20))

    assert result.approved_qty == 20
    assert result.estimated_notional == 2000
    assert result.estimated_leverage == 1
    assert result.reason == "approved"


def test_risk_manager_clamps_by_notional_cap() -> None:
    mgr = RiskManager(RiskLimits(notional_cap=1000, leverage_cap=10))
    result = mgr.apply(RiskInput(price=100, equity=1000, current_qty=0, target_qty=20))

    assert result.approved_qty == 10
    assert result.estimated_notional == 1000
    assert result.reason == "clamped: notional cap"


def test_risk_manager_clamps_by_leverage_cap() -> None:
    mgr = RiskManager(RiskLimits(notional_cap=99999, leverage_cap=1.5))
    result = mgr.apply(RiskInput(price=100, equity=1000, current_qty=0, target_qty=20))

    assert result.approved_qty == 15
    assert result.estimated_notional == 1500
    assert result.estimated_leverage == 1.5
    assert result.reason == "clamped: leverage cap"


def test_daily_stop_blocks_opening_new_position_after_drawdown_limit() -> None:
    mgr = RiskManager(RiskLimits(notional_cap=99999, leverage_cap=10, daily_stop_drawdown_pct=0.05))

    # start-of-day anchor
    mgr.apply(
        RiskInput(
            price=100,
            equity=1000,
            current_qty=0,
            target_qty=0,
            as_of=datetime(2026, 2, 28, 0, 0, tzinfo=timezone.utc),
        )
    )

    # 6% drawdown => trigger daily stop
    result = mgr.apply(
        RiskInput(
            price=100,
            equity=940,
            current_qty=0,
            target_qty=1,
            as_of=datetime(2026, 2, 28, 1, 0, tzinfo=timezone.utc),
        )
    )

    assert result.approved_qty == 0.0
    assert result.reason == "rejected: daily stop"


def test_daily_stop_still_allows_reducing_position_and_flatten_only() -> None:
    mgr = RiskManager(RiskLimits(notional_cap=99999, leverage_cap=10, daily_stop_drawdown_pct=0.05))
    mgr.apply(
        RiskInput(
            price=100,
            equity=1000,
            current_qty=0,
            target_qty=0,
            as_of=datetime(2026, 2, 28, 0, 0, tzinfo=timezone.utc),
        )
    )

    # Trigger daily stop first (same day)
    mgr.apply(
        RiskInput(
            price=100,
            equity=940,
            current_qty=2,
            target_qty=2,
            as_of=datetime(2026, 2, 28, 1, 0, tzinfo=timezone.utc),
        )
    )

    # reducing exposure is still allowed
    reduce_result = mgr.apply(
        RiskInput(
            price=100,
            equity=930,
            current_qty=2,
            target_qty=1,
            as_of=datetime(2026, 2, 28, 1, 5, tzinfo=timezone.utc),
        )
    )
    assert reduce_result.approved_qty == 1
    assert reduce_result.reason == "approved"

    # flatten is also allowed
    flatten_result = mgr.apply(
        RiskInput(
            price=100,
            equity=925,
            current_qty=1,
            target_qty=0,
            as_of=datetime(2026, 2, 28, 1, 10, tzinfo=timezone.utc),
        )
    )
    assert flatten_result.approved_qty == 0
    assert flatten_result.reason == "approved"

    # after flatten, opening a new position is still blocked on same day
    reopen_blocked = mgr.apply(
        RiskInput(
            price=100,
            equity=920,
            current_qty=0,
            target_qty=-1,
            as_of=datetime(2026, 2, 28, 1, 15, tzinfo=timezone.utc),
        )
    )
    assert reopen_blocked.approved_qty == 0.0
    assert reopen_blocked.reason == "rejected: daily stop"
