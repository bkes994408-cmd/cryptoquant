from __future__ import annotations

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
