from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from cryptoquant.oms import OMS, OrderStatus
from cryptoquant.risk.kill_switch import KillSwitch


@dataclass(frozen=True)
class Fill:
    client_order_id: str
    symbol: str
    qty: float
    requested_price: float
    fill_price: float
    slippage_cost: float
    fee: float
    notional: float
    ts: datetime


class PaperExecutor:
    """Minimal paper executor for market orders with slippage/fee model."""

    def __init__(
        self,
        oms: OMS,
        *,
        fee_bps: float = 4.0,
        slippage_bps: float = 2.0,
        kill_switch: KillSwitch | None = None,
    ) -> None:
        if fee_bps < 0 or slippage_bps < 0:
            raise ValueError("fee/slippage bps must be non-negative")
        self._oms = oms
        self._kill_switch = kill_switch
        self._fee_rate = fee_bps / 10_000
        self._slippage_rate = slippage_bps / 10_000
        self._fills: dict[str, Fill] = {}
        self._position_qty: dict[str, float] = {}

    def execute_market(
        self,
        *,
        client_order_id: str,
        symbol: str,
        qty: float,
        mark_price: float,
        ts: datetime,
    ) -> Fill:
        if qty == 0:
            raise ValueError("qty must be non-zero")
        if mark_price <= 0:
            raise ValueError("mark_price must be positive")
        if self._kill_switch is not None:
            self._kill_switch.assert_allows_execution()

        existing = self._fills.get(client_order_id)
        if existing is not None:
            return existing

        order = self._oms.submit(client_order_id=client_order_id, symbol=symbol, qty=qty)
        if order.status == OrderStatus.FILLED:
            return self._fills[client_order_id]
        if order.status != OrderStatus.NEW:
            raise ValueError(f"cannot execute order in status={order.status}")

        side = 1.0 if qty > 0 else -1.0
        fill_price = mark_price * (1.0 + side * self._slippage_rate)
        notional = abs(qty) * fill_price
        fee = notional * self._fee_rate
        slippage_cost = abs(qty) * abs(fill_price - mark_price)

        fill = Fill(
            client_order_id=client_order_id,
            symbol=symbol,
            qty=qty,
            requested_price=mark_price,
            fill_price=fill_price,
            slippage_cost=slippage_cost,
            fee=fee,
            notional=notional,
            ts=ts,
        )
        self._fills[client_order_id] = fill

        self._position_qty[symbol] = self._position_qty.get(symbol, 0.0) + qty
        self._oms.fill(client_order_id)
        return fill

    def execute_to_target(
        self,
        *,
        client_order_id_prefix: str,
        symbol: str,
        current_qty: float,
        target_qty: float,
        mark_price: float,
        ts: datetime,
    ) -> list[Fill]:
        """Execute toward target qty.

        If position direction flips (e.g. +2 -> -1), split into two legs:
        1) reduce-only close to flat, 2) open in new direction.
        """
        if current_qty == target_qty:
            return []

        # Same direction (or opening/closing from flat): single leg is enough.
        if current_qty == 0 or target_qty == 0 or current_qty * target_qty > 0:
            delta = target_qty - current_qty
            return [
                self.execute_market(
                    client_order_id=f"{client_order_id_prefix}-single",
                    symbol=symbol,
                    qty=delta,
                    mark_price=mark_price,
                    ts=ts,
                )
            ]

        # Flip direction: close first, then open.
        close_qty = -current_qty
        open_qty = target_qty
        close_fill = self.execute_market(
            client_order_id=f"{client_order_id_prefix}-close",
            symbol=symbol,
            qty=close_qty,
            mark_price=mark_price,
            ts=ts,
        )
        open_fill = self.execute_market(
            client_order_id=f"{client_order_id_prefix}-open",
            symbol=symbol,
            qty=open_qty,
            mark_price=mark_price,
            ts=ts,
        )
        return [close_fill, open_fill]

    def position_qty(self, symbol: str) -> float:
        return self._position_qty.get(symbol, 0.0)
