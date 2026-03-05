from __future__ import annotations

from cryptoquant.monitoring import Alert, AlertLevel, Monitoring


class InMemorySink:
    def __init__(self) -> None:
        self.alerts: list[Alert] = []

    def emit(self, alert: Alert) -> None:
        self.alerts.append(alert)


def test_monitoring_emits_order_filled_alert() -> None:
    sink = InMemorySink()
    mon = Monitoring(sink)

    mon.record_order_filled("o-1")

    assert mon.orders == 1
    assert sink.alerts[-1].code == "order.filled"
    assert sink.alerts[-1].level == AlertLevel.INFO


def test_monitoring_escalates_reject_alert_level_after_threshold() -> None:
    sink = InMemorySink()
    mon = Monitoring(sink, reject_warn_threshold=2)

    mon.record_order_rejected("o-1", "risk")
    mon.record_order_rejected("o-2", "risk")

    assert mon.rejects == 2
    assert sink.alerts[-2].code == "order.rejected"
    assert sink.alerts[-2].level == AlertLevel.INFO
    assert sink.alerts[-1].code == "order.rejected"
    assert sink.alerts[-1].level == AlertLevel.WARN


def test_monitoring_safe_mode_alerts_enabled_and_disabled() -> None:
    sink = InMemorySink()
    mon = Monitoring(sink)

    mon.record_safe_mode(True, "kill switch engaged")
    mon.record_safe_mode(False, "recovered")

    assert sink.alerts[-2].code == "safe_mode.enabled"
    assert sink.alerts[-2].level == AlertLevel.ERROR
    assert sink.alerts[-1].code == "safe_mode.disabled"
    assert sink.alerts[-1].level == AlertLevel.INFO
