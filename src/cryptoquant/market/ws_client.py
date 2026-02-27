from __future__ import annotations

import contextlib
import json
import time
from datetime import datetime, timezone
from typing import Callable, Protocol

from cryptoquant.events.market import MarketEvent


class WebSocketLike(Protocol):
    def recv(self) -> str: ...

    def close(self) -> None: ...


class BinanceKlineWSClient:
    """Minimal Binance kline websocket client with auto reconnect.

    Scope intentionally small for MVP-1:
    - subscribe via combined stream URL
    - emit only closed 1m kline events
    - reconnect with bounded exponential backoff
    """

    def __init__(
        self,
        *,
        symbols: list[str],
        on_event: Callable[[MarketEvent], None],
        ws_factory: Callable[[str], WebSocketLike] | None = None,
        base_url: str = "wss://stream.binance.com:9443/stream?streams=",
        reconnect_initial_sec: float = 1.0,
        reconnect_max_sec: float = 8.0,
        sleep_fn: Callable[[float], None] = time.sleep,
    ) -> None:
        if not symbols:
            raise ValueError("symbols cannot be empty")

        self._symbols = [s.lower() for s in symbols]
        self._on_event = on_event
        self._base_url = base_url
        self._reconnect_initial_sec = reconnect_initial_sec
        self._reconnect_max_sec = reconnect_max_sec
        self._sleep_fn = sleep_fn
        self._ws_factory = ws_factory or _default_ws_factory
        self._stopped = False

    @property
    def stream_url(self) -> str:
        streams = "/".join(f"{s}@kline_1m" for s in self._symbols)
        return f"{self._base_url}{streams}"

    def stop(self) -> None:
        self._stopped = True

    def run_forever(self) -> None:
        backoff = self._reconnect_initial_sec

        while not self._stopped:
            ws: WebSocketLike | None = None
            try:
                ws = self._ws_factory(self.stream_url)
                backoff = self._reconnect_initial_sec
                while not self._stopped:
                    raw = ws.recv()
                    event = self._parse_market_event(raw)
                    if event is not None:
                        self._on_event(event)
            except KeyboardInterrupt:
                raise
            except Exception:
                if self._stopped:
                    break
                self._sleep_fn(backoff)
                backoff = min(backoff * 2, self._reconnect_max_sec)
            finally:
                if ws is not None:
                    with contextlib.suppress(Exception):
                        ws.close()

    @staticmethod
    def _parse_market_event(raw: str) -> MarketEvent | None:
        payload = json.loads(raw)
        data = payload.get("data", payload)
        kline = data.get("k")
        if not isinstance(kline, dict):
            return None

        if kline.get("i") != "1m" or not bool(kline.get("x")):
            return None

        symbol = str(kline["s"])
        close = float(kline["c"])
        close_ts = datetime.fromtimestamp(int(kline["T"]) / 1000, tz=timezone.utc)

        return MarketEvent(
            symbol=symbol,
            timeframe="1m",
            close=close,
            ts=close_ts,
            source="binance_ws",
        )


def _default_ws_factory(url: str) -> WebSocketLike:
    try:
        import websocket  # type: ignore[import-not-found]
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(
            "websocket-client is required for live WS usage; install websocket-client"
        ) from exc

    return websocket.create_connection(url, timeout=30)
