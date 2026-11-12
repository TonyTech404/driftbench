# driftbench

**Do AI documentation tools give coding agents the current API, or the outdated one?**

Coding agents lean on documentation tools (Context7, DeepWiki, web search) to look up libraries they
weren't trained on. When a library renames or deprecates an API, those tools can keep serving the
old version, and the agent writes code that is already out of date.

driftbench measures that. Every question comes from a real API change in a 2026 release, checked
against the library's own release notes, PRs or source. Each tool gets the same questions, and
its answer is labeled by which API its code uses.

> Status: prototype. 24 questions, 9 libraries, 2 tools (plus Exa with an API key). See [Roadmap](#roadmap).

## Results (November 2026)

24 questions, run once on 2026-11-12. Labels use the code in each answer.

| Tool | Current | Mixed | Stale | First snippet stale | Median latency |
| --- | --- | --- | --- | --- | --- |
| DeepWiki (MCP) | 22/24 (92%) | 0/24 | 0/24 | 0/24 | 11.3 s |
| Context7 | 12/24 (50%) | 5/24 (21%) | 3/24 (12%) | 6/24 (25%) | 3.8 s |

Naming the library version in the question didn't help either tool: Context7 got 12/24 current
both ways, and DeepWiki went from 22 to 21.

**Read this carefully before quoting it.** The two tools return different things. DeepWiki
returns an answer an LLM wrote from the repository's current source code. Context7 returns
documentation excerpts, often several versions' worth, which an agent then has to choose
between. So "mixed" from Context7 often means "the right answer is in there, next to the old
one", and an agent may or may not pick the right one. Agent mode (see the roadmap) will
measure that directly by labeling the code a model writes after using each tool.

Full per-question table: [results/2026-11.md](results/2026-11.md).

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
| `exa` | Exa search, `type: fast` with highlights | `EXA_API_KEY` |

Tools without a key are skipped, not failed. Adding a tool means writing one class with an `ask()`
method in [src/driftbench/tools/](src/driftbench/tools/).

## Run it

```bash
uv sync
uv run pytest                                   # checks every question's patterns
uv run driftbench run --questions data/questions/2026-11.json --out results/2026-11.jsonl
uv run driftbench report --questions data/questions/2026-11.json \
  --results results/2026-11.jsonl --out results/2026-11.md
```

Runs resume where they stopped. After changing how labels work, re-label saved output without
calling the tools again:

```bash
uv run driftbench relabel --questions data/questions/2026-11.json --results results/2026-11.jsonl
```

Raw tool output goes to `results/raw/` and isn't committed,
because it contains other sites' content.

To look for new changes since a date:

```bash
uv run driftbench candidates --since 2026-11-01
```

## Limitations

- **Small set.** 24 questions is enough to show differences, not to rank tools precisely.
- **Regex labels.** They're checked against samples, but an unusual answer can still be
  mislabeled. Raw outputs can be regenerated to audit any label.
- **One run per question.** Tool output can vary between runs; use `--runs 2` or more.
- **Questions picked by hand.** The extractor finds candidates, but a person confirms each change
  and writes the question.
- **Docs can lag too.** If a library's own docs still show the old API, a tool that copies them
  will look stale.

## Roadmap

- [ ] Monthly run in GitHub Actions, with results committed
- [ ] Draft questions from candidates with an LLM, with human review
- [ ] More tools: Exa results, Firecrawl, GitHub MCP, plain web search, no-tool baseline
- [ ] Agent mode: give a model each tool and label the code it writes
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
