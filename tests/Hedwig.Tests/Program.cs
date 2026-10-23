using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Text.Json;
using Hedwig;

// A real Chromium test against controlled HTTP responses, requiring no external search service.
var socket = new TcpListener(IPAddress.Loopback, 0);
socket.Start();
var port = ((IPEndPoint)socket.LocalEndpoint).Port;
socket.Stop();
var origin = $"http://127.0.0.1:{port}";
using var listener = new HttpListener();
listener.Prefixes.Add(origin + "/");
listener.Start();
var visited = new List<string>();
var queries = new List<string?>();
var serving = Task.Run(async () =>
{
    while (listener.IsListening)
    {
        HttpListenerContext context;
        try { context = await listener.GetContextAsync(); }
        catch (Exception) when (!listener.IsListening) { break; }
        var path = context.Request.Url!.AbsolutePath;
        lock (visited)
        {
            visited.Add(path);
            queries.Add(context.Request.QueryString["q"]);
        }
        context.Response.StatusCode = path == "/blocked" ? 403 : 200;
        context.Response.ContentType = "text/html";
        var encoded = "a1" + Convert.ToBase64String(Encoding.UTF8.GetBytes("https://example.org/source")).TrimEnd('=').Replace('+', '-').Replace('/', '_');
        var html = path == "/results"
            ? $"<html><body><script>setTimeout(() => document.body.innerHTML = '<div class=\"result\"><h2><a href=\"https://www.bing.com/ck/a?u={encoded}\">Weather source</a></h2><p>Forecast evidence</p></div>', 100)</script></body></html>"
            : "<html><body>No results</body></html>";
        var bytes = Encoding.UTF8.GetBytes(html);
        await context.Response.OutputStream.WriteAsync(bytes);
        context.Response.Close();
    }
});

try
{
    SearchProvider Provider(string name, string path) => new(name, origin + path + "?q={query}", ".result", "h2 a", "p");
    await using (var research = new BrowserResearch(true, [Provider("Blocked", "/blocked"), Provider("Fallback", "/results")]))
    {
        var result = await research.SearchWeb("Memphis weather & forecast");
        using var json = JsonDocument.Parse(result);
        Assert(json.RootElement.GetProperty("provider").GetString() == "Fallback", "Uses fallback after HTTP 403");
        var source = json.RootElement.GetProperty("results")[0];
        Assert(source.GetProperty("url").GetString() == "https://example.org/source", "Decodes Bing redirect into source URL");
        Assert(source.GetProperty("snippet").GetString() == "Forecast evidence", "Waits for dynamically rendered results");
        Assert(visited.IndexOf("/blocked") < visited.IndexOf("/results"), "Attempts providers in order");
        Assert(queries.All(q => q == "Memphis weather & forecast"), "Preserves escaped search queries");
    }
    await using (var research = new BrowserResearch(true, [Provider("Blocked", "/blocked")]))
    {
        var result = await research.SearchWeb("weather");
        Assert(result.Contains("HTTP 403") && result.Contains("does not mean"), "Reports actual failures without inferring unavailable information");
    }
    Console.WriteLine("All search browser checks passed.");
}
finally
{
    listener.Stop();
    await serving;
}

static void Assert(bool condition, string description)
{
    if (!condition) throw new InvalidOperationException(description);
    Console.WriteLine($"PASS: {description}");
}
