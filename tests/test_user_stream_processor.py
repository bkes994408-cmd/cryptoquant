from __future__ import annotations

from cryptoquant.execution import ExecutionReport, UserStreamProcessor
from cryptoquant.monitoring import Alert, Monitoring
from cryptoquant.oms import OMS, OrderStatus


class InMemorySink:
    def __init__(self) -> None:
        self.alerts: list[Alert] = []

    def emit(self, alert: Alert) -> None:
        self.alerts.append(alert)


def test_user_stream_processor_marks_order_filled() -> None:
    oms = OMS()
    oms.submit(client_order_id="o-1", symbol="BTCUSDT", qty=1.0)
    processor = UserStreamProcessor(oms)

    processor.on_execution_report(ExecutionReport(client_order_id="o-1", order_status="FILLED"))

    assert oms.get("o-1") is not None
    assert oms.get("o-1").status == OrderStatus.FILLED


def test_user_stream_processor_marks_order_rejected_and_emits_alert() -> None:
    oms = OMS()
    oms.submit(client_order_id="o-2", symbol="BTCUSDT", qty=1.0)
    sink = InMemorySink()
    mon = Monitoring(sink)
    processor = UserStreamProcessor(oms, monitoring=mon)

    processor.on_execution_report(
        ExecutionReport(client_order_id="o-2", order_status="REJECTED", reject_reason="price filter")
    )

    assert oms.get("o-2") is not None
    assert oms.get("o-2").status == OrderStatus.REJECTED
    assert oms.get("o-2").reject_reason == "price filter"
    assert sink.alerts[-1].code == "order.rejected"


def test_user_stream_processor_ignores_unknown_order_id() -> None:
    oms = OMS()
    processor = UserStreamProcessor(oms)

    processor.on_execution_report(ExecutionReport(client_order_id="missing", order_status="FILLED"))

    assert oms.get("missing") is None


def test_user_stream_processor_treats_new_like_status_as_noop() -> None:
    oms = OMS()
    oms.submit(client_order_id="o-3", symbol="BTCUSDT", qty=1.0)
    processor = UserStreamProcessor(oms)

    processor.on_execution_report(ExecutionReport(client_order_id="o-3", order_status="NEW"))
    processor.on_execution_report(ExecutionReport(client_order_id="o-3", order_status="ACK"))
    processor.on_execution_report(ExecutionReport(client_order_id="o-3", order_status="PARTIALLY_FILLED"))

    assert oms.get("o-3") is not None
    assert oms.get("o-3").status == OrderStatus.NEW
