from __future__ import annotations

import json
from datetime import datetime, timezone

from cryptoquant.events.bus import EventBus
from cryptoquant.events.market import MarketEvent
from cryptoquant.market.ws_client import BinanceKlineWSClient


def test_parse_message_returns_event_only_for_closed_kline() -> None:
    client = BinanceKlineWSClient(bus=EventBus(), symbol="BTCUSDT")

    closed = {
        "e": "kline",
        "k": {
            "s": "BTCUSDT",
            "i": "1m",
            "c": "68000.12",
            "T": 1700000000000,
            "x": True,
        },
    }
    open_ = {
        "e": "kline",
        "k": {
            "s": "BTCUSDT",
            "i": "1m",
            "c": "68000.13",
            "T": 1700000000000,
            "x": False,
        },
    }

    event = client.parse_message(json.dumps(closed))
    assert event == MarketEvent(
        symbol="BTCUSDT",
        timeframe="1m",
        close=68000.12,
        ts=datetime.fromtimestamp(1700000000000 / 1000, tz=timezone.utc),
        source="binance",
    )
    assert client.parse_message(json.dumps(open_)) is None


def test_backoff_is_exponential_and_capped() -> None:
    client = BinanceKlineWSClient(
        bus=EventBus(),
        symbol="BTCUSDT",
        backoff_base_seconds=1.0,
        backoff_max_seconds=4.0,
    )

    assert client._compute_backoff(0) == 1.0
    assert client._compute_backoff(1) == 2.0
    assert client._compute_backoff(2) == 4.0
    assert client._compute_backoff(3) == 4.0
