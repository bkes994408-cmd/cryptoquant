from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True)
class RiskLimits:
    notional_cap: float
    leverage_cap: float
    daily_stop_drawdown_pct: float | None = None


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
    """Apply minimal position caps for paper trading."""

    def __init__(self, limits: RiskLimits) -> None:
        if limits.notional_cap <= 0 or limits.leverage_cap <= 0:
            raise ValueError("risk caps must be positive")
        if limits.daily_stop_drawdown_pct is not None and limits.daily_stop_drawdown_pct <= 0:
            raise ValueError("daily_stop_drawdown_pct must be positive")
        self._limits = limits
        self._daily_anchor_day: date | None = None
        self._daily_anchor_equity: float | None = None
        self._daily_stop_triggered = False

    def apply(self, req: RiskInput) -> RiskResult:
        if req.price <= 0:
            return RiskResult(0.0, 0.0, 0.0, "rejected: invalid price")
        if req.equity <= 0:
            return RiskResult(0.0, 0.0, 0.0, "rejected: non-positive equity")

        self._refresh_daily_state(req)
        if self._daily_stop_triggered and self._is_opening_new_risk(req.current_qty, req.target_qty):
            return RiskResult(0.0, 0.0, 0.0, "rejected: daily stop")

        max_by_notional = self._limits.notional_cap / req.price
        max_by_leverage = (self._limits.leverage_cap * req.equity) / req.price
        max_abs_qty = min(max_by_notional, max_by_leverage)

        approved = req.target_qty
        reason = "approved"
        if abs(approved) > max_abs_qty:
            approved = max_abs_qty if approved > 0 else -max_abs_qty
            reason = "clamped: notional cap" if max_by_notional <= max_by_leverage else "clamped: leverage cap"

        notional = abs(approved) * req.price
        leverage = notional / req.equity
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
        if drawdown_pct >= stop_pct:
            self._daily_stop_triggered = True

    @staticmethod
    def _is_opening_new_risk(current_qty: float, target_qty: float) -> bool:
        if target_qty == 0:
            return False
        if current_qty == 0:
            return True
        if current_qty * target_qty < 0:
            return True
        return abs(target_qty) > abs(current_qty)
