namespace CryptoQuant.Risk;

using CryptoQuant.Core;

/// <summary>
/// Portfolio-level risk controls (skeleton).
/// Provide three levers:
/// 1) Volatility targeting (scale total exposure)
/// 2) Correlation-aware exposure caps (per-cluster)
/// 3) Drawdown-based de-risk (step down risk when DD grows)
/// </summary>
public sealed class PortfolioRiskController
{
    public decimal TargetDailyVol { get; init; } = 0.02m; // 2% daily target (example)
    public decimal MaxDrawdown { get; init; } = 0.10m;    // 10% max DD (example)

    /// <summary>
    /// Returns a risk multiplier in [0,1]. Multiply all targets by this.
    /// </summary>
    public decimal RiskMultiplier(EquityCurve curve, decimal realizedDailyVol)
    {
        var dd = curve.MaxDrawdownPct();
        if (dd >= MaxDrawdown) return 0m; // stop / flatten in your engine

        // Drawdown de-risk (linear)
        var ddMult = 1m - (dd / MaxDrawdown); // 1 -> 0 as dd approaches max

        // Vol targeting multiplier
        var volMult = realizedDailyVol <= 0 ? 1m : Clamp(TargetDailyVol / realizedDailyVol, 0.25m, 2.0m);

        // Final cap to [0,1] for safety (you can allow >1 if desired)
        return Clamp(ddMult * volMult, 0m, 1m);
    }

    private static decimal Clamp(decimal v, decimal lo, decimal hi) => Math.Min(Math.Max(v, lo), hi);
}

/// <summary>
/// Minimal equity curve helper.
/// Replace with DB-backed implementation later.
/// </summary>
public sealed class EquityCurve
{
    private readonly List<(DateTime tsUtc, decimal equity)> _pts = new();

    public void Add(DateTime tsUtc, decimal equity) => _pts.Add((tsUtc, equity));

    public decimal MaxDrawdownPct()
    {
        if (_pts.Count < 2) return 0m;
        decimal peak = _pts[0].equity;
        decimal maxDd = 0m;
        foreach (var p in _pts)
        {
            peak = Math.Max(peak, p.equity);
            if (peak <= 0) continue;
            var dd = (peak - p.equity) / peak;
            maxDd = Math.Max(maxDd, dd);
        }
        return maxDd;
    }
}