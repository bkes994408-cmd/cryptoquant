from __future__ import annotations

import contextlib
import json
import time
from typing import Callable, Protocol

from .user_stream import ExecutionReport


class WebSocketLike(Protocol):
    def recv(self) -> str: ...

    def close(self) -> None: ...


class ListenKeyProvider(Protocol):
    def get_listen_key(self) -> str: ...

    def clear_cached_listen_key(self) -> None: ...


class BinanceUserStreamClient:
    """Minimal Binance user-stream client with reconnect support."""

    def __init__(
        self,
        *,
        listen_key_provider: ListenKeyProvider,
        on_execution_report: Callable[[ExecutionReport], None],
        ws_factory: Callable[[str], WebSocketLike] | None = None,
        base_url: str = "wss://fstream.binance.com/ws/",
        reconnect_initial_sec: float = 1.0,
        reconnect_max_sec: float = 8.0,
        sleep_fn: Callable[[float], None] = time.sleep,
    ) -> None:
        self._listen_key_provider = listen_key_provider
        self._on_execution_report = on_execution_report
        self._ws_factory = ws_factory or _default_ws_factory
        self._base_url = base_url
        self._reconnect_initial_sec = reconnect_initial_sec
        self._reconnect_max_sec = reconnect_max_sec
        self._sleep_fn = sleep_fn
        self._stopped = False
        self._reconnect_requested = False

    def stop(self) -> None:
        self._stopped = True

    def reconnect(self) -> None:
        """Request WS reconnect without stopping the service."""
        self._reconnect_requested = True

    def run_forever(self) -> None:
        backoff = self._reconnect_initial_sec
        while not self._stopped:
            ws: WebSocketLike | None = None
            try:
                listen_key = self._listen_key_provider.get_listen_key()
                ws = self._ws_factory(f"{self._base_url}{listen_key}")
                backoff = self._reconnect_initial_sec
                self._reconnect_requested = False
                while not self._stopped:
                    if self._reconnect_requested:
                        raise RuntimeError("reconnect requested")
                    report = parse_binance_execution_report(ws.recv())
                    if report is not None:
                        self._on_execution_report(report)
            except KeyboardInterrupt:
                raise
            except Exception:
                if self._stopped:
                    break
                if self._reconnect_requested:
                    self._reconnect_requested = False
                    continue
                self._listen_key_provider.clear_cached_listen_key()
                self._sleep_fn(backoff)
                backoff = min(backoff * 2, self._reconnect_max_sec)
            finally:
                if ws is not None:
                    with contextlib.suppress(Exception):
                        ws.close()


def parse_binance_execution_report(raw: str) -> ExecutionReport | None:
    payload = json.loads(raw)
    data = payload.get("data", payload)

    if data.get("e") != "ORDER_TRADE_UPDATE":
        return None

    order = data.get("o", {})
    client_order_id = order.get("c")
    status = order.get("X")
    if not client_order_id or not status:
        return None

    reject_reason = order.get("r")
    if reject_reason in {"NONE", ""}:
        reject_reason = None

    return ExecutionReport(
        client_order_id=str(client_order_id),
        order_status=str(status),
        reject_reason=None if reject_reason is None else str(reject_reason),
    )


def _default_ws_factory(url: str) -> WebSocketLike:
    try:
        import websocket  # type: ignore[import-not-found]
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("websocket-client is required for live WS usage; install websocket-client") from exc

    return websocket.create_connection(url, timeout=30)
