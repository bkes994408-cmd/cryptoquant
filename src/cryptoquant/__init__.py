"""CryptoQuant package.

MVP-1 introduces a minimal event-driven core to unblock future Market WS integration.
"""

from .aggregation import Bar, BarAggregator
from .events.market import MarketEvent
from .events.bus import EventBus
from .market import BinanceKlineWSClient
from .strategy import StrategyDecision, StrategyEngine, MovingAverageCrossoverStrategy
from .risk import KillSwitch, RiskInput, RiskLimits, RiskManager, RiskResult
from .oms import OMS, Order, OrderStatus
from .execution import (
    BinanceFuturesOrderGateway,
    BinanceGatewayConfig,
    DryRunResult,
    Fill,
    HttpTransport,
    LiveExecutor,
    LiveOrderAck,
    LiveOrderRequest,
    OrderGateway,
    PaperExecutor,
    RecoveredState,
    RecoverySnapshot,
    UserStreamEvent,
    recover_state,
    ExecutionReport,
    UserStreamProcessor,
    run_testnet_dry_run,
    BinanceUserStreamClient,
    parse_binance_execution_report,
)
from .backtest import BacktestResult, EventReplayer
from .security import DEFAULT_SECRET_KEYS, redact_secrets
from .monitoring import Alert, AlertLevel, AlertSink, Monitoring

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
    "KillSwitch",
    "OMS",
    "Order",
    "OrderStatus",
    "BinanceGatewayConfig",
    "HttpTransport",
    "BinanceFuturesOrderGateway",
    "DryRunResult",
    "run_testnet_dry_run",
    "LiveOrderRequest",
    "LiveOrderAck",
    "OrderGateway",
    "LiveExecutor",
    "Fill",
    "PaperExecutor",
    "RecoverySnapshot",
    "UserStreamEvent",
    "RecoveredState",
    "recover_state",
    "ExecutionReport",
    "UserStreamProcessor",
    "BinanceUserStreamClient",
    "parse_binance_execution_report",
    "BacktestResult",
    "EventReplayer",
    "DEFAULT_SECRET_KEYS",
    "redact_secrets",
    "Alert",
    "AlertLevel",
    "AlertSink",
    "Monitoring",
]
