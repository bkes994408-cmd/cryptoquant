namespace CryptoQuant.Strategies;

/// <summary>
/// Per-strategy risk budget. Used by RiskAllocator to scale strategy outputs.
/// </summary>
public sealed record StrategyBudget(
    string StrategyName,
    decimal Weight,          // 0..1
    decimal MaxNotionalShare // 0..1 (share of portfolio max notional)
);