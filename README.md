# cryptoquant

MVP-driven quantitative trading scaffold（事件驅動 + 可測試 execution/risk/strategy 模組）。

## MVP-8：交易所 API 集成與高級風控（目前完成範圍）

本次交付目前已完成：

1. **Binance Futures + 多帳戶 live execution** 最小可用能力：

- `BinanceFuturesOrderGateway`：可發送市場單並回傳標準化 ack。
- `MultiAccountBinanceGateway`：依 `account_id` 路由到對應 API 金鑰。
- `MultiAccountLiveExecutor`：
  - 每帳戶獨立 idempotency（`account_id + client_order_id`）
  - `KillSwitch` 防護
  - 下單前風險檢查（含 `qty != 0`）
  - 帳戶集合一致性驗證（`oms_by_account` 必須與 gateway 帳戶集合一致）

> 非本次範圍：完整資產同步、WebSocket user stream、資金費率與保證金管理、跨交易所抽象。

1. **訂單簿深度與微觀結構分析**：

- `OrderBookMicrostructureAnalyzer`：對 order book snapshot 產生可用於策略/風控的即時指標。
- 內建指標：`spread`、`spread_bps`、`mid_price`、`micro_price`、
  `depth_imbalance`、`order_flow_imbalance`。
- 可指定 `depth_levels`，統計前 N 檔深度與 side VWAP。

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

## 風控語義：Dynamic Stop（Trailing）

`RiskManager` 在 `dynamic_stop` 啟用時，會根據目前持倉方向追蹤「有利極值」：

- `LONG`：追蹤最高價，stop = `extreme * (1 - trailing_pct)`
- `SHORT`：追蹤最低價，stop = `extreme * (1 + trailing_pct)`

當價格觸發 stop 後，`dynamic_stop_triggered=True`，且當前決策會**強制把同向維持/加碼目標壓成 0（flatten）**。

### 觸發後的翻向開倉策略（避免歧義）

Dynamic stop 觸發後，系統策略是：

- ✅ **允許風險降低/平倉**（同向減倉、到 0）
- ✅ **允許翻向開倉**（例如 LONG 停損後可直接開 SHORT，或反之）
- ❌ **不允許同向維持或加碼**（直到倉位狀態更新為可追蹤的新 side）

也就是說，dynamic stop 的目標是「阻止原方向風險延續」，不是凍結所有交易行為。

## 開發

```bash
pip install -e .[dev]
pytest -q
```
