# Sprint Result（MVP-1 第一階段：Market Data Flow）

日期：2026-02-27

## 本輪完成項目

1. Market WS（1m kline close）+ 自動重連（最小可用）
   - 新增 `src/cryptoquant/market/ws_client.py`
   - 實作 `BinanceKlineWSClient`
     - 透過 Binance combined stream 訂閱 `@kline_1m`
     - 僅在 `k.x=true`（K 線收盤）時發出 `MarketEvent`
     - 斷線後以 bounded exponential backoff 自動重連
   - 新增 `src/cryptoquant/market/__init__.py`

2. BarAggregator（15m/1h）+ 基本 gap fill
   - 原有 `BarAggregator` 已具備 15m/1h 聚合與 gap fill；本輪以資料流測試補齊驗證，確認可銜接 MarketEvent。

3. 最小測試（驗證資料流可運作）
   - 新增 `tests/test_market_ws.py`
     - 驗證只處理 closed kline
     - 驗證斷線後可重連並持續產生事件
   - 新增 `tests/test_market_dataflow.py`
     - 驗證 EventBus + MarketEvent + BarAggregator（含 gap fill）資料流可跑通

4. 文件更新
   - 更新 `docs/ROADMAP.md`：勾選已完成子項（Market WS、BarAggregator）

## 驗證結果（本機）

- `./venv_ci_cryptoquant/bin/pytest -q`：**8 passed**

## 已知限制（刻意保留為 MVP）

- WS 客戶端目前只處理最小欄位與最小錯誤復原邏輯（重連/backoff），尚未加入心跳監測、訂閱動態調整、更多異常分類。
- live 使用需安裝 `websocket-client`（目前採 lazy import，測試不依賴外部 WS 套件）。

## 下一步建議

1. 增加 market stream 與 event bus 的整合 runner（把 `BinanceKlineWSClient` 直接接到 bus）。
2. 增加 aggregator 的增量模式（streaming append）避免每次全量 aggregate。
3. 在 MVP-1 後續子項串接 Strategy Engine / Risk / OMS / Paper Executor。
