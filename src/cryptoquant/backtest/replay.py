from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable

from cryptoquant.events.market import MarketEvent
from cryptoquant.execution import Fill, PaperExecutor


@dataclass(frozen=True)
class BacktestResult:
    fills: list[Fill]


class EventReplayer:
    """Replay market events and route generated market orders to PaperExecutor.

    - If `symbol` is provided, only that symbol is replayed (legacy behavior).
    - If `symbol` is None, events for all symbols are replayed.
    """

    def __init__(self, executor: PaperExecutor, *, symbol: str | None = None) -> None:
        self._executor = executor
        self._symbol = symbol

    def run(
        self,
        events: Iterable[MarketEvent],
        *,
        target_qty_fn: Callable[[MarketEvent], float],
        order_id_prefix: str = "bt",
    ) -> BacktestResult:
        fills: list[Fill] = []
        for idx, event in enumerate(sorted(events, key=lambda e: e.ts), start=1):
            if self._symbol is not None and event.symbol != self._symbol:
                continue

            symbol = event.symbol
            target_qty = target_qty_fn(event)
            current_qty = self._executor.position_qty(symbol)
            if current_qty == target_qty:
                continue

            legs = self._executor.execute_to_target(
                client_order_id_prefix=f"{order_id_prefix}-{idx}",
                symbol=symbol,
                current_qty=current_qty,
                target_qty=target_qty,
                mark_price=event.close,
                ts=event.ts,
            )
            fills.extend(legs)
        return BacktestResult(fills=fills)
