from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from queue import Empty, Full, Queue
from threading import Event, RLock, Thread
from time import perf_counter_ns, sleep
from typing import Any, Callable, DefaultDict, Iterable, TypeVar


TEvent = TypeVar("TEvent")
Handler = Callable[[Any], None]


@dataclass(frozen=True)
class Subscription:
    event_type: type
    handler: Handler


@dataclass(frozen=True)
class DispatchStats:
    published: int
    dropped: int
    dispatched: int
    queue_size: int
    queue_capacity: int
    queue_high_watermark: int
    backpressure_count: int
    avg_dispatch_latency_us: float
    batches: int
    handler_errors: int


class EventBus:
    """A minimal in-process pub/sub event bus.

    Design goals for MVP-1:
    - explicit subscribe/unsubscribe
    - deterministic handler invocation order (subscribe order)
    - thread-safety for future async/WS ingestion paths
    """

    def __init__(self) -> None:
        self._lock = RLock()
        self._handlers: DefaultDict[type, list[Handler]] = defaultdict(list)

    def subscribe(self, event_type: type[TEvent], handler: Callable[[TEvent], None]) -> Subscription:
        with self._lock:
            self._handlers[event_type].append(handler)  # type: ignore[arg-type]
        return Subscription(event_type=event_type, handler=handler)  # type: ignore[arg-type]

    def unsubscribe(self, sub: Subscription) -> None:
        with self._lock:
            handlers = self._handlers.get(sub.event_type)
            if not handlers:
                return
            try:
                handlers.remove(sub.handler)
            except ValueError:
                return

    def publish(self, event: Any) -> None:
        event_type = type(event)
        with self._lock:
            handlers: Iterable[Handler] = tuple(self._handlers.get(event_type, ()))
        for handler in handlers:
            handler(event)


class LowLatencyEventBus(EventBus):
    """Queue-backed event bus optimized for high publish throughput.

    Uses bounded queue + worker micro-batching to avoid unbounded memory growth.
    """

    def __init__(
        self,
        *,
        queue_size: int = 100_000,
        worker_count: int = 2,
        batch_size: int = 256,
        drop_on_full: bool = True,
    ) -> None:
        super().__init__()
        if queue_size <= 0:
            raise ValueError("queue_size must be > 0")
        if worker_count <= 0:
            raise ValueError("worker_count must be > 0")
        if batch_size <= 0:
            raise ValueError("batch_size must be > 0")

        self._queue: Queue[tuple[int, Any]] = Queue(maxsize=queue_size)
        self._worker_count = worker_count
        self._batch_size = batch_size
        self._drop_on_full = drop_on_full
        self._stop = Event()
        self._workers: list[Thread] = []

        self._metrics_lock = RLock()
        self._published = 0
        self._dropped = 0
        self._dispatched = 0
        self._dispatch_latency_ns_sum = 0
        self._batches = 0
        self._handler_errors = 0
        self._queue_high_watermark = 0
        self._backpressure_count = 0

    def start(self) -> None:
        if self._workers:
            return
        self._stop.clear()
        for idx in range(self._worker_count):
            t = Thread(target=self._worker_loop, name=f"cq-eventbus-{idx}", daemon=True)
            t.start()
            self._workers.append(t)

    def stop(self, timeout_sec: float = 2.0) -> None:
        self.flush(timeout_sec=timeout_sec)
        self._stop.set()
        for t in self._workers:
            t.join(timeout=timeout_sec)
        self._workers.clear()

    def flush(self, timeout_sec: float = 2.0) -> bool:
        deadline = perf_counter_ns() + int(timeout_sec * 1_000_000_000)
        while self._queue.unfinished_tasks > 0:
            if perf_counter_ns() >= deadline:
                return False
            sleep(0.001)
        return True

    def publish(self, event: Any) -> None:
        self.publish_many((event,))

    def publish_many(self, events: Iterable[Any]) -> None:
        for event in events:
            enqueue_ts = perf_counter_ns()
            try:
                if self._drop_on_full:
                    self._queue.put_nowait((enqueue_ts, event))
                else:
                    if self._queue.full():
                        with self._metrics_lock:
                            self._backpressure_count += 1
                    self._queue.put((enqueue_ts, event))
                with self._metrics_lock:
                    self._published += 1
                    self._queue_high_watermark = max(self._queue_high_watermark, self._queue.qsize())
            except Full:
                with self._metrics_lock:
                    self._dropped += 1
                    self._backpressure_count += 1

    def stats(self) -> DispatchStats:
        with self._metrics_lock:
            avg_latency_us = (
                (self._dispatch_latency_ns_sum / self._dispatched) / 1_000 if self._dispatched else 0.0
            )
            return DispatchStats(
                published=self._published,
                dropped=self._dropped,
                dispatched=self._dispatched,
                queue_size=self._queue.qsize(),
                queue_capacity=self._queue.maxsize,
                queue_high_watermark=self._queue_high_watermark,
                backpressure_count=self._backpressure_count,
                avg_dispatch_latency_us=avg_latency_us,
                batches=self._batches,
                handler_errors=self._handler_errors,
            )

    def _worker_loop(self) -> None:
        while not self._stop.is_set() or not self._queue.empty():
            try:
                first = self._queue.get(timeout=0.05)
            except Empty:
                continue

            batch = [first]
            for _ in range(self._batch_size - 1):
                try:
                    batch.append(self._queue.get_nowait())
                except Empty:
                    break

            batch_latency_ns = 0
            dispatched = 0
            errors = 0

            for enqueue_ts, event in batch:
                try:
                    super().publish(event)
                except Exception:
                    errors += 1
                finally:
                    dispatched += 1
                    batch_latency_ns += perf_counter_ns() - enqueue_ts
                    self._queue.task_done()

            with self._metrics_lock:
                self._batches += 1
                self._dispatched += dispatched
                self._handler_errors += errors
                self._dispatch_latency_ns_sum += batch_latency_ns
