from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any

import websockets
from websockets.asyncio.client import ClientConnection

from cryptoquant.events.bus import EventBus
from cryptoquant.events.market import MarketEvent

logger = logging.getLogger(__name__)


class BinanceKlineWSClient:
    """Binance market websocket client for 1m kline close events.

    - subscribes to `<symbol>@kline_1m`
    - only publishes events when the candle is closed (`k.x == True`)
    - reconnects automatically with exponential backoff (1s, 2s, 4s...)
    """

    def __init__(
        self,
        bus: EventBus,
        symbol: str,
        *,
        endpoint: str = "wss://stream.binance.com:9443/ws",
        timeframe: str = "1m",
        backoff_base_seconds: float = 1.0,
        backoff_max_seconds: float = 32.0,
    ) -> None:
        self._bus = bus
        self._symbol = symbol.upper()
        self._stream_symbol = symbol.lower()
        self._endpoint = endpoint
        self._timeframe = timeframe
        self._backoff_base_seconds = backoff_base_seconds
        self._backoff_max_seconds = backoff_max_seconds
        self._stop_event = asyncio.Event()

    @property
    def stream_url(self) -> str:
        return f"{self._endpoint}/{self._stream_symbol}@kline_{self._timeframe}"

    async def run_forever(self) -> None:
        attempt = 0
        while not self._stop_event.is_set():
            try:
                async with websockets.connect(self.stream_url) as ws:
                    logger.info("Market WS connected: %s", self.stream_url)
                    attempt = 0
                    await self._consume(ws)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # pragma: no cover - integration level
                delay = self._compute_backoff(attempt)
                logger.warning(
                    "Market WS disconnected, retry in %.1fs (attempt=%d): %s",
                    delay,
                    attempt + 1,
                    exc,
                )
                attempt += 1
                await asyncio.sleep(delay)

    def stop(self) -> None:
        self._stop_event.set()

    async def _consume(self, ws: ClientConnection) -> None:
        async for raw in ws:
            event = self.parse_message(raw)
            if event is None:
                continue
            self._bus.publish(event)
            if self._stop_event.is_set():
                break

    def parse_message(self, raw: str) -> MarketEvent | None:
        data = json.loads(raw)
        kline = data.get("k")
        if not isinstance(kline, dict):
            return None

        if not kline.get("x", False):  # candle closed?
            return None

        symbol = str(kline["s"])
        timeframe = str(kline["i"])
        close = float(kline["c"])
        close_ts_ms = int(kline["T"])
        ts = datetime.fromtimestamp(close_ts_ms / 1000, tz=timezone.utc)

        return MarketEvent(
            symbol=symbol,
            timeframe=timeframe,  # type: ignore[arg-type]
            close=close,
            ts=ts,
            source="binance",
        )

    def _compute_backoff(self, attempt: int) -> float:
        return min(self._backoff_base_seconds * (2**attempt), self._backoff_max_seconds)
