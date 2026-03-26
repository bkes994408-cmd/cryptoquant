# Sprint Result

## v1.1 Sprint-2：Paper flip reduce-only safety hardening（2026-03-22）

1. Paper Executor 增加 reduce-only 驗證
   - 更新 `src/cryptoquant/execution/paper.py`
   - `execute_market(..., reduce_only=True)` 現在會檢查：
     - 必須有既有持倉且方向相反（否則拒絕）
     - 必須有既有持倉且方向相反（否則拒絕）
     - reduce-only 數量不可超過目前持倉

2. Flip 拆單流程相容性修正
   - `execute_to_target(...)` 在 flip close leg 會依「是否有 executor
     內部已追蹤持倉」決定是否啟用 reduce-only guard
   - 避免在「外部提供 current_qty、但 executor 尚未追蹤持倉」
     情境下誤拒單

3. 測試補齊
   - 更新 `tests/test_paper_executor.py`
   - 新增覆蓋：
     - 無持倉時 reduce-only 會拒絕
     - reduce-only 超過持倉大小會拒絕

驗證結果（2026-03-22）：

- `.venv/bin/python -m ruff check src/cryptoquant/execution/paper.py`
  `tests/test_paper_executor.py` ✅
- `.venv/bin/python -m pytest -q tests/test_paper_executor.py`
  `tests/test_execution_flip_flow.py` ✅（10 passed）

---

## v1.1 Sprint-1：listenKey supervisor renew + rebuild + WS reconnect（2026-03-22）

1. listenKey keepalive 自動重建
   - 更新 `src/cryptoquant/execution/user_stream_runtime.py`
   - `KeepaliveRunner` 新增連續失敗追蹤與重建機制：
     - `max_consecutive_failures_before_rebuild`
     - 連續失敗達門檻時自動
       `clear_cached_listen_key()` + `get_listen_key()`
     - 新增 `on_rebuild(new_listen_key, stats)` callback

2. User Stream WS 最小停機重連
   - 更新 `src/cryptoquant/execution/user_stream_binance.py`
   - 新增 `BinanceUserStreamClient.reconnect()`
   - 接到 reconnect request 時立即切斷當前循環並重建 socket，不走 backoff sleep

3. service wiring（預設自動串接）
   - `BinanceUserStreamService` 在未提供 `on_rebuild` 時，預設將
     listenKey rebuild 事件接到 `client.reconnect()`

4. 測試補齊
   - 更新 `tests/test_user_stream_runtime.py`
     - 覆蓋 keepalive 連續失敗後 listenKey rebuild
     - 覆蓋 service 在 rebuild 時觸發 client reconnect
   - 更新 `tests/test_binance_user_stream.py`
     - 覆蓋 `reconnect()` 觸發後立即重連 socket、且不進入 backoff

驗證結果（2026-03-22）：

- `.venv/bin/python -m pytest -q tests/test_user_stream_runtime.py`
  `tests/test_binance_user_stream.py` ✅

---

## MVP-11：回測引擎真實化升級（2026-03-20）

1. 新增真實撮合回測模型
   - 新增 `src/cryptoquant/backtest/mvp11.py`
   - 提供 `simulate_realistic_execution(...)`：
     - 支援 `fee_bps` / `slippage_bps` / `latency_bars`
     - 以訊號生成時點與延遲成交時點分離模擬市場單
     - 產出 `fills / equity_curve / total_fee / total_slippage_cost`

2. 新增多場景（Regime）回測
   - `RegimeScenario` / `run_regime_scenarios(...)`
   - 可基於 base config 套用場景倍率：
     - `slippage_multiplier`
     - `fee_multiplier`
     - `latency_bars`（可覆寫）

3. 新增多策略投資組合回測基礎
   - `run_multi_strategy_portfolio_backtest(...)`
   - 支援多策略 target qty 權重聚合（可自訂 weights，未提供時等權）

4. API 導出與測試補齊
   - 更新 `src/cryptoquant/backtest/__init__.py` 導出 MVP-11 API
   - 新增 `tests/test_backtest_mvp11.py`
   - 覆蓋：
     - 滑價/延遲/手續費生效
     - Regime 成本倍率生效
     - 多策略權重聚合最終持倉

驗證結果（2026-03-20）：

