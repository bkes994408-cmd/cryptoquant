# Roadmap / MVP Checklist（CryptoQuant）

> 原則：先 Paper/Backtest，完整測試與風控到位後再談 Live。

## MVP-0：工程化（門檻）

- [x] Repo 結構：src/ tests/ docs/
- [x] CI：lint + unit tests + basic security scan
- [x] 組態：dev/stg/prd 設定分層

## MVP-1：Paper 模式可跑通（端到端）

- [ ] Market WS（1m kline close）+ 自動重連
- [ ] BarAggregator（15m/1h）+ gap fill
- [ ] Strategy Engine：輸出 targetQty（多空/0）
- [ ] Risk Manager：notional cap / leverage cap / daily stop
- [ ] OMS：clientOrderId 冪等 + 狀態機
- [ ] Executor（Paper）：撮合（市價為主）+ 手續費/滑價模型
- [ ] 事件回放（Backtest）最小版本

## MVP-2：完整功能測試（必備）

- [ ] OMS 狀態機 unit tests（new→filled/canceled/rejected）
- [ ] 冪等測試：重送不重複下單
- [ ] 翻轉拆單（reduceOnly close→open）流程測試
- [ ] 重啟恢復（REST snapshot + User Stream 覆蓋）測試
- [ ] 風控測試：觸發 daily stop → 禁止新倉

## MVP-3：Live 前置（之後）

- [ ] Secrets 管理（不得寫入 log）
- [ ] Kill switch
- [ ] 監控告警（orders/rejects/safe mode）
