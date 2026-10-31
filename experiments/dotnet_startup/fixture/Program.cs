using System;
using System.Linq;
using System.Text.Json;
using GaiaFixture;

public static class Program
{
    public static void Main()
    {
        var selected = Statistics.Select(new[] { new Reading("beta", 2), new Reading("alpha", 1) });
        Console.WriteLine(JsonSerializer.Serialize(new {
            request = Request.Sequence,
            names = selected.Select(item => item.Name).ToArray(),
            sum = Statistics.Sum(new[] {1, 2, 3})
        }));
    }
}
