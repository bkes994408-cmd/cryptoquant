from __future__ import annotations

import json

from cryptoquant.execution import (
    BinanceUserStreamClient,
    ExecutionReport,
    parse_binance_execution_report,
)


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


def test_user_stream_client_reconnects_and_emits_report() -> None:
    class Provider:
        def __init__(self) -> None:
            self.calls = 0
            self.clear_calls = 0

        def get_listen_key(self) -> str:
            self.calls += 1
            return f"lk-{self.calls}"

        def clear_cached_listen_key(self) -> None:
            self.clear_calls += 1

    class FailingWS:
        def recv(self) -> str:
            raise RuntimeError("socket dropped")

        def close(self) -> None:
            return None

    class SingleMessageWS:
        def __init__(self) -> None:
            self._done = False

        def recv(self) -> str:
            if self._done:
                raise RuntimeError("done")
            self._done = True
            return json.dumps(
                {
                    "e": "ORDER_TRADE_UPDATE",
                    "o": {"c": "cid-1", "X": "FILLED", "r": "NONE"},
                }
            )

        def close(self) -> None:
            return None

    provider = Provider()
    sleeps: list[float] = []
    factory_calls = {"n": 0}
    reports: list[ExecutionReport] = []

    def ws_factory(_: str):
        factory_calls["n"] += 1
        if factory_calls["n"] == 1:
            return FailingWS()
        return SingleMessageWS()

    client: BinanceUserStreamClient | None = None

    def on_report(report: ExecutionReport) -> None:
        reports.append(report)
        assert client is not None
        client.stop()

    client = BinanceUserStreamClient(
        listen_key_provider=provider,
        on_execution_report=on_report,
        ws_factory=ws_factory,
        reconnect_initial_sec=0.5,
        reconnect_max_sec=2.0,
        sleep_fn=sleeps.append,
    )

    client.run_forever()

    assert provider.calls == 2
    assert provider.clear_calls == 1
    assert factory_calls["n"] == 2
    assert sleeps == [0.5]
    assert len(reports) == 1
    assert reports[0].client_order_id == "cid-1"


def test_user_stream_client_reconnect_request_forces_new_socket_without_backoff() -> None:
    class Provider:
        def __init__(self) -> None:
            self.calls = 0
            self.clear_calls = 0

        def get_listen_key(self) -> str:
            self.calls += 1
            return f"lk-{self.calls}"

        def clear_cached_listen_key(self) -> None:
            self.clear_calls += 1

    class ReconnectAwareWS:
        def __init__(self, *, client: BinanceUserStreamClient, first: bool) -> None:
            self.client = client
            self.first = first
            self.recv_calls = 0

        def recv(self) -> str:
            self.recv_calls += 1
            if self.first and self.recv_calls == 1:
                self.client.reconnect()
                return json.dumps({"e": "ACCOUNT_UPDATE"})
            return json.dumps(
                {
                    "e": "ORDER_TRADE_UPDATE",
                    "o": {"c": "cid-reconnect", "X": "FILLED", "r": "NONE"},
                }
            )

        def close(self) -> None:
            return None

    provider = Provider()
    sleeps: list[float] = []
    reports: list[ExecutionReport] = []
    factory_calls = {"n": 0}
    client: BinanceUserStreamClient | None = None

    def ws_factory(_: str):
        factory_calls["n"] += 1
        assert client is not None
        return ReconnectAwareWS(client=client, first=factory_calls["n"] == 1)

    def on_report(report: ExecutionReport) -> None:
        reports.append(report)
        assert client is not None
        client.stop()

    client = BinanceUserStreamClient(
        listen_key_provider=provider,
        on_execution_report=on_report,
        ws_factory=ws_factory,
        reconnect_initial_sec=0.5,
        reconnect_max_sec=2.0,
        sleep_fn=sleeps.append,
    )

    client.run_forever()

    assert factory_calls["n"] == 2
    assert provider.calls == 2
    assert provider.clear_calls == 0
    assert sleeps == []
    assert [r.client_order_id for r in reports] == ["cid-reconnect"]
