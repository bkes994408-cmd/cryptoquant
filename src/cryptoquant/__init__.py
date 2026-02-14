"""CryptoQuant package.

MVP-1 introduces a minimal event-driven core to unblock future Market WS integration.
"""

from .events.market import MarketEvent
from .events.bus import EventBus

__all__ = ["EventBus", "MarketEvent"]
