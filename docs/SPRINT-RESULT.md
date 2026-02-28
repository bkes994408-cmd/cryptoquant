# Sprint Result

## MVP-1 第一階段：Market Data Flow（2026-02-27）

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
   - 新增 `tests/test_market_dataflow.py`

4. 文件更新
   - 更新 `docs/ROADMAP.md`：勾選已完成子項（Market WS、BarAggregator）

驗證結果：`./venv_ci_cryptoquant/bin/pytest -q` → **8 passed**

---

## MVP-1 第二階段：Strategy / Risk / OMS 基礎（2026-02-28）

1. Strategy Engine 基礎實作
   - 新增 `src/cryptoquant/strategy/engine.py`
     - `StrategyEngine`：接收聚合後 bars，輸出 `StrategyDecision(target_qty, signal)`
   - 新增 `src/cryptoquant/strategy/ma_crossover.py`
     - `MovingAverageCrossoverStrategy`（MA crossover 範例）
     - `fast > slow => long`、`fast < slow => short`、不足資料或相等 => `0`

2. Risk Manager 基礎實作
   - 新增 `src/cryptoquant/risk/manager.py`
     - `RiskLimits` / `RiskInput` / `RiskResult`
     - 先實作 `notional cap` 與 `leverage cap` 兩種限制（clamp target qty）

3. OMS 基礎實作
   - 新增 `src/cryptoquant/oms/oms.py`、`src/cryptoquant/oms/models.py`
     - `submit` 具 `clientOrderId` 冪等
     - 最小狀態機：`NEW -> FILLED/CANCELED/REJECTED`

4. 最小測試
   - 新增 `tests/test_strategy_engine.py`
   - 新增 `tests/test_risk_manager.py`

5. 文件更新
   - 更新 `docs/ROADMAP.md`：勾選本階段已完成項，並保留 `daily stop` 未完成

驗證結果：`./venv_ci_cryptoquant/bin/pytest -q`（本輪請以最新測試結果為準）

## 後續建議

- 補 OMS 狀態機與冪等專項測試（對應 MVP-2 清單）
- 在 RiskManager 加入 daily stop（以日內已實現/未實現損益為 gate）
- 串接 Strategy → Risk → OMS → Paper Executor 的端到端 runner

---

## MVP-1 最後階段：Paper Executor / Backtest Replay / Daily Stop（2026-02-28）

1. Paper Executor（市價撮合 + 手續費/滑價）
   - 新增 `src/cryptoquant/execution/paper.py`
     - `PaperExecutor.execute_market(...)`：
       - 市價單以 `mark_price` 為基準，套用雙邊滑價（buy 上滑、sell 下滑）
       - 計算 `notional`、`fee`、`slippage_cost`
       - 透過既有 `OMS` 狀態機完成 `NEW -> FILLED`
       - `client_order_id` 重送具冪等（回傳相同 fill，不重複持倉變動）

2. 最小事件回放（Backtest）
   - 新增 `src/cryptoquant/backtest/replay.py`
     - `EventReplayer.run(...)`：
       - 依時間順序回放 `MarketEvent`
       - 透過 `target_qty_fn` 產生目標倉位
       - 自動計算 `delta = target - current` 並送入 `PaperExecutor`
       - 產出 `BacktestResult(fills)` 用於驗證行為

3. Risk Manager：daily stop
   - 擴充 `src/cryptoquant/risk/manager.py`
     - `RiskLimits.daily_stop_drawdown_pct`（可選）
     - 以「當日錨定權益」計算日內回撤，達門檻即觸發 `daily stop`
     - 觸發後禁止「新開/加倉/翻向新倉」，但允許減倉和平倉

4. 測試補齊
   - 新增 `tests/test_paper_executor.py`
   - 新增 `tests/test_backtest_replay.py`
   - 更新 `tests/test_risk_manager.py`，加入 daily stop 測試

5. 文件更新
   - `docs/ROADMAP.md` 勾選：
     - Risk Manager：daily stop
     - Executor（Paper）
     - 事件回放（Backtest）最小版本

驗證結果：`./venv_ci_cryptoquant/bin/pytest -q`（請見本輪最新結果）
