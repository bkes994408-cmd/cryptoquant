from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from typing import Callable


class RiskAlertLevel(str, Enum):
    INFO = "INFO"
    WARN = "WARN"
    ERROR = "ERROR"


@dataclass(frozen=True)
class RiskAlert:
    level: RiskAlertLevel
    code: str
    message: str


@dataclass(frozen=True)
class DynamicStopConfig:
    trailing_pct: float

    def __post_init__(self) -> None:
        if not (0 < self.trailing_pct < 1):
            raise ValueError("dynamic_stop.trailing_pct must be in (0, 1)")


@dataclass(frozen=True)
class RiskLimits:
    notional_cap: float
    leverage_cap: float
    daily_stop_drawdown_pct: float | None = None
    warn_utilization_pct: float = 0.85
    dynamic_stop: DynamicStopConfig | None = None


@dataclass(frozen=True)
class RiskInput:
    price: float
    equity: float
    current_qty: float
    target_qty: float
    as_of: datetime | None = None


@dataclass(frozen=True)
class RiskResult:
    approved_qty: float
    estimated_notional: float
    estimated_leverage: float
    reason: str


class RiskManager:
    """Apply position caps, real-time alerts, and dynamic stop-loss constraints."""

    def __init__(self, limits: RiskLimits, *, alert_sink: Callable[[RiskAlert], None] | None = None) -> None:
        if limits.notional_cap <= 0 or limits.leverage_cap <= 0:
            raise ValueError("risk caps must be positive")
        if limits.daily_stop_drawdown_pct is not None and limits.daily_stop_drawdown_pct <= 0:
            raise ValueError("daily_stop_drawdown_pct must be positive")
        if not (0 < limits.warn_utilization_pct < 1):
            raise ValueError("warn_utilization_pct must be in (0, 1)")
        if limits.dynamic_stop is not None and not (0 < limits.dynamic_stop.trailing_pct < 1):
            raise ValueError("dynamic_stop.trailing_pct must be in (0, 1)")
        self._limits = limits
        self._alert_sink = alert_sink
        self._daily_anchor_day: date | None = None
        self._daily_anchor_equity: float | None = None
        self._daily_stop_triggered = False

        self._tracked_side: int = 0
        self._tracked_extreme_price: float | None = None
        self._dynamic_stop_triggered = False

        self._notional_warn_active = False
        self._leverage_warn_active = False

    def apply(self, req: RiskInput) -> RiskResult:
        if req.price <= 0:
            return RiskResult(0.0, 0.0, 0.0, "rejected: invalid price")
        if req.equity <= 0:
            return RiskResult(0.0, 0.0, 0.0, "rejected: non-positive equity")

        self._refresh_daily_state(req)
        self._refresh_dynamic_stop_state(req)

        approved = req.target_qty
        if self._daily_stop_triggered and self._is_opening_new_risk(req.current_qty, approved):
            return RiskResult(0.0, 0.0, 0.0, "rejected: daily stop")

        if self._dynamic_stop_triggered and self._is_maintaining_or_adding_risk(req.current_qty, approved):
            approved = 0.0
            self._emit_alert(
                RiskAlert(
                    level=RiskAlertLevel.ERROR,
                    code="risk.dynamic_stop.enforced",
                    message="dynamic stop-loss enforced: force flatten target to zero",
                )
            )

        max_by_notional = self._limits.notional_cap / req.price
        max_by_leverage = (self._limits.leverage_cap * req.equity) / req.price
        max_abs_qty = min(max_by_notional, max_by_leverage)

        reason = "approved"
        if abs(approved) > max_abs_qty:
            approved = max_abs_qty if approved > 0 else -max_abs_qty
            reason = "clamped: notional cap" if max_by_notional <= max_by_leverage else "clamped: leverage cap"

        notional = abs(approved) * req.price
        leverage = notional / req.equity
        self._emit_utilization_alerts(notional=notional, leverage=leverage)
        return RiskResult(approved, notional, leverage, reason)

    def _refresh_daily_state(self, req: RiskInput) -> None:
        stop_pct = self._limits.daily_stop_drawdown_pct
        if stop_pct is None:
            return

        day = req.as_of.date() if req.as_of is not None else date.today()
        if self._daily_anchor_day != day:
            self._daily_anchor_day = day
            self._daily_anchor_equity = req.equity
            self._daily_stop_triggered = False
            return

        anchor = self._daily_anchor_equity
        if anchor is None or anchor <= 0:
            return
        drawdown_pct = (anchor - req.equity) / anchor
        if drawdown_pct >= stop_pct and not self._daily_stop_triggered:
            self._daily_stop_triggered = True
            self._emit_alert(
                RiskAlert(
                    level=RiskAlertLevel.ERROR,
                    code="risk.daily_stop.triggered",
                    message=f"daily stop triggered at drawdown={drawdown_pct:.2%}",
                )
            )

    def _refresh_dynamic_stop_state(self, req: RiskInput) -> None:
        conf = self._limits.dynamic_stop
        if conf is None:
            return

        current_side = self._side(req.current_qty)
        if current_side == 0:
            self._tracked_side = 0
            self._tracked_extreme_price = None
            self._dynamic_stop_triggered = False
            return

        if self._tracked_side != current_side:
            self._tracked_side = current_side
            self._tracked_extreme_price = req.price
            self._dynamic_stop_triggered = False
            return

        if self._tracked_extreme_price is None:
            self._tracked_extreme_price = req.price
            return

        if current_side > 0:
            self._tracked_extreme_price = max(self._tracked_extreme_price, req.price)
            stop_price = self._tracked_extreme_price * (1 - conf.trailing_pct)
            hit = req.price <= stop_price
        else:
            self._tracked_extreme_price = min(self._tracked_extreme_price, req.price)
            stop_price = self._tracked_extreme_price * (1 + conf.trailing_pct)
            hit = req.price >= stop_price

        if hit and not self._dynamic_stop_triggered:
            self._dynamic_stop_triggered = True
            self._emit_alert(
                RiskAlert(
                    level=RiskAlertLevel.WARN,
                    code="risk.dynamic_stop.triggered",
                    message=(
                        f"dynamic stop triggered: side={'LONG' if current_side > 0 else 'SHORT'} "
                        f"price={req.price:.6f} stop={stop_price:.6f}"
                    ),
                )
            )

    def _emit_utilization_alerts(self, *, notional: float, leverage: float) -> None:
        notional_util = notional / self._limits.notional_cap
        leverage_util = leverage / self._limits.leverage_cap

        notional_over = notional_util >= self._limits.warn_utilization_pct
        leverage_over = leverage_util >= self._limits.warn_utilization_pct

        if notional_over and not self._notional_warn_active:
            self._emit_alert(
                RiskAlert(
                    level=RiskAlertLevel.WARN,
                    code="risk.notional.near_cap",
                    message=f"notional utilization high: {notional_util:.1%}",
                )
            )
        self._notional_warn_active = notional_over

        if leverage_over and not self._leverage_warn_active:
            self._emit_alert(
                RiskAlert(
                    level=RiskAlertLevel.WARN,
                    code="risk.leverage.near_cap",
                    message=f"leverage utilization high: {leverage_util:.1%}",
                )
            )
        self._leverage_warn_active = leverage_over

    def _emit_alert(self, alert: RiskAlert) -> None:
        if self._alert_sink is not None:
            self._alert_sink(alert)

    @staticmethod
    def _is_opening_new_risk(current_qty: float, target_qty: float) -> bool:
        if target_qty == 0:
            return False
        if current_qty == 0:
            return True
        if current_qty * target_qty < 0:
            return True
        return abs(target_qty) > abs(current_qty)

    @staticmethod
    def _is_maintaining_or_adding_risk(current_qty: float, target_qty: float) -> bool:
        if current_qty == 0:
            return False
        if target_qty == 0:
            return False
        if current_qty * target_qty < 0:
            return False
        return abs(target_qty) >= abs(current_qty)

    @staticmethod
    def _side(qty: float) -> int:
        if qty > 0:
            return 1
        if qty < 0:
            return -1
        return 0
