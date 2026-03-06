from __future__ import annotations

import hashlib
import hmac
import json
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Callable, Protocol


class HttpTransport(Protocol):
    def post(self, *, url: str, headers: dict[str, str], body: bytes) -> dict: ...

    def put(self, *, url: str, headers: dict[str, str], body: bytes) -> dict: ...


@dataclass(frozen=True)
class BinanceAuthConfig:
    api_key: str
    api_secret: str
    base_url: str = "https://fapi.binance.com"
    recv_window_ms: int = 5000


class UrlLibHttpTransport:
    def _request(self, *, method: str, url: str, headers: dict[str, str], body: bytes) -> dict:
        req = urllib.request.Request(url=url, data=body, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=10) as resp:  # nosec B310
            return json.loads(resp.read().decode("utf-8"))

    def post(self, *, url: str, headers: dict[str, str], body: bytes) -> dict:
        return self._request(method="POST", url=url, headers=headers, body=body)

    def put(self, *, url: str, headers: dict[str, str], body: bytes) -> dict:
        return self._request(method="PUT", url=url, headers=headers, body=body)


class BinanceFuturesListenKeyProvider:
    def __init__(
        self,
        config: BinanceAuthConfig,
        *,
        transport: HttpTransport | None = None,
        timestamp_ms_fn: Callable[[], int] | None = None,
    ) -> None:
        self._config = config
        self._transport = transport or UrlLibHttpTransport()
        self._timestamp_ms_fn = timestamp_ms_fn or (lambda: int(time.time() * 1000))
        self._listen_key: str | None = None

    def get_listen_key(self) -> str:
        if self._listen_key is not None:
            return self._listen_key

        body = self._signed_body()
        payload = self._transport.post(
            url=f"{self._config.base_url}/fapi/v1/listenKey",
            headers=self._headers(),
            body=body,
        )
        key = str(payload.get("listenKey", ""))
        if not key:
            raise ValueError("missing listenKey in create response")
        self._listen_key = key
        return key

    def keepalive(self) -> str:
        key = self.get_listen_key()
        body = self._signed_body(extra={"listenKey": key})
        payload = self._transport.put(
            url=f"{self._config.base_url}/fapi/v1/listenKey",
            headers=self._headers(),
            body=body,
        )
        returned = str(payload.get("listenKey", key))
        self._listen_key = returned
        return returned

    def _headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/x-www-form-urlencoded",
            "X-MBX-APIKEY": self._config.api_key,
        }

    def _signed_body(self, *, extra: dict[str, str] | None = None) -> bytes:
        params = {
            "recvWindow": str(self._config.recv_window_ms),
            "timestamp": str(self._timestamp_ms_fn()),
        }
        if extra:
            params.update(extra)
        query = urllib.parse.urlencode(params)
        signature = hmac.new(
            self._config.api_secret.encode("utf-8"),
            query.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return f"{query}&signature={signature}".encode("utf-8")