- `.venv/bin/python -m pytest -q tests/test_backtest_mvp11.py` ✅（3 passed）
- `.venv/bin/python -m pytest -q tests/test_backtest_mvp11.py`
  `tests/test_market_regime_detector.py`
  `tests/test_multi_strategy_portfolio_manager.py` ✅（11 passed）

---

## MVP-9：智能決策與多策略組合 / 多策略投資組合管理（2026-03-14）

1. 新增多策略投資組合管理模組
   - 新增 `src/cryptoquant/portfolio/multi_strategy.py`
   - 提供：
     - `MultiStrategyPortfolioManager`：可同時運行多策略並彙總目標倉位
     - `MultiStrategyConfig`：最小歷史長度、再平衡頻率、最佳化設定
     - `MultiStrategyDecision`：輸出聚合目標倉位、各策略決策、權重、分散度

2. 自動資金分配最佳化整合
   - 透過既有 `optimize_strategy_weights(...)` 對策略報酬序列進行風險調整後權重配置
   - 支援按 `rebalance_interval` 週期重算，避免每次事件都觸發完整最佳化

3. API 導出與測試補齊
   - 更新 `src/cryptoquant/portfolio/__init__.py` 導出多策略管理 API
   - 新增 `tests/test_multi_strategy_portfolio_manager.py`
   - 覆蓋：
     - 多策略並行決策與預設等權重聚合
     - 根據已實現報酬觸發再平衡並提升高風險調整收益策略權重
     - 報酬輸入策略名稱一致性驗證

驗證結果（2026-03-14）：

- `.venv/bin/python -m pytest -q`
  `tests/test_multi_strategy_portfolio_manager.py` ✅（3 passed）
- `.venv/bin/python -m pytest -q`
  `tests/test_multi_strategy_portfolio_manager.py`
  `tests/test_portfolio_optimizer.py tests/test_strategy_engine.py` ✅（7 passed）

---

## MVP-8：實時交易集成與高級風控 / 策略參數動態調整與強化學習應用（2026-03-12）

1. 新增動態參數調整控制器（retune + hold）
   - `src/cryptoquant/strategy/adaptive.py`
   - 提供：
     - `AdaptiveStrategyConfig`（lookback / retune interval / epsilon）
     - `EpsilonGreedyParameterBandit`（探索/利用）
     - `AdaptiveParameterController`（週期重整 + 線上 reward 更新）

2. 與既有策略最佳化流程整合
   - 控制器使用 `AutomatedStrategyOptimizer` 的 leaderboard 結果作為 reward 來源
   - 非重整周期採 `hold` 模式，重用上次 optimization 結果，避免每筆事件都做完整重算

3. 測試覆蓋
   - `tests/test_strategy_adaptive.py`
   - 涵蓋：
     - epsilon 邊界/探索/利用行為
     - 非有限 reward 防呆
     - retune/hold 週期與 optimize 呼叫次數
     - 與 `StrategyEngine` 的最小整合流程

4. 文件更新
   - 更新 `docs/ROADMAP.md`：勾選 `MVP-8` 子項 `策略參數動態調整與強化學習應用`

驗證結果（2026-03-12）：

- `.venv/bin/python -m pytest -q tests/test_strategy_optimizer.py`
  `tests/test_strategy_adaptive.py tests/test_strategy_engine.py` ✅（13 passed）
- `.venv/bin/python -m pytest -q` ✅（148 passed）

---

## MVP-8：實時交易集成與高級風控 / 實時風控預警與動態停損機制（2026-03-11）

1. 風控模組能力補強（realtime alert + dynamic stop）
   - 更新 `src/cryptoquant/risk/manager.py`
   - 新增 `RiskStatus` 狀態快照
     （daily stop / dynamic stop / side / extreme / stop price）
   - 動態停損強制平倉告警去重：在條件持續期間只發一次
     `risk.dynamic_stop.enforced`，降低告警噪音

2. API 導出
   - 更新 `src/cryptoquant/risk/__init__.py`、`src/cryptoquant/__init__.py`
   - 導出 `RiskStatus`

3. 測試補齊
   - 更新 `tests/test_risk_manager.py`
   - 覆蓋：
     - dynamic stop enforced 告警去重與重置行為
     - `RiskManager.status()` 動態停損價格回報正確性

4. 文件更新
   - 更新 `docs/ROADMAP.md`：勾選 `MVP-8` 子項 `實時風控預警與動態停損機制`

