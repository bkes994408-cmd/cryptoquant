# Roadmap / MVP Checklist（CryptoQuant）

> 原則：先 Paper/Backtest，完整測試與風控到位後再談 Live。

## MVP-0：工程化（門檻）

- [x] Repo 結構：src/ tests/ docs/
- [x] CI：lint + unit tests + basic security scan
- [x] 組態：dev/stg/prd 設定分層

## MVP-1：Paper 模式可跑通（端到端）

- [x] Market WS（1m kline close）+ 自動重連
- [x] BarAggregator（15m/1h）+ gap fill
- [x] Strategy Engine：輸出 targetQty（多空/0）
- [x] Risk Manager：notional cap / leverage cap
- [x] Risk Manager：daily stop
- [x] OMS：clientOrderId 冪等 + 狀態機
- [x] Executor（Paper）：撮合（市價為主）+ 手續費/滑價模型
- [x] 事件回放（Backtest）最小版本

## MVP-2：完整功能測試（必備）

- [x] OMS 狀態機 unit tests（new→filled/canceled/rejected）
- [x] 冪等測試：重送不重複下單
- [x] 翻轉拆單（reduceOnly close→open）流程測試
- [x] 重啟恢復（REST snapshot + User Stream 覆蓋）測試
- [x] 風控測試：觸發 daily stop → 禁止新倉

## MVP-3：Live 前置（之後）

- [x] Secrets 管理（不得寫入 log）
- [x] Kill switch
- [x] 監控告警（orders/rejects/safe mode）

## MVP-4：Live Adapter（進行中）

- [x] Live executor skeleton（gateway interface + idempotency + kill switch guard）
- [x] Binance REST gateway（實際下單）
- [x] User Stream 事件接線（ACK/FILL/REJECT 回寫 OMS）
- [x] 端到端 dry-run（testnet）

## MVP-5：高階實時交易與擴展

- [x] 集成多個交易對
- [x] 實時績效監控與分析
- [x] 自動化策略優化
- [x] 回測平台強化（更多數據源、高級指標）
- [x] 高頻交易基礎設施調優（低延遲、高吞吐量）

## MVP-6：進階回測策略驗證框架

- [x] 高頻交易基礎設施調優（低延遲、高吞吐量）
- [x] 回測事件匯流排壓測基準（p95 latency / max throughput）
- [x] 策略穩健性驗證（walk-forward / regime split）
- [x] 大樣本回放資源治理（memory / queue backpressure 可觀測）
