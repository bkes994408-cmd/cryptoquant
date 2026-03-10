# cryptoquant

Minimal event-driven scaffold for a future Paper/Backtest engine.

## Risk Manager（MVP-8）

`RiskManager` 目前支援以下高級風控能力：

- `notional_cap` / `leverage_cap` 倉位上限控制
- `daily_stop_drawdown_pct` 每日回撤停手
- `warn_utilization_pct` 實時接近上限預警（WARN）
- `dynamic_stop.trailing_pct` 動態停損（trailing stop）

### Dynamic Stop 行為

- Long：追蹤有利方向最高價，當 `price <= extreme * (1 - trailing_pct)` 觸發
- Short：追蹤有利方向最低價，當 `price >= extreme * (1 + trailing_pct)` 觸發
- 觸發後若策略仍要求「同向維持/加碼」，風控會強制 `target_qty = 0`
- 觸發後若策略要求同向減倉，仍允許執行
- 平倉或換向後，trailing 狀態會重置

### 參數約束

- `warn_utilization_pct` 必須在 `(0, 1)`
- `dynamic_stop.trailing_pct` 必須在 `(0, 1)`

### Alert Codes

- `risk.notional.near_cap`
- `risk.leverage.near_cap`
- `risk.daily_stop.triggered`
- `risk.dynamic_stop.triggered`
- `risk.dynamic_stop.enforced`
