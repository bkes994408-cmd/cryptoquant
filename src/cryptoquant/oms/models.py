from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class OrderStatus(str, Enum):
    NEW = "NEW"
    FILLED = "FILLED"
    CANCELED = "CANCELED"
    REJECTED = "REJECTED"


@dataclass
class Order:
    client_order_id: str
    symbol: str
    qty: float
    status: OrderStatus = OrderStatus.NEW
    reject_reason: str | None = None
