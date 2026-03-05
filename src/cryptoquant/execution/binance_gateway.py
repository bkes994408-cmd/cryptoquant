from __future__ import annotations

import hashlib
import hmac
import json
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Protocol

from .live import LiveOrderAck


class HttpTransport(Protocol):
    def post(self, *, url: str, headers: dict[str, str], body: bytes) -> dict: ...


@dataclass(frozen=True)
class BinanceGatewayConfig:
    api_key: str
    api_secret: str
    base_url: str = "https://fapi.binance.com"
    recv_window_ms: int = 5000


def _validate_https_url(url: str) -> None:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError("url must be absolute https URL")


class UrlLibHttpTransport:
    def post(self, *, url: str, headers: dict[str, str], body: bytes) -> dict:
        _validate_https_url(url)
        req = urllib.request.Request(url=url, data=body, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=10) as resp:  # nosec B310
            return json.loads(resp.read().decode("utf-8"))


class BinanceFuturesOrderGateway:
    """Binance USDⓈ-M futures REST gateway for market orders."""

    def __init__(
        self,
        config: BinanceGatewayConfig,
        *,
        transport: HttpTransport | None = None,
        timestamp_ms_fn: Callable[[], int] | None = None,
    ) -> None:
        _validate_https_url(config.base_url)
        self._config = config
        self._transport = transport or UrlLibHttpTransport()
        self._timestamp_ms_fn = timestamp_ms_fn or (lambda: int(time.time() * 1000))

    def place_market_order(self, *, symbol: str, qty: float, client_order_id: str) -> LiveOrderAck:
        if qty == 0:
            raise ValueError("qty must be non-zero")

        side = "BUY" if qty > 0 else "SELL"
        params = {
            "symbol": symbol,
            "side": side,
            "type": "MARKET",
            "quantity": str(abs(qty)),
            "newClientOrderId": client_order_id,
            "recvWindow": str(self._config.recv_window_ms),
            "timestamp": str(self._timestamp_ms_fn()),
        }
        query = urllib.parse.urlencode(params)
        signature = hmac.new(
            self._config.api_secret.encode("utf-8"),
            query.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        body = f"{query}&signature={signature}".encode("utf-8")
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "X-MBX-APIKEY": self._config.api_key,
        }
        url = f"{self._config.base_url}/fapi/v1/order"

        payload = self._transport.post(url=url, headers=headers, body=body)

        exchange_order_id = str(payload.get("orderId", ""))
        if not exchange_order_id:
            raise ValueError("missing orderId from Binance response")

        ts_ms = int(payload.get("updateTime") or payload.get("transactTime") or self._timestamp_ms_fn())
        accepted_at = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)

        return LiveOrderAck(
            client_order_id=client_order_id,
            exchange_order_id=exchange_order_id,
            accepted_at=accepted_at,
        )
