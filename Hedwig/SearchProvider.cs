namespace Hedwig;

internal sealed record SearchProvider(
    string Name, string UrlTemplate, string ResultSelector, string LinkSelector, string SnippetSelector)
{
    public static IReadOnlyList<SearchProvider> Defaults { get; } =
    [
        new("Bing", "https://www.bing.com/search?q={query}", "li.b_algo", "h2 a", ".b_caption p"),
        new("DuckDuckGo", "https://duckduckgo.com/?q={query}&ia=web", "[data-testid='result']",
            "a[data-testid='result-title-a']", "[data-result='snippet']"),
        new("DuckDuckGo HTML", "https://html.duckduckgo.com/html/?q={query}", ".result", ".result__a", ".result__snippet")
    ];
}
