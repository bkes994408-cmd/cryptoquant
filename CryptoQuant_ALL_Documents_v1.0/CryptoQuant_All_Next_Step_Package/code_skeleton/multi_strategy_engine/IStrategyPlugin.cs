namespace CryptoQuant.Strategies;

using CryptoQuant.Core;

/// <summary>
/// Strategy plugin contract.
/// - Receives bars (main/filter) and current portfolio snapshot
/// - Outputs target position per symbol (can be + long, - short, 0 flat)
/// </summary>
public interface IStrategyPlugin
{
    string Name { get; }

    /// <summary>Optional: called once at startup with universe.</summary>
    void Initialize(string[] symbols);

    /// <summary>Filter timeframe bar (e.g., 1h). Use for regime detection.</summary>
    void OnFilterBar(string symbol, Bar bar, StrategyContext ctx);

    /// <summary>Main timeframe bar (e.g., 15m). Return desired target position (qty) for symbol.</summary>
    decimal OnMainBar(string symbol, Bar bar, StrategyContext ctx);
}