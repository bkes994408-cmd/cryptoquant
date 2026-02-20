"""CryptoQuant package.

MVP-1 introduces a minimal event-driven core to unblock future Market WS integration.
"""

from .aggregation import Bar, BarAggregator
from .events.market import MarketEvent
from .events.bus import EventBus
from .market import BinanceKlineWSClient

__all__ = ["EventBus", "MarketEvent", "Bar", "BarAggregator", "BinanceKlineWSClient"]
