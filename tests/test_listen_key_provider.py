from __future__ import annotations

import urllib.parse

import pytest

from cryptoquant.execution import BinanceAuthConfig, BinanceFuturesListenKeyProvider


class FakeTransport:
    def __init__(self, post_payload: dict, put_payload: dict) -> None:
        self.post_payload = post_payload
        self.put_payload = put_payload
        self.post_calls = 0
        self.put_calls = 0
        self.last_post_body = b""
        self.last_put_body = b""

    def post(self, *, url: str, headers: dict[str, str], body: bytes) -> dict:
        self.post_calls += 1
        self.last_post_body = body
        return self.post_payload

    def put(self, *, url: str, headers: dict[str, str], body: bytes) -> dict:
        self.put_calls += 1
        self.last_put_body = body
        return self.put_payload


def test_listen_key_provider_creates_and_caches_key() -> None:
    t = FakeTransport(post_payload={"listenKey": "lk-1"}, put_payload={"listenKey": "lk-1"})
    p = BinanceFuturesListenKeyProvider(
        BinanceAuthConfig(api_key="k", api_secret="s"), transport=t, timestamp_ms_fn=lambda: 111
    )

    first = p.get_listen_key()
    second = p.get_listen_key()

    assert first == "lk-1"
    assert second == "lk-1"
    assert t.post_calls == 1

    parsed = urllib.parse.parse_qs(t.last_post_body.decode("utf-8"))
    assert parsed["timestamp"] == ["111"]
    assert "signature" in parsed


def test_listen_key_provider_keepalive_uses_put() -> None:
    t = FakeTransport(post_payload={"listenKey": "lk-1"}, put_payload={"listenKey": "lk-1"})
    p = BinanceFuturesListenKeyProvider(
        BinanceAuthConfig(api_key="k", api_secret="s"), transport=t, timestamp_ms_fn=lambda: 222
    )

    key = p.keepalive()

    assert key == "lk-1"
    assert t.post_calls == 1
    assert t.put_calls == 1
    parsed = urllib.parse.parse_qs(t.last_put_body.decode("utf-8"))
    assert parsed["listenKey"] == ["lk-1"]
    assert parsed["timestamp"] == ["222"]


def test_listen_key_provider_raises_when_missing_key() -> None:
    t = FakeTransport(post_payload={}, put_payload={})
    p = BinanceFuturesListenKeyProvider(BinanceAuthConfig(api_key="k", api_secret="s"), transport=t)

    with pytest.raises(ValueError, match="missing listenKey"):
        p.get_listen_key()


def test_listen_key_provider_clear_cache_forces_recreate() -> None:
    t = FakeTransport(post_payload={"listenKey": "lk-1"}, put_payload={"listenKey": "lk-1"})
    p = BinanceFuturesListenKeyProvider(
        BinanceAuthConfig(api_key="k", api_secret="s"), transport=t, timestamp_ms_fn=lambda: 111
    )

    assert p.get_listen_key() == "lk-1"
    p.clear_cached_listen_key()
    assert p.get_listen_key() == "lk-1"
    assert t.post_calls == 2
