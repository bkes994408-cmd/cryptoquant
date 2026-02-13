# Multi-Strategy Engine Skeleton

## How to integrate
- Replace your single strategy instance with `MultiStrategyEngine`
- Keep `FuturesEngine` responsible for:
  - Risk checks
  - Flip splitting
  - OMS idempotency
- `MultiStrategyEngine` only decides **targets**, not how to execute.

## Minimal wiring
1) Build plugins list: `new IStrategyPlugin[]{ new DualRegimeStrategyPlugin(...), new BreakoutPlugin(...) }`
2) Define budgets: weights and caps
3) Create `RiskAllocator(budgets)` and `MultiStrategyEngine(plugins, allocator, symbols)`
4) In engine loop: forward filter bars and main bars, then use returned targetQty for existing execution flow