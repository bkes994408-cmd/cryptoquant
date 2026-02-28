"""CryptoQuant package.

MVP-1 introduces a minimal event-driven core to unblock future Market WS integration.
"""

from .aggregation import Bar, BarAggregator
from .events.market import MarketEvent
from .events.bus import EventBus
from .market import BinanceKlineWSClient
from .strategy import StrategyDecision, StrategyEngine, MovingAverageCrossoverStrategy
from .risk import RiskInput, RiskLimits, RiskManager, RiskResult
from .oms import OMS, Order, OrderStatus
from .execution import Fill, PaperExecutor
from .backtest import BacktestResult, EventReplayer

__all__ = [
    "EventBus",
    "MarketEvent",
    "Bar",
    "BarAggregator",
    "BinanceKlineWSClient",
    "StrategyDecision",
    "StrategyEngine",
    "MovingAverageCrossoverStrategy",
    "RiskInput",
    "RiskLimits",
    "RiskManager",
    "RiskResult",
    "OMS",
    "Order",
    "OrderStatus",
    "Fill",
    "PaperExecutor",
    "BacktestResult",
    "EventReplayer",
]
