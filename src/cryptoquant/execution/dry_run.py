from __future__ import annotations

from dataclasses import dataclass

from cryptoquant.monitoring import Alert, Monitoring
from cryptoquant.oms import OMS, OrderStatus

from .live import LiveExecutor, LiveOrderRequest, OrderGateway
from .user_stream import ExecutionReport, UserStreamProcessor


@dataclass(frozen=True)
class DryRunResult:
    client_order_id: str
    exchange_order_id: str
    final_status: OrderStatus
    alerts: tuple[Alert, ...]


class _InMemorySink:
    def __init__(self) -> None:
        self.alerts: list[Alert] = []

    def emit(self, alert: Alert) -> None:
        self.alerts.append(alert)


def run_testnet_dry_run(
    *,
    gateway: OrderGateway,
    symbol: str,
    qty: float,
    client_order_id: str,
    simulate_fill_event: bool = True,
) -> DryRunResult:
    """Run minimal end-to-end dry-run path: LiveExecutor -> UserStream -> OMS."""

    oms = OMS()
    sink = _InMemorySink()
    monitoring = Monitoring(sink)
    executor = LiveExecutor(oms, gateway)
    stream = UserStreamProcessor(oms, monitoring=monitoring)

    ack = executor.execute_market(
        LiveOrderRequest(client_order_id=client_order_id, symbol=symbol, qty=qty)
    )

    if simulate_fill_event:
        stream.on_execution_report(
            ExecutionReport(client_order_id=client_order_id, order_status="FILLED")
        )

    order = oms.get(client_order_id)
    if order is None:
        raise RuntimeError("order not found after dry run")

    return DryRunResult(
        client_order_id=client_order_id,
        exchange_order_id=ack.exchange_order_id,
        final_status=order.status,
        alerts=tuple(sink.alerts),
    )
