from __future__ import annotations

import threading

from cryptoquant.execution import BinanceUserStreamService, KeepaliveRunner


class FakeProvider:
    def __init__(self) -> None:
        self.calls = 0

    def keepalive(self) -> str:
        self.calls += 1
        return "lk"


class FakeClient:
    def __init__(self) -> None:
        self.calls = 0

    def run_forever(self) -> None:
        self.calls += 1


class FakeProcessor:
    def __init__(self) -> None:
        self.events = []

    def on_execution_report(self, event) -> None:
        self.events.append(event)


def test_keepalive_runner_run_once() -> None:
    p = FakeProvider()
    runner = KeepaliveRunner(provider=p)
    key = runner.run_once()

    assert key == "lk"
    assert p.calls == 1


def test_keepalive_runner_run_forever_can_stop_via_event() -> None:
    p = FakeProvider()

    def fake_sleep(_: float) -> None:
        stop.set()

    stop = threading.Event()
    runner = KeepaliveRunner(provider=p, interval_sec=0.01, sleep_fn=fake_sleep)
    runner.run_forever(stop)

    assert p.calls == 1


def test_user_stream_service_starts_keepalive_and_runs_client_once() -> None:
    p = FakeProvider()
    keepalive = KeepaliveRunner(provider=p, interval_sec=999999)
    client = FakeClient()
    processor = FakeProcessor()

    class InlineThread:
        def __init__(self, *, target, kwargs, daemon) -> None:
            _ = daemon
            self._target = target
            self._kwargs = kwargs

        def start(self) -> None:
            stop_event = self._kwargs["stop_event"]
            stop_event.set()
            self._target(stop_event=stop_event)

    svc = BinanceUserStreamService(
        client=client,
        processor=processor,
        keepalive_runner=keepalive,
        thread_factory=InlineThread,
    )
    svc.run_forever()

    assert client.calls == 1
    assert p.calls == 0


def test_user_stream_service_wire_callback_passes_through() -> None:
    processor = FakeProcessor()
    callback = BinanceUserStreamService.wire_callback(processor)
    callback("evt")
    assert processor.events == ["evt"]