驗證結果（2026-03-11）：

- `.venv/bin/ruff check src/cryptoquant/risk/manager.py`
  `tests/test_risk_manager.py` ✅
- `.venv/bin/pytest -q tests/test_risk_manager.py` ✅
- `.venv/bin/pytest -q` ⚠️ 未通過（baseline 既有問題，非本次修改引入）：
  - `tests/test_backtest_data_sources.py`：
    `ImportError: cannot import name 'CSVDataSourceConfig'`
    `from 'cryptoquant.backtest'`
  - `tests/test_backtest_indicators.py`：
    `ImportError: cannot import name 'atr'`
    `from 'cryptoquant.backtest'`

---

## MVP-8：實時交易集成與高級風控 / 訂單簿深度與微觀結構分析（2026-03-11）

1. 新增訂單簿微觀結構分析模組
   - 新增 `src/cryptoquant/market/microstructure.py`
   - 提供：
     - `OrderBookSnapshot` / `OrderBookLevel`
     - `OrderBookMicrostructureAnalyzer`
     - `MicrostructureMetrics`
   - 指標涵蓋：
     - spread / spread_bps / mid_price
     - top-of-book `micro_price`
     - depth（bid/ask）與 depth imbalance
     - side VWAP（指定 depth level）
     - OFI（order flow imbalance，以上一筆 top-of-book 比較）

2. API 導出
   - 更新 `src/cryptoquant/market/__init__.py`
   - 導出 microstructure 核心資料結構與 analyzer

3. 測試補齊
   - 新增 `tests/test_orderbook_microstructure.py`
   - 覆蓋：
     - spread/depth/depth imbalance 正確性
     - micro_price 計算
     - OFI 在 top-of-book 變化下的方向性
     - 參數防呆（invalid depth levels）

4. 文件更新
   - 更新 `docs/ROADMAP.md`：勾選 `MVP-8` 子項 `訂單簿深度與微觀結構分析`

驗證結果（2026-03-11 重新驗證）：

- `.venv/bin/ruff check src/cryptoquant/market/microstructure.py`
  `tests/test_orderbook_microstructure.py` ✅
- `.venv/bin/pytest -q tests/test_orderbook_microstructure.py` ✅（5 passed）
- `.venv/bin/pytest -q` ⚠️ 未通過（baseline 既有問題，非本次修改引入）：
  - `tests/test_backtest_data_sources.py`：
    `ImportError: cannot import name 'CSVDataSourceConfig'`
    `from 'cryptoquant.backtest'`
  - `tests/test_backtest_indicators.py`：
    `ImportError: cannot import name 'atr'`
    `from 'cryptoquant.backtest'`

---

## MVP-6：進階回測策略驗證框架 / 策略穩健性驗證（walk-forward / regime split）（2026-03-09）

1. 新增策略穩健性驗證模組
   - 新增 `src/cryptoquant/backtest/robustness.py`
   - 提供 `run_walk_forward_validation(...)`：
     以 rolling train/test window 做 walk-forward 驗證
   - 提供 `run_regime_split_validation(...)`：
     依報酬率閾值拆分 bull / sideways / bear regime
   - 提供 `evaluate_strategy_metrics(...)`：輸出交易次數、turnover、PnL、報酬率、win rate

2. 新增可直接執行的驗證腳本
   - 新增 `scripts/validate_strategy_robustness.py`
   - 讀取 `ts,close` CSV，輸出 walk-forward 與 regime split 的 JSON 摘要

3. 測試補齊
   - 新增 `tests/test_backtest_robustness.py`
   - 覆蓋：
     - metrics 基本欄位
     - walk-forward 視窗切分與聚合指標
     - regime split 三種市場狀態回報

4. 文件更新
   - 更新 `src/cryptoquant/backtest/__init__.py` 導出 robustness API
   - 更新 `docs/ROADMAP.md`：勾選 `策略穩健性驗證（walk-forward / regime split）`

驗證結果：

- `./venv_ci_cryptoquant/bin/pytest -q` ✅

---

MVP-6：進階回測策略驗證框架

## 回測事件匯流排壓測基準（p95 latency / max throughput）（2026-03-09）

