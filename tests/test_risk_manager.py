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

    mgr.apply(
        RiskInput(
            price=100,
            equity=1000,
            current_qty=0,
            target_qty=0,
            as_of=datetime(2026, 2, 28, 0, 0, tzinfo=timezone.utc),
        )
    )

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

    mgr.apply(
        RiskInput(
            price=100,
            equity=940,
            current_qty=2,
            target_qty=2,
            as_of=datetime(2026, 2, 28, 1, 0, tzinfo=timezone.utc),
        )
    )

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

    mgr.apply(RiskInput(price=100, equity=10_000, current_qty=2, target_qty=2))
    mgr.apply(RiskInput(price=110, equity=10_100, current_qty=2, target_qty=2))

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

    reentry = mgr.apply(RiskInput(price=103, equity=10_000, current_qty=0, target_qty=1))
    assert reentry.approved_qty == 1


def test_dynamic_stop_trailing_pct_must_be_in_open_interval_zero_one() -> None:
    with pytest.raises(ValueError, match=r"dynamic_stop.trailing_pct must be in \(0, 1\)"):
        DynamicStopConfig(trailing_pct=0.0)

    with pytest.raises(ValueError, match=r"dynamic_stop.trailing_pct must be in \(0, 1\)"):
        DynamicStopConfig(trailing_pct=-0.01)

    with pytest.raises(ValueError, match=r"dynamic_stop.trailing_pct must be in \(0, 1\)"):
        RiskManager(
            RiskLimits(
                notional_cap=10_000,
                leverage_cap=5,
                dynamic_stop=DynamicStopConfig(trailing_pct=1.0),
            )
        )

    with pytest.raises(ValueError, match=r"dynamic_stop.trailing_pct must be in \(0, 1\)"):
        RiskManager(
            RiskLimits(
                notional_cap=10_000,
                leverage_cap=5,
                dynamic_stop=DynamicStopConfig(trailing_pct=1.2),
            )
        )


def test_dynamic_stop_allows_same_side_reduction_after_trigger() -> None:
    mgr = RiskManager(
        RiskLimits(
            notional_cap=100_000,
            leverage_cap=10,
            dynamic_stop=DynamicStopConfig(trailing_pct=0.05),
        )
    )

    mgr.apply(RiskInput(price=100, equity=10_000, current_qty=3, target_qty=3))
    mgr.apply(RiskInput(price=110, equity=10_050, current_qty=3, target_qty=3))

    stop_hit = mgr.apply(RiskInput(price=104, equity=10_000, current_qty=3, target_qty=3))
    assert stop_hit.approved_qty == 0.0

    reduced = mgr.apply(RiskInput(price=103, equity=9_980, current_qty=3, target_qty=1))
    assert reduced.approved_qty == 1
    assert reduced.reason == "approved"


def test_dynamic_stop_side_flip_sequence_resets_extreme_multi_short_multi() -> None:
    mgr = RiskManager(
        RiskLimits(
            notional_cap=100_000,
            leverage_cap=10,
            dynamic_stop=DynamicStopConfig(trailing_pct=0.05),
        )
    )

    mgr.apply(RiskInput(price=100, equity=10_000, current_qty=2, target_qty=2))
    mgr.apply(RiskInput(price=110, equity=10_100, current_qty=2, target_qty=2))

    flip_to_short = mgr.apply(RiskInput(price=104, equity=10_050, current_qty=-2, target_qty=-2))
    assert flip_to_short.approved_qty == -2

    mgr.apply(RiskInput(price=95, equity=10_120, current_qty=-2, target_qty=-2))
    short_stop_hit = mgr.apply(RiskInput(price=100, equity=10_060, current_qty=-2, target_qty=-2))
    assert short_stop_hit.approved_qty == 0.0

    mgr.apply(RiskInput(price=99, equity=10_040, current_qty=0, target_qty=0))
    long_reopen = mgr.apply(RiskInput(price=101, equity=10_030, current_qty=2, target_qty=2))
    assert long_reopen.approved_qty == 2


def test_utilization_alerts_are_deduplicated_for_identical_payloads() -> None:
    alerts: list[RiskAlert] = []
    mgr = RiskManager(
        RiskLimits(notional_cap=1_000, leverage_cap=2, warn_utilization_pct=0.8),
        alert_sink=alerts.append,
    )

    mgr.apply(RiskInput(price=100, equity=500, current_qty=0, target_qty=8.5))
    mgr.apply(RiskInput(price=100, equity=500, current_qty=0, target_qty=8.5))

    codes = [a.code for a in alerts]
    assert codes.count("risk.notional.near_cap") == 1
    assert codes.count("risk.leverage.near_cap") == 1
