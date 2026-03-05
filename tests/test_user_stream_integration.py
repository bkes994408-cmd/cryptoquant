from __future__ import annotations

import json

from cryptoquant.execution import UserStreamProcessor, parse_binance_execution_report
from cryptoquant.oms import OMS, OrderStatus


def test_binance_payload_to_processor_updates_oms() -> None:
    oms = OMS()
    oms.submit(client_order_id="cid-1", symbol="BTCUSDT", qty=1.0)
    processor = UserStreamProcessor(oms)

    raw = json.dumps(
        {
            "e": "ORDER_TRADE_UPDATE",
            "o": {
                "c": "cid-1",
                "X": "FILLED",
                "r": "NONE",
            },
        }
    )

    report = parse_binance_execution_report(raw)
    assert report is not None
    processor.on_execution_report(report)

    assert oms.get("cid-1") is not None
    assert oms.get("cid-1").status == OrderStatus.FILLED
