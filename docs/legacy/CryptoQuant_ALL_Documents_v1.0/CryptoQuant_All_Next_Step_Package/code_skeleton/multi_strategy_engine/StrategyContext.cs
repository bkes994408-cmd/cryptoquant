namespace CryptoQuant.Strategies;

using CryptoQuant.Core;

/// <summary>
/// Immutable context passed to strategies each bar.
/// Keep it read-only to prevent hidden coupling.
/// </summary>
public sealed record StrategyContext(
    DateTime TsUtc,
    IReadOnlyDictionary<string, decimal> LastPrice,
    PortfolioState Portfolio,
    RuntimeParams Params
);

/// <summary>
/// Runtime parameters for hot reload.
/// Keep it small; extend as needed.
/// </summary>
public sealed record RuntimeParams(
    decimal RiskPctPerTrade,
    decimal MaxLeverage,
    decimal MaxNotionalToEquity
);