from __future__ import annotations

import argparse
import os

from cryptoquant.execution import (
    BinanceFuturesOrderGateway,
    BinanceGatewayConfig,
    DryRunRequest,
    run_testnet_dry_run,
    run_testnet_dry_run_batch,
)


def _parse_pair(raw: str) -> tuple[str, float]:
    if ":" not in raw:
        raise argparse.ArgumentTypeError("pair must be in SYMBOL:QTY format")

    symbol, qty_raw = raw.split(":", 1)
    symbol = symbol.strip().upper()
    if not symbol:
        raise argparse.ArgumentTypeError("symbol cannot be empty")

    try:
        qty = float(qty_raw)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("qty must be numeric") from exc

    return symbol, qty


def main() -> int:
    parser = argparse.ArgumentParser(description="CryptoQuant testnet dry-run")
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--qty", type=float, default=0.001)
    parser.add_argument("--client-order-id", default="dry-run-1")
    parser.add_argument(
        "--pair",
        action="append",
        type=_parse_pair,
        help="multi-order mode: repeat SYMBOL:QTY, e.g. --pair BTCUSDT:0.001 --pair ETHUSDT:-0.01",
    )
    parser.add_argument("--client-order-id-prefix", default="dry-run")
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

    if args.pair:
        requests = [
            DryRunRequest(
                symbol=symbol,
                qty=qty,
                client_order_id=f"{args.client_order_id_prefix}-{idx}",
            )
            for idx, (symbol, qty) in enumerate(args.pair, start=1)
        ]
        results = run_testnet_dry_run_batch(
            gateway=gateway,
            requests=requests,
            simulate_fill_event=not args.no_fill_event,
        )
        print(
            [
                {
                    "client_order_id": result.client_order_id,
                    "exchange_order_id": result.exchange_order_id,
                    "final_status": result.final_status.value,
                    "alerts": [a.code for a in result.alerts],
                }
                for result in results
            ]
        )
        return 0

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
