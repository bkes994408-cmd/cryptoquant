# Portfolio Risk Model (Implementation Notes)

## Inputs you need

- Equity time series (at least per minute or per bar)
- Realized volatility estimate (EWMA or rolling std of returns)
- Correlation clusters (optional): e.g., majors vs alts; or learned clusters

## Outputs

- Global risk multiplier (0..1) applied to *all* strategy targets
- Optional per-cluster caps (future)

## Recommended MVP behavior

- If drawdown >= MaxDrawdown: trip kill switch and stop trading
- Else: scale targets by multiplier, and re-check exposure caps
