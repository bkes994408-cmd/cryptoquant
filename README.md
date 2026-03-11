# cryptoquant

MVP-driven quantitative trading scaffold（事件驅動 + 可測試 execution/risk/strategy 模組）。

## MVP-8：交易所 API 集成與多帳戶管理（目前完成範圍）

本次交付聚焦 **Binance Futures + 多帳戶 live execution** 的最小可用能力：

- `BinanceFuturesOrderGateway`：可發送市場單並回傳標準化 ack。
- `MultiAccountBinanceGateway`：依 `account_id` 路由到對應 API 金鑰。
- `MultiAccountLiveExecutor`：
  - 每帳戶獨立 idempotency（`account_id + client_order_id`）
  - `KillSwitch` 防護
  - 下單前風險檢查（含 `qty != 0`）
  - 帳戶集合一致性驗證（`oms_by_account` 必須與 gateway 帳戶集合一致）

> 非本次範圍：完整資產同步、WebSocket user stream、資金費率與保證金管理、跨交易所抽象。

## 最小可用範例

```python
from cryptoquant.execution import (
    ExchangeAccountConfig,
    MultiAccountBinanceGateway,
    MultiAccountLiveExecutor,
    MultiAccountOrderRequest,
)
from cryptoquant.oms import OMS

accounts = [
    ExchangeAccountConfig(
        account_id="acct-a",
        exchange="binance",
        api_key="<BINANCE_API_KEY_A>",
        api_secret="<BINANCE_API_SECRET_A>",
    ),
    ExchangeAccountConfig(
        account_id="acct-b",
        exchange="binance",
        api_key="<BINANCE_API_KEY_B>",
        api_secret="<BINANCE_API_SECRET_B>",
    ),
]

gateway = MultiAccountBinanceGateway(accounts)
executor = MultiAccountLiveExecutor(
    oms_by_account={"acct-a": OMS(), "acct-b": OMS()},
    gateway=gateway,
)

ack = executor.execute_market(
    MultiAccountOrderRequest(
        account_id="acct-a",
        client_order_id="rebalance-20260311-001",
        symbol="BTCUSDT",
        qty=0.01,
    )
)

print(ack.exchange_order_id, ack.ack_ts_ms)
```

## 開發

```bash
pip install -e .[dev]
pytest -q
```
