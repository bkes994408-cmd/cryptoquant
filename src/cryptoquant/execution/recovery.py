from __future__ import annotations

from dataclasses import dataclass

from cryptoquant.oms import OrderStatus


@dataclass(frozen=True)
class RecoverySnapshot:
    """State loaded from REST snapshot at boot time."""

    positions: dict[str, float]
    orders: dict[str, OrderStatus]


@dataclass(frozen=True)
class UserStreamEvent:
    """Incremental state update from user stream."""

    kind: str  # "position" | "order"
    key: str
    value: float | OrderStatus


@dataclass(frozen=True)
class RecoveredState:
    positions: dict[str, float]
    orders: dict[str, OrderStatus]


def recover_state(snapshot: RecoverySnapshot, user_stream_events: list[UserStreamEvent]) -> RecoveredState:
    """Recover trading state by overlaying user stream updates on REST snapshot.

    The recovery rule is simple and deterministic: start from REST snapshot and
    apply user-stream events in order. Latest event wins.
    """

    positions = dict(snapshot.positions)
    orders = dict(snapshot.orders)

    for event in user_stream_events:
        if event.kind == "position":
            positions[event.key] = float(event.value)
            continue
        if event.kind == "order":
            if isinstance(event.value, OrderStatus):
                orders[event.key] = event.value
            else:
                orders[event.key] = OrderStatus(str(event.value))
            continue
        raise ValueError(f"unsupported user stream event kind={event.kind}")

    return RecoveredState(positions=positions, orders=orders)
