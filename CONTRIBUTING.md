# Contributing

Thanks for helping. The most useful contributions are new questions and new tools.

## Setup

```bash
uv sync
uv run pytest
```

Before opening a PR, run `uv run ruff check .`, `uv run ruff format .` and `uv run pytest`.
CI runs the same checks.

## Adding a question

A question is one real API change. To keep the benchmark credible, it must:

1. **Come from a primary source.** Release notes, a merged PR, a migration guide, or the
   library's source code. Put the link in `source_url`. Blog posts and tutorials don't count.
2. **Be current.** The old API is deprecated or removed in the latest release.
3. **Have distinct old and new tokens**, so a regex can tell them apart.
4. **Not give the answer away.** The question can't contain the old or new API.

To find candidates, run:

```bash
uv run driftbench candidates --since 2026-11-01
```

Then add an entry to the current file in `data/questions/`:

| Field | What goes in it |
| --- | --- |
| `id` | `library-short-description`, lowercase |
| `library`, `repo` | Display name, and the GitHub `owner/repo` |
| `version`, `release_date` | The first release with the change |
| `old_api`, `new_api` | Human-readable summary of each |
| `old_patterns`, `new_patterns` | Python regexes matching code that uses each API |
| `question`, `question_with_version` | What a developer would ask, without and with the version |
| `source_url` | The primary source |
| `notes` | Optional: anything a reviewer should know |

Finally, add an outdated and a current code sample for your question to `SNIPPETS` in
[tests/test_questions.py](tests/test_questions.py). The tests check that your regexes label
them correctly and that the question doesn't contain either API.

## Adding a tool

Add a class to [src/driftbench/tools/](src/driftbench/tools/) that subclasses `Tool`:

- `name`: the short name used in results.
- `available()`: return `(False, reason)` when a required API key is missing, so the tool is
  skipped instead of failing.
- `ask(q, query, variant)`: return a `ToolResponse` whose `text` is exactly what an agent would
  read. Wrap the call in `timed()` so latency and errors are recorded.

For an MCP server, use `McpClient` from [tools/mcp.py](src/driftbench/tools/mcp.py) instead of
writing the protocol again.

Register it in [src/driftbench/tools/\_\_init\_\_.py](src/driftbench/tools/__init__.py). Call
the tool the way its own MCP server or SDK does, and explain any non-default settings in the
module docstring.

Add offline tests to [tests/test_tools.py](tests/test_tools.py) that check the request your
adapter sends and how it reads the service's documented response, and add the tool to
[tests/test_live.py](tests/test_live.py).

## Disputing a result

If you think a label is wrong, open an issue with the question id, the tool, and what the tool
returned. Raw output isn't committed, so you can regenerate it with
`driftbench run --only <id> --tools <tool>`. Tool vendors are welcome to respond, too.
