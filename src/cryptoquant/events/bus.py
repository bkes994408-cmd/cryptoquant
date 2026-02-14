from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from threading import RLock
from typing import Any, Callable, DefaultDict, Generic, Iterable, TypeVar


TEvent = TypeVar("TEvent")
Handler = Callable[[Any], None]


@dataclass(frozen=True)
class Subscription:
    event_type: type
    handler: Handler


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
