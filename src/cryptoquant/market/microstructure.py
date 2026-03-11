from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class OrderBookLevel:
    price: float
    size: float


@dataclass(frozen=True)
class OrderBookSnapshot:
    symbol: str
    ts: datetime
    bids: tuple[OrderBookLevel, ...]
    asks: tuple[OrderBookLevel, ...]
    source: str = "unknown"


@dataclass(frozen=True)
class MicrostructureMetrics:
    symbol: str
    ts: datetime
    depth_levels: int
    best_bid: float
    best_ask: float
    spread: float
    spread_bps: float
    mid_price: float
    micro_price: float
    bid_depth: float
    ask_depth: float
    depth_imbalance: float
    bid_vwap: float
    ask_vwap: float
    order_flow_imbalance: float


class OrderBookMicrostructureAnalyzer:
    """Analyze order book depth and microstructure signals.

    Current metrics include:
    - spread / spread_bps / mid_price
    - micro_price (top-of-book size weighted fair price)
    - bid/ask depth and depth imbalance
    - side VWAP on selected depth
    - order flow imbalance (OFI) with top-of-book delta vs previous snapshot
    """

    def __init__(self) -> None:
        self._prev_top: tuple[float, float, float, float] | None = None

    def analyze(
        self,
        snapshot: OrderBookSnapshot,
        *,
        depth_levels: int = 5,
    ) -> MicrostructureMetrics:
        if depth_levels <= 0:
            raise ValueError("depth_levels must be > 0")
        if not snapshot.bids or not snapshot.asks:
            raise ValueError("snapshot must contain both bids and asks")

        bids = snapshot.bids[:depth_levels]
        asks = snapshot.asks[:depth_levels]

        best_bid = bids[0].price
        best_ask = asks[0].price
        spread = max(best_ask - best_bid, 0.0)
        mid = (best_bid + best_ask) / 2.0
        spread_bps = (spread / mid * 10_000.0) if mid > 0 else 0.0

        bid_depth = sum(max(l.size, 0.0) for l in bids)
        ask_depth = sum(max(l.size, 0.0) for l in asks)
        total_depth = bid_depth + ask_depth
        depth_imbalance = (
            (bid_depth - ask_depth) / total_depth if total_depth > 0 else 0.0
        )

        bid_vwap = _vwap(bids)
        ask_vwap = _vwap(asks)

        top_bid_size = max(bids[0].size, 0.0)
        top_ask_size = max(asks[0].size, 0.0)
        micro_price = (
            (best_ask * top_bid_size + best_bid * top_ask_size)
            / (top_bid_size + top_ask_size)
            if (top_bid_size + top_ask_size) > 0
            else mid
        )

        ofi = self._compute_ofi(best_bid, top_bid_size, best_ask, top_ask_size)
        self._prev_top = (best_bid, top_bid_size, best_ask, top_ask_size)

        return MicrostructureMetrics(
            symbol=snapshot.symbol,
            ts=snapshot.ts,
            depth_levels=min(depth_levels, len(snapshot.bids), len(snapshot.asks)),
            best_bid=best_bid,
            best_ask=best_ask,
            spread=spread,
            spread_bps=spread_bps,
            mid_price=mid,
            micro_price=micro_price,
            bid_depth=bid_depth,
            ask_depth=ask_depth,
            depth_imbalance=depth_imbalance,
            bid_vwap=bid_vwap,
            ask_vwap=ask_vwap,
            order_flow_imbalance=ofi,
        )

    def _compute_ofi(
        self,
        bid_px: float,
        bid_sz: float,
        ask_px: float,
        ask_sz: float,
    ) -> float:
        if self._prev_top is None:
            return 0.0

        prev_bid_px, prev_bid_sz, prev_ask_px, prev_ask_sz = self._prev_top

        bid_component = (
            (1.0 if bid_px >= prev_bid_px else 0.0) * bid_sz
            - (1.0 if bid_px <= prev_bid_px else 0.0) * prev_bid_sz
        )
        ask_component = (
            (1.0 if ask_px <= prev_ask_px else 0.0) * ask_sz
            - (1.0 if ask_px >= prev_ask_px else 0.0) * prev_ask_sz
        )

        return bid_component - ask_component


def _vwap(levels: tuple[OrderBookLevel, ...]) -> float:
    denom = sum(max(level.size, 0.0) for level in levels)
    if denom <= 0:
        return 0.0
    return sum(level.price * max(level.size, 0.0) for level in levels) / denom
