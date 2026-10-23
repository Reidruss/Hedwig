# Hedwig

A .NET 10 console assistant using Microsoft Agent Framework, a local Ollama model,
and Playwright Chromium for web research. The agent chooses when to search and
read pages; ordinary questions do not launch a browser.

## Setup

Install the .NET 10 SDK and [Ollama](https://ollama.com/), then start Ollama and
pull a model that supports tool calling:

```bash
ollama serve
# In another terminal:
ollama pull qwen3.5:4b

dotnet build Hedwig.sln
dotnet run --project Hedwig --no-build -- --install-browser
dotnet run --project Hedwig --no-build
```

If Ollama is already running, skip `ollama serve`. On Linux, if Chromium reports
missing system libraries, install Playwright's dependencies using the generated
script (requires PowerShell and may request administrator privileges):

```bash
pwsh Hedwig/bin/Debug/net10.0/playwright.ps1 install-deps chromium
```

## Use

Enter prompts repeatedly. Conversation history (including research tool results)
is kept in memory until `/reset`, a failed request, or exit.

```text
You: Explain what a heat pump does.
You: Research recent heat pump developments and cite the sources you read.
You: Compare those with conventional air conditioning.
You: /reset
You: /exit
```

- `/exit`, end of input, or Ctrl+C stops the application.
- `/reset` starts a fresh conversation.
- `--show-browser` makes Chromium visible during research.
- `OLLAMA_ENDPOINT` overrides `http://localhost:11434/`.
- `OLLAMA_MODEL_NAME` overrides `qwen3.5:4b`.

For example:

```bash
OLLAMA_MODEL_NAME=qwen3.5:9b dotnet run --project Hedwig -- --show-browser
```

The model must support native tool calling to use research. `SearchWeb` queries
Bing through Playwright, with DuckDuckGo and DuckDuckGo HTML as fallbacks,
and returns up to five results. It waits for result links to populate, decodes
Bing redirect links into source URLs, and logs provider failures to the console. `ReadPage` returns
the source URL, title, and up to 12,000 characters of visible text. Research is
limited to six browser operations and eight model tool iterations per prompt.
Search providers can block browser automation; if all fail, the agent receives
the individual failures and is instructed to read a known authoritative site
directly, without treating a search failure as evidence that information does
not exist. Each turn includes the system clock and time zone so the model can
interpret dates relative to today. Dynamic pages, PDFs, paywalls,
and login pages may not yield useful text. Use `/reset` for a fresh topic if the
conversation grows too long for your model's context window.

Model inference runs through your configured Ollama server. Web searches and page
visits use the internet. Browsing uses a fresh browser context per tool call.

To diagnose live search independently of the model:

```bash
dotnet run --project Hedwig -- --search Memphis Tennessee weather forecast
```

This prints actual search results or per-provider errors. It requires internet
access and Chromium, but no Ollama connection. Search results still need to be
checked for relevance and read before using them as evidence.

## Verification

```bash
dotnet build Hedwig.sln
python3 tests/smoke.py
# Also verify real Chromium page reading against a local test page:
python3 tests/smoke.py --browser
# Browser search regression tests (403 fallback, dynamic results, URL decoding):
dotnet run --project tests/Hedwig.Tests
```

The integration tests use a temporary local mock Ollama server to check streaming,
conversation history, reset, EOF, tool execution, and recovery after server errors.
They do not download or require a model. The browser test additionally requires
Chromium from the setup step. Live research quality depends on the selected model
and availability of source websites.

Integration follows Microsoft's [Ollama provider](https://learn.microsoft.com/en-us/agent-framework/agents/providers/ollama)
and [function tools](https://learn.microsoft.com/en-us/agent-framework/agents/tools/function-tools)
APIs. Browser setup follows [Playwright's browser installation documentation](https://playwright.dev/dotnet/docs/browsers).
