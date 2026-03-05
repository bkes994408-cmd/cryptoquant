from __future__ import annotations

import argparse
import os

from cryptoquant.execution import (
    BinanceFuturesOrderGateway,
    BinanceGatewayConfig,
    run_testnet_dry_run,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="CryptoQuant testnet dry-run")
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--qty", type=float, default=0.001)
    parser.add_argument("--client-order-id", default="dry-run-1")
    parser.add_argument("--no-fill-event", action="store_true")
    args = parser.parse_args()

    api_key = os.getenv("BINANCE_API_KEY", "")
    api_secret = os.getenv("BINANCE_API_SECRET", "")
    base_url = os.getenv("BINANCE_BASE_URL", "https://testnet.binancefuture.com")

    if not api_key or not api_secret:
        raise SystemExit("BINANCE_API_KEY / BINANCE_API_SECRET are required")

    gateway = BinanceFuturesOrderGateway(
        BinanceGatewayConfig(api_key=api_key, api_secret=api_secret, base_url=base_url)
    )

    result = run_testnet_dry_run(
        gateway=gateway,
        symbol=args.symbol,
        qty=args.qty,
        client_order_id=args.client_order_id,
        simulate_fill_event=not args.no_fill_event,
    )

    print(
        {
            "client_order_id": result.client_order_id,
            "exchange_order_id": result.exchange_order_id,
            "final_status": result.final_status.value,
            "alerts": [a.code for a in result.alerts],
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
