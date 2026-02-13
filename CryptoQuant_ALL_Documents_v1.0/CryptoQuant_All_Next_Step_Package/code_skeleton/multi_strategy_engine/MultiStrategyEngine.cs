namespace CryptoQuant.Strategies;

using CryptoQuant.Core;

/// <summary>
/// Multi-strategy engine:
/// - Runs N strategy plugins
/// - Collects per-strategy target signals
/// - Combines into final target via RiskAllocator
/// </summary>
public sealed class MultiStrategyEngine
{
    private readonly IReadOnlyList<IStrategyPlugin> _plugins;
    private readonly RiskAllocator _allocator;

    // per-strategy per-symbol targets (updated each main bar)
    private readonly Dictionary<string, Dictionary<string, decimal>> _targets =
        new(StringComparer.OrdinalIgnoreCase);

    public MultiStrategyEngine(IEnumerable<IStrategyPlugin> plugins, RiskAllocator allocator, string[] symbols)
    {
        _plugins = plugins.ToList();
        _allocator = allocator;

        foreach (var p in _plugins)
        {
            p.Initialize(symbols);
            _targets[p.Name] = new Dictionary<string, decimal>(StringComparer.OrdinalIgnoreCase);
        }
    }

    public void OnFilterBar(string symbol, Bar bar, StrategyContext ctx)
    {
        foreach (var p in _plugins)
            p.OnFilterBar(symbol, bar, ctx);
    }

    /// <summary>
    /// Call on each main timeframe bar close for each symbol.
    /// Returns final combined target for that symbol.
    /// </summary>
    public decimal OnMainBar(string symbol, Bar bar, StrategyContext ctx, FuturesPortfolio pf)
    {
        foreach (var p in _plugins)
        {
            var tgt = p.OnMainBar(symbol, bar, ctx);
            _targets[p.Name][symbol] = tgt;
        }

        // Build read-only snapshot
        var snapshot = _targets.ToDictionary(
            kv => kv.Key,
            kv => (IReadOnlyDictionary<string, decimal>)kv.Value,
            StringComparer.OrdinalIgnoreCase);

        var combined = _allocator.Combine(snapshot, pf, ctx.LastPrice);
        return combined.TryGetValue(symbol, out var v) ? v : 0m;
    }
}