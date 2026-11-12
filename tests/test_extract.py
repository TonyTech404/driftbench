from driftbench.extract import extract_from_text


def pairs(text):
    return [(kind, old, new) for kind, old, new, _ in extract_from_text(text)]


def test_rename():
    assert pairs("- Rename `missing_utf8_is_empty_string` to `empty_string_is_null` (#28173)") == [
        ("rename", "missing_utf8_is_empty_string", "empty_string_is_null")
    ]


def test_deprecation_in_favor_of():
    assert pairs("Deprecate `cut` in favor of `bin_intervals`.") == [("deprecation", "cut", "bin_intervals")]


def test_use_instead_of_keeps_direction():
    assert pairs("Use `allowBuilds` instead of `ignoredBuiltDependencies`") == [
        ("replacement", "ignoredBuiltDependencies", "allowBuilds")
    ]


def test_ignores_versions_and_lines_without_code():
    assert pairs("Rename `v1.2` to `v1.3`") == []
    assert pairs("Deprecate edge runtime") == []


def test_duplicate_pair_reported_once():
    text = "Rename `a_b` to `c_d`\nRenamed `a_b` to `c_d` again"
    assert len(pairs(text)) == 1


def test_deprecation_followed_by_configure_instead():
    text = (
        "The `root_path` parameter in `FastAPI()` is deprecated. "
        "Configure the server with `fastapi run --root-path /api/v1` instead."
    )
    assert pairs(text) == [("deprecation", "root_path in FastAPI()", "fastapi run --root-path /api/v1")]


def test_import_migration_diff():
    text = "```diff\n- import { serveStatic } from 'hono/bun'\n+ import { serveStatic } from '@hono/bun'\n```"
    assert pairs(text) == [
        ("replacement", "import { serveStatic } from 'hono/bun'", "import { serveStatic } from '@hono/bun'")
    ]


def test_deprecate_parameter_and_replace_with_new_option():
    text = (
        "- Deprecate `strict` parameter of `pl.concat`, replace with new `how='horizontal_extend'` (#27965)"
    )
    assert pairs(text) == [("deprecation", "strict in pl.concat", "how='horizontal_extend'")]


def test_exposes_multiple_replacement_properties_in_order():
    text = (
        "- consoleMessage.location() now exposes `line` / `column` properties "
        "(`lineNumber` / `columnNumber` are deprecated)."
    )
    assert pairs(text) == [("deprecation", "lineNumber", "line"), ("deprecation", "columnNumber", "column")]


def test_ignores_non_migration_diffs():
    assert pairs("```diff\n- version 1.2\n+ version 1.3\n```") == []
    assert pairs("- import { x } from 'a'\n+ import { x } from 'b'") == []
    assert pairs("```diff\n- import { x } from 'a'\n+ import { y } from 'b'\n```") == []
