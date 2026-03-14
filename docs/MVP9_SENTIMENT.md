# MVP-9 市場情緒分析整合（第一版）

本次實作提供一個低風險、可擴充的第一增量：

## 1) Adapter Layer

- `SentimentAdapter`（Protocol）：定義 `fetch(since, limit)` 介面，後續可接社群/新聞 API。
- `InMemorySentimentAdapter`：測試與本地原型用，確保 deterministic 行為。

## 2) Scoring Pipeline

- `KeywordSentimentScorer`：
  - 正負關鍵字命中（lexicon-based）
  - source 權重（news > social > forum）
  - 時效衰減（近期資料權重較高）
- `SentimentPipeline`：串接 adapter + scorer，輸出 `SentimentSnapshot`：
  - `score`：[-1, 1]
  - `confidence`：[0, 1]
  - `positive_hits` / `negative_hits` / `sample_size`

## 3) Integration Point（不破壞既有流程）

- `AdaptiveParameterController` 新增可選整合：
  - `enable_sentiment_overlay=False`（預設關閉）
  - `sentiment_pipeline` 可注入
- 開啟後會把 sentiment 對應為 reward penalty/bonus（confidence 加權），並在 `AdaptiveDecision` 暴露：
  - `sentiment_score`
  - `sentiment_confidence`

> 預設不開啟，確保既有策略流程與回測結果不受影響。

## 下一步建議

- 新增實際資料 adapter（X/Reddit/新聞 API）與 rate-limit/backoff。
- 依 symbol/topic 做資料過濾，避免跨資產噪音。
- 逐步替換 keyword scorer 為 embedding/LLM classifier，並加上 drift monitoring。
