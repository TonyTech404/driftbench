# driftbench

[![CI](https://github.com/TonyTech404/driftbench/actions/workflows/ci.yml/badge.svg)](https://github.com/TonyTech404/driftbench/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

**Do AI documentation tools give coding agents the current API, or the outdated one?**

Coding agents lean on documentation tools (Context7, DeepWiki, web search) to look up libraries they
weren't trained on. When a library renames or deprecates an API, those tools can keep serving the
old version, and the agent writes code that is already out of date.

driftbench measures that. Every question comes from a real API change in a 2026 release, checked
against the library's own release notes, PRs or source. Each tool gets the same questions, and
its answer is labeled by which API its code uses.

> Status: prototype. 23 questions, 9 libraries, 3 tools, plus an agent baseline. See
> [Roadmap](#roadmap).

## Results (November 2026)

### What an agent writes with each tool

The headline test. Claude Code (Sonnet 5, headless) answers each question with exactly one
documentation tool over MCP, or none, and the code it writes is labeled. Run once per question
on 2026-11-12, without naming the version.

| Agent setup | Current | Mixed | Stale | Used its tool | Median time |
| --- | --- | --- | --- | --- | --- |
| + DeepWiki | **19/23 (83%)** | 1/23 (4%) | 3/23 (13%) | 23/23 | 19.2 s |
| + Exa | 17/23 (74%) | 3/23 (13%) | 3/23 (13%) | 23/23 | 10.5 s |
| + Context7 | 14/23 (61%) | 1/23 (4%) | 7/23 (30%) | 23/23 | 13.7 s |
| No tool | 2/23 (9%) | 1/23 (4%) | 14/23 (61%) | – | 7.8 s |

What stands out:

- **Any tool helps a lot.** Without one, the agent wrote outdated code for 14 of 23 changes
  and current code for only 2.
- **Knowing isn't using.** On Polars `qcut`, the DeepWiki agent noted that `qcut` is
  deprecated in favor of `bin_quantiles`, then wrote `qcut` anyway.
- **The agent's own lookup matters.** Asked directly, DeepWiki answers the TanStack prefetch
  question with the current `queryClient.query()`. The agent asked DeepWiki its own question
  and wrote the deprecated `prefetchQuery`. All four setups got this one wrong.
- **Exa does far better through an agent than its raw output suggests,** because the agent
  picks the current API out of whole pages that show both.

Full per-question table: [results/2026-11-agent.md](results/2026-11-agent.md).

### What each tool returns directly

The same questions sent straight to each tool, labeling the code in what it returns.

| Tool | Current | Mixed | Stale | First snippet stale | Median size | Median latency |
| --- | --- | --- | --- | --- | --- | --- |
| DeepWiki (MCP) | 22/23 (96%) | 0/23 | 0/23 | 0/23 | 1.2k chars | 11.3 s |
| Context7 | 12/23 (52%) | 5/23 (22%) | 3/23 (13%) | 6/23 (26%) | 3.8k chars | 3.8 s |
| Exa (MCP) | 4/23 (17%) | 15/23 (65%) | 4/23 (17%) | 6/23 (26%) | 22.8k chars | 0.7 s |

Naming the library version in the question changed little. DeepWiki went from 22 to 21
current and Context7 stayed at 12. Exa went from 4 to 7, and its first-snippet-stale count
dropped from 6 to 2.

The tools return different things, which is why the agent test above is the fairer comparison:

- **DeepWiki** returns a short answer an LLM wrote from the repository's current source code.
- **Context7** returns documentation excerpts, often from several versions.
- **Exa** returns whole web pages, about 20 times more text than DeepWiki, so it often contains
  both the old and the new API.

Full per-question table: [results/2026-11.md](results/2026-11.md).

### Corrections

- **2026-11-12.** Removed `nextjs-prefetch-allow-runtime`. The `force-runtime` → `allow-runtime`
  rename only existed in pre-release builds; no stable Next.js release accepts either value,
  so the question broke its own rules. Also fixed a labeling bug: a code line such as
  `runtime = 'nodejs' // or 'edge' (deprecated)` was ignored entirely, instead of counting the
  current API it recommends. Agent results moved from 18/24 to 19/23 current with DeepWiki,
  16/24 to 17/23 with Exa, and 14/24 to 14/23 with Context7. Found while answering a reader's
  question.

## How it works

1. **Find changes.** `driftbench candidates` reads GitHub release notes for the libraries in
   [data/libraries.json](data/libraries.json) and flags renames, deprecations and replacements.
2. **Write questions.** Each confirmed change becomes a question that a developer would ask,
   without naming the old or new API. Every question records its source and two regex sets:
   one for the outdated API and one for the current API.
3. **Ask the tools.** `driftbench run` sends each question twice, once plain and once naming the
   library version, to every tool, the same way an agent's MCP client would call it.
4. **Label the answers.** Labels use the **code** in the answer, because that's what an agent
   copies. A note like "`app.mount()` is deprecated, use `mount()`" is a good answer, so the old
   API in prose doesn't count against a tool.

| Label | Meaning |
| --- | --- |
| current | the code uses only the new API |
| mixed | the code shows both, so the agent has to guess |
| stale | the code uses only the outdated API |
| neither | the answer has no code for either API |

The report also counts **first snippet stale**: answers whose first relevant code block uses the
outdated API, since that's the one an agent is most likely to use.

### Question rules

- The change shipped in a 2026 release and is confirmed in a primary source (release notes,
  merged PR, or the library's source code). The link is in `source_url`.
- The old API is deprecated or removed in the latest release, and old and new are distinct tokens.
- The question doesn't contain either API. A test enforces this.
- Every question has an outdated and a current code sample in
  [tests/test_questions.py](tests/test_questions.py), and CI checks that the regexes label them
  correctly.

## Tools

| Tool | How it's called | Key needed |
| --- | --- | --- |
| `context7` | Context7 API: resolve the library, then fetch docs for the question (what its MCP server does) | No (optional `CONTEXT7_API_KEY` for higher limits) |
| `deepwiki` | DeepWiki's public MCP server, `ask_wiki_question` on the library's GitHub repo | No |
| `exa-mcp` | Exa's hosted MCP server, `web_search_exa` with defaults (how agents usually reach Exa) | No (optional `EXA_API_KEY`) |
| `exa` | Exa search API, `type: auto` with highlights; records Exa's cost estimate | `EXA_API_KEY` |

Tools without a key are skipped, not failed. Adding a tool means writing one class with an `ask()`
method in [src/driftbench/tools/](src/driftbench/tools/).

## Run it

```bash
uv sync
uv run pytest                                   # offline: patterns, labeling, tool adapters
uv run driftbench run --questions data/questions/2026-11.json --out results/2026-11.jsonl
uv run driftbench report --questions data/questions/2026-11.json \
  --results results/2026-11.jsonl --out results/2026-11.md
```

`DRIFTBENCH_LIVE=1 uv run pytest tests/test_live.py` also checks each adapter against the real
service.

Runs resume where they stopped. After changing how labels work, re-label saved output without
calling the tools again:

```bash
uv run driftbench relabel --questions data/questions/2026-11.json --results results/2026-11.jsonl
```

Raw tool output goes to `results/raw/` and isn't committed, because it contains other sites'
content.

To look for new changes since a date:

```bash
uv run driftbench candidates --since 2026-11-01
```

### Agent mode

Needs [Claude Code](https://docs.claude.com/en/docs/claude-code) installed and logged in, with
either a Claude subscription or `ANTHROPIC_API_KEY`. Each row records which one was used.

```bash
uv run driftbench agent --questions data/questions/2026-11.json --out results/2026-11-agent.jsonl
```

`--setups` picks from `none`, `context7`, `deepwiki` and `exa` (default: all), and `--model`
is passed to `claude --model` (default: `sonnet`). The full set is 96 runs, about $3 at API
prices. If a usage limit is reached, the run stops cleanly, and rerunning resumes it.

## Limitations

- **Small set.** 23 questions is enough to show differences, not to rank tools precisely.
- **Regex labels.** They're checked against samples, but an unusual answer can still be
  mislabeled. Raw outputs can be regenerated to audit any label.
- **One run per question.** Tool output can vary between runs; use `--runs 2` or more.
- **The `exa` API adapter has no results yet.** It needs a paid key, so it's tested only
  against simulated responses in Exa's documented format. `exa-mcp` covers Exa in the results.
- **One agent, one model.** Agent results are Claude Code with Sonnet 5. Other agents and
  models may use the same tools differently.
- **Questions picked by hand.** The extractor finds candidates, but a person confirms each change
  and writes the question.
- **Docs can lag too.** If a library's own docs still show the old API, a tool that copies them
  will look stale.

## Roadmap

- [ ] Monthly run in GitHub Actions, with results committed
- [ ] Draft questions from candidates with an LLM, with human review
- [x] Agent mode: Claude Code with each tool, plus a no-tool baseline
- [ ] Agent mode with other agents and models
- [ ] More tools: Firecrawl, GitHub MCP, plain web search
- [ ] Public leaderboard page

## Prior work

- [Context7 vs Exa](https://github.com/enesakar/context7-vs-exa-benchmark), a freshness
  benchmark by the Context7 team. driftbench uses a similar labeling idea, built independently
  and covering more tools.
- [LibEvoBench](https://arxiv.org/abs/2606.25402) and [GitChameleon](https://arxiv.org/abs/2411.05830)
  test whether models know version-specific APIs. driftbench tests the documentation tools
  agents use to look them up.

## Contributing

New questions and tools are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT
