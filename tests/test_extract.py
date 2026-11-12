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
