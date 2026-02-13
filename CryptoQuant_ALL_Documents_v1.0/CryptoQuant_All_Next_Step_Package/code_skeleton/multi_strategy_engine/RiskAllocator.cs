namespace CryptoQuant.Strategies;

using CryptoQuant.Core;

/// <summary>
/// Combines multiple strategy target signals into a single portfolio target per symbol.
/// Recommended policy for v2.x: risk-budgeted weighted sum with caps.
/// </summary>
public sealed class RiskAllocator
{
    private readonly Dictionary<string, StrategyBudget> _budgets;

    public RiskAllocator(IEnumerable<StrategyBudget> budgets)
    {
        _budgets = budgets.ToDictionary(b => b.StrategyName, b => b, StringComparer.OrdinalIgnoreCase);
    }

    /// <summary>
    /// Combine targets from strategies.
    /// Input: strategyTargets[strategyName][symbol] = targetQty
    /// Output: combinedTargets[symbol] = targetQty
    /// </summary>
    public Dictionary<string, decimal> Combine(
        IReadOnlyDictionary<string, IReadOnlyDictionary<string, decimal>> strategyTargets,
        FuturesPortfolio pf,
        IReadOnlyDictionary<string, decimal> lastPrice)
    {
        var combined = new Dictionary<string, decimal>(StringComparer.OrdinalIgnoreCase);

        foreach (var (stratName, perSym) in strategyTargets)
        {
            if (!_budgets.TryGetValue(stratName, out var b)) continue;

            foreach (var (sym, tgt) in perSym)
            {
                if (!combined.ContainsKey(sym)) combined[sym] = 0m;
                combined[sym] += tgt * b.Weight;
            }
        }

        // Optional: cap by portfolio max notional (simplified)
        var maxNotional = pf.AccountEquity() *  pf.MaxNotionalToEquityCap; // set from hot params
        foreach (var sym in combined.Keys.ToList())
        {
            if (!lastPrice.TryGetValue(sym, out var px) || px <= 0) continue;
            var notional = Math.Abs(combined[sym]) * px;
            if (notional > maxNotional && maxNotional > 0)
            {
                var scale = maxNotional / notional;
                combined[sym] *= scale;
            }
        }

        return combined;
    }
}