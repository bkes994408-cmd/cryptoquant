# cryptoquant

Minimal event-driven scaffold for a future Paper/Backtest engine.

## Risk Manager（MVP-8）

`RiskManager` 支援：

- `notional_cap` / `leverage_cap` 倉位上限
- `daily_stop_drawdown_pct` 每日回撤停手
- `warn_utilization_pct` 風險利用率預警閾值（`0 < x < 1`）
- `dynamic_stop.trailing_pct` 動態停損回撤比例（`0 < x < 1`）

### Dynamic stop 行為

- Long：追蹤最高價，當 `price <= extreme * (1 - trailing_pct)` 觸發
- Short：追蹤最低價，當 `price >= extreme * (1 + trailing_pct)` 觸發
- 觸發後若策略要求同向維持/加碼，風控強制 `target_qty = 0`
- 觸發後若策略要求同向減倉，允許執行
- 平倉或換向後，trailing 狀態重置
- 目前無 cooldown

### Alert codes

- `risk.notional.near_cap`
- `risk.leverage.near_cap`
- `risk.daily_stop.triggered`
- `risk.dynamic_stop.triggered`
- `risk.dynamic_stop.enforced`

### 告警節流 / 去重

`near_cap` 告警採閾值穿越觸發：

- 利用率首次上穿閾值時發送
- 持續高於閾值不重複發送
- 回落後再次上穿才重送
