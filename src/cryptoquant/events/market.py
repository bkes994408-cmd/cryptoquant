from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal


Timeframe = Literal["1m", "5m", "15m", "1h", "4h", "1d"]


@dataclass(frozen=True)
class MarketEvent:
    """A minimal market data event.

    This is intentionally tiny: enough shape to be produced by a future Market WS
    client and consumed by aggregators/strategies.
    """

    symbol: str
    timeframe: Timeframe
    close: float
    ts: datetime

    source: str = "dummy"
