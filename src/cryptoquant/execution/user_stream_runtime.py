from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Callable, Protocol, runtime_checkable

from .user_stream import UserStreamProcessor
from .user_stream_binance import BinanceUserStreamClient


class KeepaliveProvider(Protocol):
    def keepalive(self) -> str: ...


@runtime_checkable
class ListenKeyResettableProvider(Protocol):
    def clear_cached_listen_key(self) -> None: ...

    def get_listen_key(self) -> str: ...


@dataclass(frozen=True)
class KeepaliveStats:
    success_count: int
    failure_count: int
    last_error: str | None


@dataclass
class KeepaliveRunner:
    provider: KeepaliveProvider
    interval_sec: float = 30 * 60
    failure_backoff_initial_sec: float = 1.0
    failure_backoff_max_sec: float = 30.0
    max_consecutive_failures_before_rebuild: int = 2
    sleep_fn: Callable[[float], None] = time.sleep
    on_failure: Callable[[KeepaliveStats], None] | None = None
    on_rebuild: Callable[[str, KeepaliveStats], None] | None = None

    def __post_init__(self) -> None:
        self._success_count = 0
        self._failure_count = 0
        self._last_error: str | None = None
        self._consecutive_failures = 0

    def stats(self) -> KeepaliveStats:
        return KeepaliveStats(
            success_count=self._success_count,
            failure_count=self._failure_count,
            last_error=self._last_error,
        )

    def run_once(self) -> str:
        key = self.provider.keepalive()
        self._success_count += 1
        self._consecutive_failures = 0
        self._last_error = None
        return key

    def run_forever(self, stop_event: threading.Event) -> None:
        backoff = self.failure_backoff_initial_sec
        while not stop_event.is_set():
            try:
                self.provider.keepalive()
                self._success_count += 1
                self._consecutive_failures = 0
                self._last_error = None
                backoff = self.failure_backoff_initial_sec
                self.sleep_fn(self.interval_sec)
            except Exception as exc:
                self._failure_count += 1
                self._consecutive_failures += 1
                self._last_error = str(exc)
                stats = self.stats()
                if self.on_failure is not None:
                    self.on_failure(stats)
                self._maybe_rebuild_after_failure(stats=stats)
                if stop_event.is_set():
                    break
                self.sleep_fn(backoff)
                backoff = min(backoff * 2, self.failure_backoff_max_sec)

    def _maybe_rebuild_after_failure(self, *, stats: KeepaliveStats) -> None:
        if self._consecutive_failures < self.max_consecutive_failures_before_rebuild:
            return
        provider = self.provider
        if not isinstance(provider, ListenKeyResettableProvider):
            self._consecutive_failures = 0
            return

        provider.clear_cached_listen_key()
        new_listen_key = provider.get_listen_key()
        self._consecutive_failures = 0
        if self.on_rebuild is not None:
            self.on_rebuild(new_listen_key, stats)


class BinanceUserStreamService:
    """Compose WS client + keepalive loop + processor wiring."""

    def __init__(
        self,
        *,
        client: BinanceUserStreamClient,
        processor: UserStreamProcessor,
        keepalive_runner: KeepaliveRunner,
        thread_factory: Callable[..., threading.Thread] = threading.Thread,
    ) -> None:
        self._client = client
        self._processor = processor
        self._keepalive_runner = keepalive_runner
        self._thread_factory = thread_factory
        self._stop_event = threading.Event()
        if self._keepalive_runner.on_rebuild is None:
            self._keepalive_runner.on_rebuild = self._on_listen_key_rebuilt

    def stop(self) -> None:
        self._stop_event.set()
        self._client.stop()

    def run_forever(self) -> None:
        worker = self._thread_factory(
            target=self._keepalive_runner.run_forever,
            kwargs={"stop_event": self._stop_event},
            daemon=True,
        )
        worker.start()
        try:
            self._client.run_forever()
        finally:
            self._stop_event.set()

    def _on_listen_key_rebuilt(self, _new_listen_key: str, _stats: KeepaliveStats) -> None:
        self._client.reconnect()

    @staticmethod
    def wire_callback(processor: UserStreamProcessor):
        return processor.on_execution_report
