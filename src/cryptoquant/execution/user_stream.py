from __future__ import annotations

from dataclasses import dataclass

from cryptoquant.monitoring import Monitoring
from cryptoquant.oms import OMS, OrderStatus


@dataclass(frozen=True)
class ExecutionReport:
    """Normalized user-stream execution report."""

    client_order_id: str
    order_status: str
    reject_reason: str | None = None


class UserStreamProcessor:
    """Apply user-stream execution reports to OMS state."""

    def __init__(self, oms: OMS, *, monitoring: Monitoring | None = None) -> None:
        self._oms = oms
        self._monitoring = monitoring

    def on_execution_report(self, event: ExecutionReport) -> None:
        order = self._oms.get(event.client_order_id)
        if order is None:
            return

        status = event.order_status.upper()

        # ACK/NEW-like states keep order as NEW in this minimal OMS.
        if status in {"NEW", "ACK", "PARTIALLY_FILLED"}:
            return

        if status == "FILLED":
            if order.status == OrderStatus.FILLED:
                return
            self._oms.fill(event.client_order_id)
            if self._monitoring is not None:
                self._monitoring.record_order_filled(event.client_order_id)
            return

        if status in {"CANCELED", "EXPIRED"}:
            if order.status == OrderStatus.CANCELED:
                return
            self._oms.cancel(event.client_order_id)
            return

        if status in {"REJECTED"}:
            reason = event.reject_reason or "exchange rejected"
            if order.status == OrderStatus.REJECTED:
                return
            self._oms.reject(event.client_order_id, reason=reason)
            if self._monitoring is not None:
                self._monitoring.record_order_rejected(event.client_order_id, reason)
            return
