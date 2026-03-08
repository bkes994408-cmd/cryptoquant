#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone

from cryptoquant.backtest import (
    RegimeSplitConfig,
    WalkForwardConfig,
    run_regime_split_validation,
    run_walk_forward_validation,
)
from cryptoquant.events.market import MarketEvent


def _load_events(csv_path: str, *, symbol: str, timeframe: str) -> list[MarketEvent]:
    events: list[MarketEvent] = []
    with open(csv_path, newline="", encoding="utf-8") as fp:
        reader = csv.DictReader(fp)
        for row in reader:
            ts = datetime.fromisoformat(row["ts"].replace("Z", "+00:00")).astimezone(timezone.utc)
            close = float(row["close"])
            events.append(MarketEvent(symbol=symbol, timeframe=timeframe, close=close, ts=ts, source="csv"))
    return events


def _momentum_target(event: MarketEvent) -> float:
    # Demo strategy for robustness harness; replace with real strategy output in production.
    return 1.0 if event.close >= 100.0 else -1.0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run robustness validation (walk-forward + regime split)")
    parser.add_argument("--csv", required=True, help="CSV path with columns: ts,close")
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--timeframe", default="1m")
    parser.add_argument("--train-size", type=int, default=200)
    parser.add_argument("--test-size", type=int, default=50)
    parser.add_argument("--step-size", type=int, default=50)
    parser.add_argument("--regime-threshold", type=float, default=0.002)
    parser.add_argument("--fee-bps", type=float, default=4.0)
    parser.add_argument("--slippage-bps", type=float, default=2.0)
    args = parser.parse_args()

    events = _load_events(args.csv, symbol=args.symbol, timeframe=args.timeframe)

    walk_forward = run_walk_forward_validation(
        events,
        symbol=args.symbol,
        target_qty_fn=_momentum_target,
        config=WalkForwardConfig(
            train_size=args.train_size,
            test_size=args.test_size,
            step_size=args.step_size,
            fee_bps=args.fee_bps,
            slippage_bps=args.slippage_bps,
        ),
    )
    regime = run_regime_split_validation(
        events,
        symbol=args.symbol,
        target_qty_fn=_momentum_target,
        config=RegimeSplitConfig(
            return_threshold=args.regime_threshold,
            fee_bps=args.fee_bps,
            slippage_bps=args.slippage_bps,
        ),
    )

    print(
        json.dumps(
            {
                "walk_forward": {
                    "slices": len(walk_forward.slices),
                    "avg_test_return_pct": round(walk_forward.avg_test_return_pct, 4),
                    "positive_test_ratio": round(walk_forward.positive_test_ratio, 4),
                },
                "regime_split": {
                    "bull": None if regime.bull is None else round(regime.bull.return_pct, 4),
                    "sideways": None if regime.sideways is None else round(regime.sideways.return_pct, 4),
                    "bear": None if regime.bear is None else round(regime.bear.return_pct, 4),
                },
            },
            ensure_ascii=False,
        )
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