1. 新增事件匯流排壓測框架
   - 新增 `src/cryptoquant/backtest/event_bus_benchmark.py`
   - 提供 `run_event_bus_benchmark(...)`，
     輸出 `p50/p95/p99/max latency (us)` 與 `throughput (events/sec)`
   - 支援 warmup、worker/batch/queue 配置，並可切換 drop-on-full 或 block-on-full

2. 新增可直接執行的壓測腳本
   - 新增 `scripts/benchmark_event_bus.py`
   - 範例：
     - `PYTHONPATH=src ./venv_ci_cryptoquant/bin/python`
       `scripts/benchmark_event_bus.py --events 100000 --warmup-events 10000`
       `--workers 2 --batch-size 256`

3. 測試補齊
   - 新增 `tests/test_event_bus_benchmark.py`
   - 覆蓋百分位計算與壓測結果關鍵欄位（p95 latency / throughput）

4. 文件更新
   - 更新 `src/cryptoquant/backtest/__init__.py` 導出 benchmark API
   - 更新 `docs/ROADMAP.md`：勾選 `回測事件匯流排壓測基準（p95 latency / max throughput）`

驗證結果：

- `./venv_ci_cryptoquant/bin/pytest -q` ✅

---

## MVP-6：進階回測策略驗證框架 / 高頻交易基礎設施調優（低延遲、高吞吐量）（2026-03-09）

1. 事件匯流排可靠性/吞吐優化
   - 擴充 `LowLatencyEventBus`：新增 `flush(timeout_sec)`，可在回測階段等待 queue drained
   - `stop()` 先 flush 再停工，降低 shutdown 遺留事件風險
   - 批次 dispatch metrics 聚合改為「每批一次上鎖」以降低 lock contention
   - worker 加入 handler exception 隔離，單一 handler 失敗不拖垮整條 dispatch pipeline

2. 可觀測性指標擴展
   - `DispatchStats` 新增：
     - `batches`（批次數）
     - `handler_errors`（handler 例外次數）

3. 測試補齊
   - 更新 `tests/test_low_latency_event_bus.py`，新增覆蓋：
     - `flush` 能正確等待隊列清空
     - handler 發生例外時，worker 能持續運作並累計錯誤計數

4. 文件更新
   - 更新 `docs/ROADMAP.md`：新增 `MVP-6：進階回測策略驗證框架`
   - 勾選該階段首個完成項：`高頻交易基礎設施調優（低延遲、高吞吐量）`

驗證結果：

- `./venv_ci_cryptoquant/bin/pytest -q` ✅

---

## MVP-5：高頻交易基礎設施調優（低延遲、高吞吐量）（2026-03-08）

1. 低延遲/高吞吐事件匯流排
   - 擴充 `src/cryptoquant/events/bus.py`，新增 `LowLatencyEventBus`
   - 透過 bounded queue + worker threads + micro-batch dispatch 提升 burst 吞吐
   - 支援 `drop_on_full` 背壓策略，避免高峰時 publisher 阻塞
   - 新增 `DispatchStats`，可觀測 published/dropped/dispatched
     與平均 dispatch latency（微秒）

2. API 導出
   - 更新 `src/cryptoquant/events/__init__.py`
   - 導出 `LowLatencyEventBus` 與 `DispatchStats`，便於執行層直接接線

3. 測試補齊
   - 新增 `tests/test_low_latency_event_bus.py`
   - 覆蓋：
     - batched dispatch correctness（200 events）
     - backpressure drop 行為（queue 滿載時 dropped > 0）

4. 文件更新
   - 更新 `docs/ROADMAP.md`：勾選 `MVP-5` 子項 `高頻交易基礎設施調優（低延遲、高吞吐量）`

驗證結果：

- `./venv_ci_cryptoquant/bin/pytest -q` ✅

---

## MVP-1 第一階段：Market Data Flow（2026-02-27）

1. Market WS（1m kline close）+ 自動重連（最小可用）
   - 新增 `src/cryptoquant/market/ws_client.py`
   - 實作 `BinanceKlineWSClient`
     - 透過 Binance combined stream 訂閱 `@kline_1m`
     - 僅在 `k.x=true`（K 線收盤）時發出 `MarketEvent`
     - 斷線後以 bounded exponential backoff 自動重連
   - 新增 `src/cryptoquant/market/__init__.py`

