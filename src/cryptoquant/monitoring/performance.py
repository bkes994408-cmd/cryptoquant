from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from math import sqrt


@dataclass(frozen=True)
class PositionPerformance:
    symbol: str
    qty: float
    avg_entry_price: float
    mark_price: float | None
    notional_exposure: float
    unrealized_pnl: float


@dataclass(frozen=True)
class PerformanceSnapshot:
    ts: datetime
    realized_pnl: float
    unrealized_pnl: float
    fee_total: float
    slippage_total: float
    net_pnl: float
    max_drawdown: float
    close_trades: int
    win_rate: float
    sharpe_like: float
    by_symbol: dict[str, PositionPerformance]


@dataclass
class _PositionState:
    qty: float = 0.0
    avg_entry_price: float = 0.0
    mark_price: float | None = None


class RealTimePerformanceMonitor:
    """Track real-time strategy performance from fills + mark updates.

    Core metrics:
    - realized/unrealized/net pnl
    - cumulative fee/slippage
    - max drawdown from equity curve
    - close-trade win rate
    - simple sharpe-like score from equity deltas
    """

    def __init__(self) -> None:
        self._positions: dict[str, _PositionState] = {}
        self._realized_pnl = 0.0
        self._fee_total = 0.0
        self._slippage_total = 0.0

        self._equity_peak = 0.0
        self._max_drawdown = 0.0
        self._last_net = 0.0
        self._returns: list[float] = []

        self._close_trades = 0
        self._winning_closes = 0

    def record_fill(
        self,
        *,
        symbol: str,
        qty: float,
        fill_price: float,
        fee: float = 0.0,
        slippage_cost: float = 0.0,
        ts: datetime | None = None,
    ) -> PerformanceSnapshot:
        if qty == 0:
            raise ValueError("qty must be non-zero")
        if fill_price <= 0:
            raise ValueError("fill_price must be positive")
        if fee < 0 or slippage_cost < 0:
            raise ValueError("fee/slippage must be non-negative")

        pos = self._positions.setdefault(symbol, _PositionState())
        old_qty = pos.qty
        old_avg = pos.avg_entry_price
        close_pnl = 0.0

        if old_qty == 0 or old_qty * qty > 0:
            new_qty = old_qty + qty
            total_cost = abs(old_qty) * old_avg + abs(qty) * fill_price
            pos.avg_entry_price = total_cost / abs(new_qty)
            pos.qty = new_qty
        else:
            close_qty = min(abs(old_qty), abs(qty))
            side = 1.0 if old_qty > 0 else -1.0
            close_pnl = close_qty * (fill_price - old_avg) * side
            self._realized_pnl += close_pnl
            self._close_trades += 1
            if close_pnl > 0:
                self._winning_closes += 1

            new_qty = old_qty + qty
            if new_qty == 0:
                pos.qty = 0.0
                pos.avg_entry_price = 0.0
            elif old_qty * new_qty > 0:
                pos.qty = new_qty
            else:
                pos.qty = new_qty
                pos.avg_entry_price = fill_price

        self._fee_total += fee
        self._slippage_total += slippage_cost
        return self._build_snapshot(ts=ts)

    def record_mark_price(
        self,
        *,
        symbol: str,
        mark_price: float,
        ts: datetime | None = None,
    ) -> PerformanceSnapshot:
        if mark_price <= 0:
            raise ValueError("mark_price must be positive")
        pos = self._positions.setdefault(symbol, _PositionState())
        pos.mark_price = mark_price
        return self._build_snapshot(ts=ts)

    def snapshot(self, *, ts: datetime | None = None) -> PerformanceSnapshot:
        return self._build_snapshot(ts=ts)

    def _build_snapshot(self, *, ts: datetime | None = None) -> PerformanceSnapshot:
        unrealized = 0.0
        by_symbol: dict[str, PositionPerformance] = {}

        for symbol, pos in self._positions.items():
            symbol_unrealized = 0.0
            symbol_exposure = 0.0
            if pos.mark_price is not None and pos.qty != 0:
                symbol_unrealized = pos.qty * (pos.mark_price - pos.avg_entry_price)
                symbol_exposure = abs(pos.qty) * pos.mark_price
            unrealized += symbol_unrealized
            by_symbol[symbol] = PositionPerformance(
                symbol=symbol,
                qty=pos.qty,
                avg_entry_price=pos.avg_entry_price,
                mark_price=pos.mark_price,
                notional_exposure=symbol_exposure,
                unrealized_pnl=symbol_unrealized,
            )

        net = self._realized_pnl + unrealized - self._fee_total - self._slippage_total

        if net > self._equity_peak:
            self._equity_peak = net
        drawdown = self._equity_peak - net
        if drawdown > self._max_drawdown:
            self._max_drawdown = drawdown

        delta = net - self._last_net
        self._returns.append(delta)
        self._last_net = net

        sharpe_like = 0.0
        if len(self._returns) > 1:
            mean = sum(self._returns) / len(self._returns)
            var = sum((x - mean) ** 2 for x in self._returns) / len(self._returns)
            std = sqrt(var)
            sharpe_like = 0.0 if std == 0 else mean / std

        win_rate = 0.0 if self._close_trades == 0 else self._winning_closes / self._close_trades

        return PerformanceSnapshot(
            ts=ts or datetime.now(timezone.utc),
            realized_pnl=self._realized_pnl,
            unrealized_pnl=unrealized,
            fee_total=self._fee_total,
            slippage_total=self._slippage_total,
            net_pnl=net,
            max_drawdown=self._max_drawdown,
            close_trades=self._close_trades,
            win_rate=win_rate,
            sharpe_like=sharpe_like,
            by_symbol=by_symbol,
        )
