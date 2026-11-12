from driftbench.label import CURRENT, MIXED, NEITHER, STALE, label_response
from driftbench.questions import Question

Q = Question.from_dict(
    {
        "id": "t",
        "library": "Hono",
        "repo": "honojs/hono",
        "version": "4.13.13",
        "release_date": "2026-10-04",
        "old_api": "app.mount",
        "new_api": "mount()",
        "old_patterns": [r"\.mount\s*\("],
        "new_patterns": [r"(?<![.\w])mount\s*\("],
        "question": "q",
        "question_with_version": "q",
        "source_url": "https://example.com",
    }
)


def test_deprecation_note_in_prose_does_not_count_against_code():
    text = (
        "Use the middleware:\n\n```ts\napp.all('/x/*', mount(h))\n```\n\n"
        "The older `app.mount('/x', h)` API is deprecated."
    )
    labs = label_response(Q, text)
    assert labs.code.label == CURRENT
    assert labs.first.label == CURRENT
    assert labs.text.label == MIXED


def test_first_relevant_block_is_reported():
    text = "```ts\nconst app = new Hono()\n```\n```ts\napp.mount('/x', h)\n```\n```ts\nmount(h)\n```"
    labs = label_response(Q, text)
    assert labs.first.label == STALE
    assert labs.code.label == MIXED


def test_falls_back_to_inline_code_without_fences():
    assert label_response(Q, "Call `app.mount('/x', h)`.").code.label == STALE
    assert label_response(Q, "Nothing relevant here.").code.label == NEITHER


def test_tilde_fences():
    assert label_response(Q, "~~~\nmount(h)\n~~~").code.label == CURRENT
