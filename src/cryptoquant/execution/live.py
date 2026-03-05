from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from cryptoquant.oms import OMS, OrderStatus
from cryptoquant.risk import KillSwitch


@dataclass(frozen=True)
class LiveOrderRequest:
    client_order_id: str
    symbol: str
    qty: float


@dataclass(frozen=True)
class LiveOrderAck:
    client_order_id: str
    exchange_order_id: str
    accepted_at: datetime


class OrderGateway(Protocol):
    def place_market_order(self, *, symbol: str, qty: float, client_order_id: str) -> LiveOrderAck: ...


class LiveExecutor:
    """Live-mode execution skeleton.

    Responsibilities:
    - Enforce kill switch before sending.
    - Keep clientOrderId idempotency by deferring to OMS submit/get.
    - Delegate actual exchange call to an injectable gateway.
    """

    def __init__(self, oms: OMS, gateway: OrderGateway, *, kill_switch: KillSwitch | None = None) -> None:
        self._oms = oms
        self._gateway = gateway
        self._kill_switch = kill_switch
        self._acks: dict[str, LiveOrderAck] = {}

    def execute_market(self, req: LiveOrderRequest) -> LiveOrderAck:
        if req.qty == 0:
            raise ValueError("qty must be non-zero")
        if self._kill_switch is not None:
            self._kill_switch.assert_allows_execution()

        cached = self._acks.get(req.client_order_id)
        if cached is not None:
            return cached

        order = self._oms.submit(client_order_id=req.client_order_id, symbol=req.symbol, qty=req.qty)
        if order.status != OrderStatus.NEW:
            raise ValueError(f"cannot send live order in status={order.status}")

        ack = self._gateway.place_market_order(
            symbol=req.symbol,
            qty=req.qty,
            client_order_id=req.client_order_id,
        )
        self._acks[req.client_order_id] = ack
        return ack

    def get_ack(self, client_order_id: str) -> LiveOrderAck | None:
        return self._acks.get(client_order_id)