2. BarAggregator（15m/1h）+ 基本 gap fill
   - 原有 `BarAggregator` 已具備 15m/1h 聚合與 gap fill；
     本輪以資料流測試補齊驗證，確認可銜接 MarketEvent。

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

---

## MVP-2 測試推進（2026-02-28）

1. OMS 狀態機與冪等測試補齊
   - 新增 `tests/test_oms.py`
     - `NEW -> FILLED`
     - `NEW -> CANCELED`
     - `NEW -> REJECTED`
     - `clientOrderId` 冪等（重送同 id 不覆蓋原單）
     - terminal state 非法轉移保護

2. Daily stop 高價值行為測試補強
   - 更新 `tests/test_risk_manager.py`
     - 明確驗證觸發 daily stop 後：
       - 可減倉
       - 可平倉（target=0）
       - 同日平倉後仍不可再開新倉

3. 翻轉拆單（reduceOnly close→open）流程：先補測試框架 + TODO
   - 更新 `tests/test_backtest_replay.py`
   - 新增 `xfail` 測試
     `test_event_replayer_flip_should_split_reduce_only_close_then_open`
   - 現況：`EventReplayer` 仍以單筆 delta 下單，尚未實作拆單；
     測試已鎖定預期行為供後續實作

驗證結果：`pytest -q`（本輪）應為全綠 + 1 xfailed（翻轉拆單待實作）

---

MVP-6：進階回測策略驗證框架

## 大樣本回放資源治理（memory / queue backpressure 可觀測）（2026-03-09）

1. 新增大樣本回放資源治理模組
   - 新增 `src/cryptoquant/backtest/replay_resource_governance.py`
   - 提供 `run_large_sample_replay_governance(...)`，
     回傳記憶體追蹤與 queue 壓力觀測報告
   - 報告欄位包含 `peak_memory_kb`、`queue_high_watermark`、
     `max_queue_utilization`、`backpressure_count`

2. 擴充事件匯流排可觀測性
   - 擴充 `src/cryptoquant/events/bus.py`：
     `LowLatencyEventBus` 新增 queue 水位與 backpressure 計數
   - `DispatchStats` 新增 `queue_capacity`、
     `queue_high_watermark`、`backpressure_count`

3. 壓測輸出補齊資源治理指標
   - 新增/更新 `src/cryptoquant/backtest/event_bus_benchmark.py`
   - benchmark 結果新增 `backpressure_count`、`queue_high_watermark`

4. 測試補齊
   - 新增 `tests/test_low_latency_event_bus.py`
   - 新增 `tests/test_event_bus_benchmark.py`
   - 新增 `tests/test_replay_resource_governance.py`

5. 文件更新
   - 更新 `src/cryptoquant/backtest/__init__.py` 導出新增 API
   - 更新 `docs/ROADMAP.md`：勾選 `大樣本回放資源治理（memory / queue backpressure 可觀測）`

驗證結果：

- `./venv_ci_cryptoquant/bin/pytest -q` ✅

## MVP-8：實時交易集成與高級風控 / 高可用性與災難恢復（2026-03-12）

1. 新增高可用性故障切換決策模組
   - 新增 `src/cryptoquant/ops/high_availability.py`
   - 提供 `evaluate_failover(...)`：
     - primary 不可達或 heartbeat 過期時，才進入 failover 評估
     - standby 候選需同時滿足 reachable / heartbeat 門檻 / replication lag 門檻
     - 以 `lag` + `heartbeat_age` 排序，選擇最佳升主節點

2. 新增災難恢復計畫產生器
   - 同檔新增 `plan_disaster_recovery(...)`
   - 依 `generation`、`checkpoint_ts_ms`、`instance_id` 穩定排序選出恢復來源 snapshot
   - 回傳 `RecoveryPlan`（來源節點、目標節點、是否需 replay）

3. 新增 ops 模組導出
   - 新增 `src/cryptoquant/ops/__init__.py`

4. 測試補齊
   - 新增 `tests/test_high_availability.py`
   - 覆蓋情境：
     - primary 當機時從健康 standby 升主
     - 無可用 standby 時避免誤切換
     - DR snapshot 依世代與時間戳正確挑選
     - 無 snapshot 時拋出明確錯誤

5. Roadmap 更新
   - `docs/ROADMAP.md` 勾選：`高可用性與災難恢復`

驗證結果：

- `pytest -q tests/test_high_availability.py` ✅
- `pytest -q` ✅
