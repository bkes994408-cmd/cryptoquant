from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable

from cryptoquant.events.market import MarketEvent
from cryptoquant.execution import Fill, PaperExecutor


@dataclass(frozen=True)
class BacktestResult:
    fills: list[Fill]


class EventReplayer:
    """Replay market events and route generated market orders to PaperExecutor."""

    def __init__(self, executor: PaperExecutor, *, symbol: str) -> None:
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
            if event.symbol != self._symbol:
                continue
            target_qty = target_qty_fn(event)
            current_qty = self._executor.position_qty(self._symbol)
            delta = target_qty - current_qty
            if delta == 0:
                continue
            fill = self._executor.execute_market(
                client_order_id=f"{order_id_prefix}-{idx}",
                symbol=self._symbol,
                qty=delta,
                mark_price=event.close,
                ts=event.ts,
            )
            fills.append(fill)
        return BacktestResult(fills=fills)
