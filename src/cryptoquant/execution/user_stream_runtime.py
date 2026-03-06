from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Callable, Protocol

from .user_stream import UserStreamProcessor
from .user_stream_binance import BinanceUserStreamClient


class KeepaliveProvider(Protocol):
    def keepalive(self) -> str: ...


@dataclass
class KeepaliveRunner:
    provider: KeepaliveProvider
    interval_sec: float = 30 * 60
    failure_backoff_initial_sec: float = 1.0
    failure_backoff_max_sec: float = 30.0
    sleep_fn: Callable[[float], None] = time.sleep

    def run_once(self) -> str:
        return self.provider.keepalive()

    def run_forever(self, stop_event: threading.Event) -> None:
        backoff = self.failure_backoff_initial_sec
        while not stop_event.is_set():
            try:
                self.provider.keepalive()
                backoff = self.failure_backoff_initial_sec
                self.sleep_fn(self.interval_sec)
            except Exception:
                if stop_event.is_set():
                    break
                self.sleep_fn(backoff)
                backoff = min(backoff * 2, self.failure_backoff_max_sec)


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

    def run_forever(self) -> None:
        stop_event = threading.Event()
        worker = self._thread_factory(
            target=self._keepalive_runner.run_forever,
            kwargs={"stop_event": stop_event},
            daemon=True,
        )
        worker.start()
        try:
            self._client.run_forever()
        finally:
            stop_event.set()

    @staticmethod
    def wire_callback(processor: UserStreamProcessor):
        return processor.on_execution_report
