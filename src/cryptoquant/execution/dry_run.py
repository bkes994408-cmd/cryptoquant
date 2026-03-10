from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from cryptoquant.monitoring import Alert, Monitoring
from cryptoquant.oms import OMS, OrderStatus

from .live import LiveExecutor, LiveOrderRequest, OrderGateway
from .user_stream import ExecutionReport, UserStreamProcessor


@dataclass(frozen=True)
class DryRunRequest:
    symbol: str
    qty: float
    client_order_id: str


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

    return run_testnet_dry_run_batch(
        gateway=gateway,
        requests=[DryRunRequest(symbol=symbol, qty=qty, client_order_id=client_order_id)],
        simulate_fill_event=simulate_fill_event,
    )[0]


def run_testnet_dry_run_batch(
    *,
    gateway: OrderGateway,
    requests: Iterable[DryRunRequest],
    simulate_fill_event: bool = True,
) -> list[DryRunResult]:
    """Run dry-run execution for multiple symbol/qty requests in one session."""

    normalized = list(requests)
    if not normalized:
        raise ValueError("requests cannot be empty")

    oms = OMS()
    sink = _InMemorySink()
    monitoring = Monitoring(sink)
    executor = LiveExecutor(oms, gateway)
    stream = UserStreamProcessor(oms, monitoring=monitoring)

    results: list[DryRunResult] = []
    last_alert_idx = 0
    for req in normalized:
        ack = executor.execute_market(
            LiveOrderRequest(
                client_order_id=req.client_order_id,
                symbol=req.symbol,
                qty=req.qty,
            )
        )

        if simulate_fill_event:
            stream.on_execution_report(
                ExecutionReport(client_order_id=req.client_order_id, order_status="FILLED")
            )

        order = oms.get(req.client_order_id)
        if order is None:
            raise RuntimeError("order not found after dry run")

        order_alerts = tuple(sink.alerts[last_alert_idx:])
        last_alert_idx = len(sink.alerts)

        results.append(
            DryRunResult(
                client_order_id=req.client_order_id,
                exchange_order_id=ack.exchange_order_id,
                final_status=order.status,
                alerts=order_alerts,
            )
        )

    return results
