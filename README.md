# cryptoquant

Minimal event-driven scaffold for a future Paper/Backtest engine.

## MVP-1 Market WS client

Implemented `BinanceKlineWSClient` to ingest Binance `1m` kline close events and publish `MarketEvent` into `EventBus`.

Features:
- consume `wss://stream.binance.com:9443/ws/<symbol>@kline_1m`
- parse close price only when kline is closed (`k.x == true`)
- auto reconnect with exponential backoff (1s, 2s, 4s ... capped)
