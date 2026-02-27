from __future__ import annotations

import json
from datetime import datetime, timezone

from cryptoquant.events.market import MarketEvent
from cryptoquant.market import BinanceKlineWSClient


def _kline_message(*, close: str, closed: bool = True, ts_ms: int = 1700000000000) -> str:
    return json.dumps(
        {
            "stream": "btcusdt@kline_1m",
            "data": {
                "k": {
                    "s": "BTCUSDT",
                    "i": "1m",
                    "x": closed,
                    "c": close,
                    "T": ts_ms,
                }
            },
        }
    )


def test_parse_ignores_unclosed_kline_and_emits_closed_event() -> None:
    e1 = BinanceKlineWSClient._parse_market_event(_kline_message(close="100", closed=False))
    assert e1 is None

    e2 = BinanceKlineWSClient._parse_market_event(_kline_message(close="101", closed=True))
    assert isinstance(e2, MarketEvent)
    assert e2.symbol == "BTCUSDT"
    assert e2.timeframe == "1m"
    assert e2.close == 101.0
    assert e2.ts == datetime.fromtimestamp(1700000000000 / 1000, tz=timezone.utc)


def test_run_forever_reconnects_and_continues_stream() -> None:
    class FakeWS:
        def __init__(self, messages: list[str]) -> None:
            self._messages = iter(messages)

        def recv(self) -> str:
            try:
                return next(self._messages)
            except StopIteration:
                raise ConnectionError("socket dropped")

        def close(self) -> None:
            return None

    attempts = {"n": 0}
    sleep_calls: list[float] = []
    captured: list[MarketEvent] = []

    def ws_factory(_: str) -> FakeWS:
        attempts["n"] += 1
        if attempts["n"] == 1:
            return FakeWS([_kline_message(close="100")])
        return FakeWS([_kline_message(close="101")])

    first_seen = {"done": False}

    def on_event(e: MarketEvent) -> None:
        captured.append(e)
        if first_seen["done"]:
            client.stop()
        first_seen["done"] = True

    client = BinanceKlineWSClient(
        symbols=["BTCUSDT"],
        on_event=on_event,
        ws_factory=ws_factory,
        sleep_fn=lambda sec: sleep_calls.append(sec),
    )

    client.run_forever()

    assert len(captured) == 2
    assert [e.close for e in captured] == [100.0, 101.0]
    assert attempts["n"] >= 2
    assert sleep_calls == [1.0]
