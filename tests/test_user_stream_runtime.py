from __future__ import annotations

import threading

from cryptoquant.execution import BinanceUserStreamService, KeepaliveRunner


class FakeProvider:
    def __init__(self) -> None:
        self.calls = 0

    def keepalive(self) -> str:
        self.calls += 1
        return "lk"


class FlakyProvider:
    def __init__(self, fail_times: int) -> None:
        self.calls = 0
        self._fail_times = fail_times

    def keepalive(self) -> str:
        self.calls += 1
        if self.calls <= self._fail_times:
            raise RuntimeError("boom")
        return "lk"


class FakeClient:
    def __init__(self) -> None:
        self.calls = 0
        self.stop_calls = 0

    def run_forever(self) -> None:
        self.calls += 1

    def stop(self) -> None:
        self.stop_calls += 1


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
    stats = runner.stats()
    assert stats.success_count == 1
    assert stats.failure_count == 0
    assert stats.last_error is None


def test_keepalive_runner_run_forever_can_stop_via_event() -> None:
    p = FakeProvider()

    def fake_sleep(_: float) -> None:
        stop.set()

    stop = threading.Event()
    runner = KeepaliveRunner(provider=p, interval_sec=0.01, sleep_fn=fake_sleep)
    runner.run_forever(stop)

    assert p.calls == 1


def test_keepalive_runner_retries_with_backoff_on_failure() -> None:
    p = FlakyProvider(fail_times=2)
    sleeps: list[float] = []

    def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)
        if len(sleeps) >= 3:
            stop.set()

    stop = threading.Event()
    runner = KeepaliveRunner(
        provider=p,
        interval_sec=10.0,
        failure_backoff_initial_sec=0.5,
        failure_backoff_max_sec=2.0,
        sleep_fn=fake_sleep,
    )
    runner.run_forever(stop)

    assert p.calls == 3
    assert sleeps == [0.5, 1.0, 10.0]
    stats = runner.stats()
    assert stats.success_count == 1
    assert stats.failure_count == 2
    assert stats.last_error is None


def test_keepalive_runner_records_last_error_when_only_failures() -> None:
    p = FlakyProvider(fail_times=10)
    sleeps: list[float] = []

    def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)
        if len(sleeps) >= 2:
            stop.set()

    stop = threading.Event()
    runner = KeepaliveRunner(
        provider=p,
        interval_sec=10.0,
        failure_backoff_initial_sec=0.5,
        failure_backoff_max_sec=2.0,
        sleep_fn=fake_sleep,
    )
    runner.run_forever(stop)

    stats = runner.stats()
    assert stats.success_count == 0
    assert stats.failure_count == 2
    assert stats.last_error == "boom"


def test_keepalive_runner_invokes_failure_callback() -> None:
    p = FlakyProvider(fail_times=1)
    callback_stats = []

    def on_failure(stats) -> None:  # noqa: ANN001
        callback_stats.append(stats)

    def fake_sleep(_: float) -> None:
        stop.set()

    stop = threading.Event()
    runner = KeepaliveRunner(
        provider=p,
        interval_sec=10.0,
        failure_backoff_initial_sec=0.5,
        failure_backoff_max_sec=2.0,
        sleep_fn=fake_sleep,
        on_failure=on_failure,
    )
    runner.run_forever(stop)

    assert len(callback_stats) == 1
    assert callback_stats[0].failure_count == 1
    assert callback_stats[0].last_error == "boom"


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


def test_user_stream_service_stop_calls_client_stop() -> None:
    p = FakeProvider()
    keepalive = KeepaliveRunner(provider=p, interval_sec=999999)
    client = FakeClient()
    processor = FakeProcessor()

    svc = BinanceUserStreamService(
        client=client,
        processor=processor,
        keepalive_runner=keepalive,
    )

    svc.stop()
    assert client.stop_calls == 1
