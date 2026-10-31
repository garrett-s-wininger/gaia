using System;
using System.Collections.Generic;
using System.Collections.Immutable;
using System.Linq;

namespace GaiaFixture;
public record Reading(string Name, int Value);
public static class Statistics
{
    public static ImmutableArray<Reading> Select(IEnumerable<Reading> source) =>
        source.Where(item => item.Value >= 0).OrderBy(item => item.Name).ToImmutableArray();
    public static int Sum(ReadOnlySpan<int> values)
    {
        var result = 0;
        foreach (var value in values) result += value;
        return result;
    }
}
