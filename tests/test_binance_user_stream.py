from __future__ import annotations

import json

from cryptoquant.execution import ExecutionReport, parse_binance_execution_report


def test_parse_binance_execution_report_from_wrapped_payload() -> None:
    raw = json.dumps(
        {
            "stream": "abc",
            "data": {
                "e": "ORDER_TRADE_UPDATE",
                "o": {
                    "c": "cid-1",
                    "X": "FILLED",
                    "r": "NONE",
                },
            },
        }
    )

    report = parse_binance_execution_report(raw)

    assert report == ExecutionReport(client_order_id="cid-1", order_status="FILLED", reject_reason=None)


def test_parse_binance_execution_report_rejected_reason() -> None:
    raw = json.dumps(
        {
            "e": "ORDER_TRADE_UPDATE",
            "o": {
                "c": "cid-2",
                "X": "REJECTED",
                "r": "PRICE_FILTER",
            },
        }
    )

    report = parse_binance_execution_report(raw)

    assert report is not None
    assert report.order_status == "REJECTED"
    assert report.reject_reason == "PRICE_FILTER"


def test_parse_binance_execution_report_non_order_event_returns_none() -> None:
    raw = json.dumps({"e": "ACCOUNT_UPDATE"})
    assert parse_binance_execution_report(raw) is None
