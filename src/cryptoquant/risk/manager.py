from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RiskLimits:
    notional_cap: float
    leverage_cap: float


@dataclass(frozen=True)
class RiskInput:
    price: float
    equity: float
    current_qty: float
    target_qty: float


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
        self._limits = limits

    def apply(self, req: RiskInput) -> RiskResult:
        if req.price <= 0:
            return RiskResult(0.0, 0.0, 0.0, "rejected: invalid price")
        if req.equity <= 0:
            return RiskResult(0.0, 0.0, 0.0, "rejected: non-positive equity")

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
