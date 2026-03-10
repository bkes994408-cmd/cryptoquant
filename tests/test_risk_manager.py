from __future__ import annotations

from datetime import datetime, timezone

import pytest

from cryptoquant.risk import (
    DynamicStopConfig,
    RiskAlert,
    RiskInput,
    RiskLimits,
    RiskManager,
)


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


def test_risk_manager_emits_realtime_near_cap_alerts() -> None:
    alerts: list[RiskAlert] = []
    mgr = RiskManager(
        RiskLimits(notional_cap=1_000, leverage_cap=2, warn_utilization_pct=0.8),
        alert_sink=alerts.append,
    )

    mgr.apply(RiskInput(price=100, equity=500, current_qty=0, target_qty=8.5))

    alert_codes = {a.code for a in alerts}
    assert "risk.notional.near_cap" in alert_codes
    assert "risk.leverage.near_cap" in alert_codes


def test_dynamic_stop_loss_forces_flatten_after_reversal_long() -> None:
    alerts: list[RiskAlert] = []
    mgr = RiskManager(
        RiskLimits(
            notional_cap=100_000,
            leverage_cap=10,
            dynamic_stop=DynamicStopConfig(trailing_pct=0.05),
        ),
        alert_sink=alerts.append,
    )

    # Open long and let favorable move update trailing anchor.
    mgr.apply(RiskInput(price=100, equity=10_000, current_qty=2, target_qty=2))
    mgr.apply(RiskInput(price=110, equity=10_100, current_qty=2, target_qty=2))

    # Price falls below trailing stop (110 * 0.95 = 104.5), strategy still wants to hold.
    result = mgr.apply(RiskInput(price=104, equity=10_050, current_qty=2, target_qty=2))

    assert result.approved_qty == 0.0
    triggered = [a for a in alerts if a.code == "risk.dynamic_stop.triggered"]
    enforced = [a for a in alerts if a.code == "risk.dynamic_stop.enforced"]
    assert len(triggered) == 1
    assert len(enforced) == 1


def test_dynamic_stop_loss_forces_flatten_after_reversal_short() -> None:
    mgr = RiskManager(
        RiskLimits(
            notional_cap=100_000,
            leverage_cap=10,
            dynamic_stop=DynamicStopConfig(trailing_pct=0.05),
        )
    )

    # Short improves from 100 -> 92, then rebounds above short trailing stop (92 * 1.05 = 96.6).
    mgr.apply(RiskInput(price=100, equity=10_000, current_qty=-3, target_qty=-3))
    mgr.apply(RiskInput(price=92, equity=10_200, current_qty=-3, target_qty=-3))
    result = mgr.apply(RiskInput(price=97, equity=10_150, current_qty=-3, target_qty=-3))

    assert result.approved_qty == 0.0


def test_dynamic_stop_resets_after_flatten_and_allows_reentry() -> None:
    mgr = RiskManager(
        RiskLimits(
            notional_cap=100_000,
            leverage_cap=10,
            dynamic_stop=DynamicStopConfig(trailing_pct=0.05),
        )
    )

    mgr.apply(RiskInput(price=100, equity=10_000, current_qty=1, target_qty=1))
    mgr.apply(RiskInput(price=110, equity=10_050, current_qty=1, target_qty=1))
    stop_hit = mgr.apply(RiskInput(price=104, equity=10_000, current_qty=1, target_qty=1))
    assert stop_hit.approved_qty == 0.0

    # Position is flattened externally; next signal can open a new position.
    reentry = mgr.apply(RiskInput(price=103, equity=10_000, current_qty=0, target_qty=1))
    assert reentry.approved_qty == 1


def test_dynamic_stop_rejects_invalid_trailing_pct_bounds() -> None:
    with pytest.raises(ValueError):
        RiskManager(
            RiskLimits(
                notional_cap=100_000,
                leverage_cap=10,
                dynamic_stop=DynamicStopConfig(trailing_pct=1.0),
            )
        )

    with pytest.raises(ValueError):
        RiskManager(
            RiskLimits(
                notional_cap=100_000,
                leverage_cap=10,
                dynamic_stop=DynamicStopConfig(trailing_pct=-0.01),
            )
        )


def test_dynamic_stop_allows_same_side_reduce_after_trigger() -> None:
    mgr = RiskManager(
        RiskLimits(
            notional_cap=100_000,
            leverage_cap=10,
            dynamic_stop=DynamicStopConfig(trailing_pct=0.05),
        )
    )

    mgr.apply(RiskInput(price=100, equity=10_000, current_qty=2, target_qty=2))
    mgr.apply(RiskInput(price=110, equity=10_000, current_qty=2, target_qty=2))

    # Trigger stop then request same-side reduction, which should be allowed.
    reduce_result = mgr.apply(RiskInput(price=104, equity=10_000, current_qty=2, target_qty=1))
    assert reduce_result.approved_qty == 1


def test_dynamic_stop_resets_when_side_flips() -> None:
    mgr = RiskManager(
        RiskLimits(
            notional_cap=100_000,
            leverage_cap=10,
            dynamic_stop=DynamicStopConfig(trailing_pct=0.05),
        )
    )

    # Long side: trigger stop.
    mgr.apply(RiskInput(price=100, equity=10_000, current_qty=1, target_qty=1))
    mgr.apply(RiskInput(price=110, equity=10_000, current_qty=1, target_qty=1))
    long_stop = mgr.apply(RiskInput(price=104, equity=10_000, current_qty=1, target_qty=1))
    assert long_stop.approved_qty == 0.0

    # Side flips to short; trailing state should reset and allow open.
    short_open = mgr.apply(RiskInput(price=103, equity=10_000, current_qty=-1, target_qty=-1))
    assert short_open.approved_qty == -1
