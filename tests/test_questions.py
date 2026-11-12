"""Every question's patterns must tell a realistic old snippet from a realistic new one.

If a question is added without an entry here, the test fails, so patterns never ship untested.
"""

from pathlib import Path

import pytest

from driftbench.label import CURRENT, MIXED, NEITHER, STALE, label_response, label_text
from driftbench.questions import load_questions

QUESTIONS = load_questions(Path(__file__).parent.parent / "data/questions/2026-11.json")

# id: (snippet using the outdated API, snippet using the current API)
SNIPPETS = {
    "fastapi-root-path": (
        'app = FastAPI(root_path="/api/v1")',
        "fastapi run main.py --root-path /api/v1",
    ),
    "hono-mount": (
        "app.mount('/itty-router', ittyRouter.handle)",
        "import { mount } from 'hono/mount'\napp.all('/itty-router/*', mount(ittyRouter.handle))",
    ),
    "hono-bun-adapter": (
        "import { serveStatic } from 'hono/bun'",
        "import { serveStatic } from '@hono/bun'",
    ),
    "hono-aws-lambda-adapter": (
        "import { handle } from 'hono/aws-lambda'",
        'import { handle } from "@hono/aws-lambda"',
    ),
    "hono-lambda-edge-adapter": (
        "import { handle } from 'hono/lambda-edge'",
        "import { handle } from '@hono/lambda-edge'",
    ),
    "hono-deno-adapter": (
        "import { serveStatic } from 'jsr:@hono/hono/deno'",
        "import { serveStatic } from 'jsr:@hono/deno'",
    ),
    "polars-cut": (
        'df.with_columns(pl.col("x").cut([1, 5, 10]))',
        'df.with_columns(pl.col("x").bin_intervals([1, 5, 10]))',
    ),
    "polars-qcut": (
        'pl.col("x").qcut(4)',
        'pl.col("x").bin_quantiles(4)',
    ),
    "polars-concat-horizontal-extend": (
        'pl.concat([a, b], how="horizontal")',
        'pl.concat([a, b], how="horizontal_extend")',
    ),
    "polars-csv-empty-string-is-null": (
        'pl.read_csv("f.csv", missing_utf8_is_empty_string=True)',
        'pl.read_csv("f.csv", empty_string_is_null=False)',
    ),
    "tanstack-prefetch-query": (
        "await queryClient.prefetchQuery({ queryKey: ['posts'], queryFn })",
        "await queryClient.query({ queryKey: ['posts'], queryFn }).catch(noop)",
    ),
    "tanstack-fetch-query": (
        "const data = await queryClient.fetchQuery({ queryKey, queryFn })",
        "const data = await queryClient.query({ queryKey, queryFn })",
    ),
    "tanstack-ensure-query-data": (
        "loader: () => queryClient.ensureQueryData(postsQuery)",
        "loader: () => queryClient.query({ ...postsQuery, staleTime: 'static' })",
    ),
    "tanstack-infinite-query": (
        "await queryClient.prefetchInfiniteQuery({ queryKey, queryFn, initialPageParam: 0 })",
        "await queryClient.infiniteQuery({ queryKey, queryFn, initialPageParam: 0 })",
    ),
    "nextjs-use-cache-flag": (
        "const nextConfig = { experimental: { useCache: true } }",
        "const nextConfig = { cacheComponents: true }",
    ),
    "nextjs-edge-runtime": (
        "export const runtime = 'edge'",
        "export const runtime = 'nodejs'",
    ),
    "nextjs-prefetch-allow-runtime": (
        "export const prefetch = 'force-runtime'",
        "export const prefetch = 'allow-runtime'",
    ),
    "playwright-record-video": (
        "const context = await browser.newContext({ videosPath: 'videos/' })",
        "const context = await browser.newContext({ recordVideo: { dir: 'videos/' } })",
    ),
    "playwright-console-location": (
        "const { url, lineNumber, columnNumber } = msg.location()",
        "const { url, line, column } = msg.location()",
    ),
    "playwright-screencast-style": (
        "await page.screencast.showActions({ fontSize: 24 })",
        "await page.screencast.showActions({ style: 'font-size: 24px' })",
    ),
    "react-types-submit-event": (
        "const onSubmit = (e: React.FormEvent<HTMLFormElement>) => {}",
        "const onSubmit = (e: React.SubmitEvent<HTMLFormElement>) => {}",
    ),
    "transformers-rope-parameters": (
        'config.rope_scaling = {"rope_type": "yarn", "factor": 4.0}',
        'config.rope_parameters = {"rope_type": "yarn", "factor": 4.0}',
    ),
    "transformers-paged-attention-prefix": (
        'model = AutoModelForCausalLM.from_pretrained(name, attn_implementation="paged|sdpa")',
        'model = AutoModelForCausalLM.from_pretrained(name, attn_implementation="sdpa")',
    ),
    "langchain-chat-message-history": (
        "history = InMemoryChatMessageHistory()\nchain = RunnableWithMessageHistory(runnable, get_history)",
        "agent = create_agent(model, tools, checkpointer=InMemorySaver())",
    ),
}


def test_every_question_has_snippets():
    assert {q.id for q in QUESTIONS} == set(SNIPPETS)


@pytest.mark.parametrize("q", QUESTIONS, ids=lambda q: q.id)
def test_patterns_separate_old_from_new(q):
    old, new = SNIPPETS[q.id]
    assert label_text(q, old).label == STALE, label_text(q, old)
    assert label_text(q, new).label == CURRENT, label_text(q, new)
    assert label_text(q, old + "\n" + new).label == MIXED
    assert label_text(q, "unrelated text").label == NEITHER


def test_inline_deprecation_comment_keeps_the_current_api():
    # From a real agent answer: the line recommends nodejs and only mentions edge as deprecated.
    q = next(q for q in QUESTIONS if q.id == "nextjs-edge-runtime")
    text = "```ts\nexport const runtime = 'nodejs' // or 'edge' (deprecated)\n```"
    assert label_response(q, text).code.label == CURRENT


@pytest.mark.parametrize("q", QUESTIONS, ids=lambda q: q.id)
def test_question_does_not_leak_the_answer(q):
    # A question that names the new or old API would test reading, not retrieval.
    for text in (q.question, q.question_with_version):
        assert label_text(q, text).label == NEITHER, text
