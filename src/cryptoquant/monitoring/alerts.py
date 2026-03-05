from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol


class AlertLevel(str, Enum):
    INFO = "INFO"
    WARN = "WARN"
    ERROR = "ERROR"


@dataclass(frozen=True)
class Alert:
    level: AlertLevel
    code: str
    message: str


class AlertSink(Protocol):
    def emit(self, alert: Alert) -> None: ...


class Monitoring:
    """Minimal monitoring helper for orders/rejects/safe-mode alerts."""

    def __init__(self, sink: AlertSink, *, reject_warn_threshold: int = 3) -> None:
        self._sink = sink
        self._reject_warn_threshold = reject_warn_threshold
        self._orders = 0
        self._rejects = 0

    @property
    def orders(self) -> int:
        return self._orders

    @property
    def rejects(self) -> int:
        return self._rejects

    def record_order_filled(self, client_order_id: str) -> None:
        self._orders += 1
        self._sink.emit(
            Alert(
                level=AlertLevel.INFO,
                code="order.filled",
                message=f"order filled: {client_order_id}",
            )
        )

    def record_order_rejected(self, client_order_id: str, reason: str) -> None:
        self._rejects += 1
        level = AlertLevel.WARN if self._rejects >= self._reject_warn_threshold else AlertLevel.INFO
        self._sink.emit(
            Alert(
                level=level,
                code="order.rejected",
                message=f"order rejected: {client_order_id} ({reason})",
            )
        )

    def record_safe_mode(self, enabled: bool, reason: str) -> None:
        self._sink.emit(
            Alert(
                level=AlertLevel.ERROR if enabled else AlertLevel.INFO,
                code="safe_mode.enabled" if enabled else "safe_mode.disabled",
                message=reason,
            )
        )
