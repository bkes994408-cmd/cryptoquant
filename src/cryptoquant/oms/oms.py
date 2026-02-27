from __future__ import annotations

from cryptoquant.oms.models import Order, OrderStatus


class OMS:
    """Minimal idempotent OMS with a tiny state machine."""

    def __init__(self) -> None:
        self._orders: dict[str, Order] = {}

    def submit(self, *, client_order_id: str, symbol: str, qty: float) -> Order:
        if client_order_id in self._orders:
            return self._orders[client_order_id]
        order = Order(client_order_id=client_order_id, symbol=symbol, qty=qty)
        self._orders[client_order_id] = order
        return order

    def fill(self, client_order_id: str) -> Order:
        return self._transition(client_order_id, OrderStatus.FILLED)

    def cancel(self, client_order_id: str) -> Order:
        return self._transition(client_order_id, OrderStatus.CANCELED)

    def reject(self, client_order_id: str, reason: str) -> Order:
        order = self._transition(client_order_id, OrderStatus.REJECTED)
        order.reject_reason = reason
        return order

    def get(self, client_order_id: str) -> Order | None:
        return self._orders.get(client_order_id)

    def _transition(self, client_order_id: str, target: OrderStatus) -> Order:
        order = self._orders[client_order_id]
        if order.status != OrderStatus.NEW:
            raise ValueError(f"invalid transition: {order.status} -> {target}")
        order.status = target
        return order
