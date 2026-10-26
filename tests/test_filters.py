"""Unit tests for matching semantics and YAML schema."""

from pathlib import Path

import pytest

from ci_path_filter.filters import (
    FilterConfigError,
    evaluate_filters,
    load_filters,
    matches_glob,
    normalize_path,
)


@pytest.mark.parametrize(
    ("pattern", "path", "expected"),
    [
        ("*.kt", "App.kt", True),
        ("*.kt", "src/App.kt", False),
        ("app/*/Main.kt", "app/src/Main.kt", True),
        ("app/*/Main.kt", "app/src/main/Main.kt", False),
        ("**/*.kt", "App.kt", True),
        ("**/*.kt", "src/feature/App.kt", True),
        ("app/src/**/*.kt", "app/src/Main.kt", True),
        ("app/src/**/*.kt", "app/src/lib/Main.kt", True),
        ("app/src/**/*.kt", "app/src/lib/Main.ts", False),
        ("**/test/**", "test/Foo.kt", True),
        ("**/test/**", "app/test/Foo.kt", True),
        ("**/test/**", "app/testing/Foo.kt", False),
        ("docs/**", "docs/setup.md", True),
        ("docs/**", "docs/guides/setup.md", True),
        ("docs/**", "docs", True),
        ("README.md", "README.md", True),
        ("README.md", "docs/README.md", False),
        ("web/**/*.tsx", "web/App.tsx", True),
        ("web/**/*.tsx", "web/components/App.tsx", True),
        ("*.kt", "app.KT", False),
        ("src/?oo.kt", "src/Foo.kt", True),
    ],
)
def test_glob_matching(pattern: str, path: str, expected: bool) -> None:
    assert matches_glob(pattern, path) is expected


def test_windows_separator_normalization() -> None:
    assert matches_glob("app/src/**/*.kt", r"app\src\main\Main.kt")
    assert normalize_path("./src/App.kt") == "src/App.kt"


def test_evaluate_filters_assignment_example() -> None:
    filters = {
        "kotlin_sources": ["**/*.kt", "!**/test/**"],
        "tests": ["**/test/**/*.kt"],
        "documentation": ["README.md", "docs/**"],
    }
    paths = ["app/src/App.kt", "app/src/test/FiltersTest.kt", "README.md"]
    assert evaluate_filters(filters, paths) == {
        "kotlin_sources": True,
        "tests": True,
        "documentation": True,
    }


def test_exclusion_only_removes_matching_file_not_entire_filter() -> None:
    filters = {"backend": ["**/*.kt", "!**/test/**"]}
    assert evaluate_filters(filters, ["src/test/Fixture.kt", "src/Main.kt"]) == {
        "backend": True
    }


def test_excluded_files_cannot_turn_on_filter() -> None:
    filters = {"backend": ["**/*.kt", "!**/test/**"]}
    assert evaluate_filters(filters, ["src/test/Fixture.kt"]) == {"backend": False}


def test_any_inclusion_and_all_exclusions_apply_to_same_file() -> None:
    filters = {"code": ["src/**/*.kt", "src/**/*.ts", "!src/vendor/**", "!src/test/**"]}
    assert evaluate_filters(filters, ["src/vendor/Util.kt", "src/test/Main.ts"]) == {"code": False}
    assert evaluate_filters(filters, ["src/vendor/Util.kt", "src/Main.ts"]) == {"code": True}


def test_empty_changed_paths_are_all_false() -> None:
    assert evaluate_filters({"docs": ["docs/**"], "backend": ["**/*.kt"]}, []) == {
        "docs": False,
        "backend": False,
    }


def test_load_valid_yaml(tmp_path: Path) -> None:
    file = tmp_path / "filters.yaml"
    file.write_text('filters:\n  backend:\n    - "**/*.kt"\n    - "!**/test/**"\n')
    assert load_filters(file) == {"backend": ["**/*.kt", "!**/test/**"]}


@pytest.mark.parametrize(
    "contents",
    [
        "filters: []",
        "filters: {}",
        "filters: null",
        "some_other_key: {}",
        "filters:\n  missing_patterns: []",
        "filters:\n  invalid-name:\n    - 'src/**'",
        "filters:\n  only_exclusion:\n    - '!**/test/**'",
        "filters:\n  invalid_pattern:\n    - 12",
        "filters:\n  invalid_pattern:\n    - ''",
        "filters:\n  invalid_pattern:\n    - '../outside/**'",
        "filters:\n  valid:\n    - '*.kt'\nother_key: 42",
        "filters: [unclosed",
    ],
)
def test_invalid_yaml_schema_reports_error(tmp_path: Path, contents: str) -> None:
    file = tmp_path / "filters.yaml"
    file.write_text(contents)
    with pytest.raises(FilterConfigError):
        load_filters(file)


@pytest.mark.parametrize(
    "path", ["", "/absolute/path.kt", r"C:\absolute\x.kt", "../secret.kt", "src/../foo.kt"]
)
def test_invalid_repository_paths(path: str) -> None:
    with pytest.raises(ValueError):
        normalize_path(path)
