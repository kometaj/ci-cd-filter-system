"""Configuration validation and segment-aware glob evaluation."""

from __future__ import annotations

import re
from fnmatch import fnmatchcase
from functools import lru_cache
from pathlib import Path
from typing import TypeAlias

import yaml


FilterMap: TypeAlias = dict[str, list[str]]
_ENV_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class FilterConfigError(ValueError):
    """Raised when filters.yaml does not follow the expected schema."""


def normalize_path(path: str) -> str:
    """Use repository-relative, forward-slash paths consistently across OSes."""
    normalized = path.replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    if (
        not normalized
        or normalized.startswith("/")
        or re.match(r"^[A-Za-z]:/", normalized)
        or ".." in normalized.split("/")
    ):
        raise ValueError(f"Expected a repository-relative path, got {path!r}")
    return normalized


def load_filters(config_path: str | Path) -> FilterMap:
    """Load and validate a YAML mapping under the top-level `filters` key."""
    try:
        content = Path(config_path).read_text(encoding="utf-8")
        document = yaml.safe_load(content)
    except yaml.YAMLError as exc:
        raise FilterConfigError(f"Invalid YAML in {config_path}: {exc}") from exc

    if not isinstance(document, dict) or set(document) != {"filters"}:
        raise FilterConfigError("Configuration must contain only the top-level 'filters' mapping")

    filters = document["filters"]
    if not isinstance(filters, dict) or not filters:
        raise FilterConfigError("'filters' must be a nonempty mapping")

    for name, patterns in filters.items():
        if not isinstance(name, str) or not _ENV_NAME.fullmatch(name):
            raise FilterConfigError(
                f"Invalid filter name {name!r}; use letters, digits, underscores, "
                "and start with a letter or underscore"
            )
        if not isinstance(patterns, list) or not patterns:
            raise FilterConfigError(f"Filter {name!r} must have a nonempty list of glob patterns")
        if not all(isinstance(pattern, str) and pattern for pattern in patterns):
            raise FilterConfigError(f"Filter {name!r} contains an empty or non-string pattern")
        if not any(not pattern.startswith("!") for pattern in patterns):
            raise FilterConfigError(f"Filter {name!r} needs at least one inclusion pattern")
        for pattern in patterns:
            raw = pattern[1:] if pattern.startswith("!") else pattern
            try:
                normalize_path(raw)
            except ValueError as exc:
                raise FilterConfigError(f"Invalid pattern in filter {name!r}: {exc}") from exc

    return filters


def matches_glob(pattern: str, changed_path: str) -> bool:
    """Match path components; ** spans zero or more whole components.

    Single * (and optional ? / [] fnmatch syntax) stays within one component.
    Names are compared case-sensitively on every OS.
    """
    parts = normalize_path(pattern).split("/")
    path_parts = normalize_path(changed_path).split("/")

    @lru_cache(maxsize=None)
    def match(pattern_index: int, path_index: int) -> bool:
        if pattern_index == len(parts):
            return path_index == len(path_parts)
        segment = parts[pattern_index]
        if segment == "**":
            return match(pattern_index + 1, path_index) or (
                path_index < len(path_parts) and match(pattern_index, path_index + 1)
            )
        return (
            path_index < len(path_parts)
            and fnmatchcase(path_parts[path_index], segment)
            and match(pattern_index + 1, path_index + 1)
        )

    return match(0, 0)


def evaluate_filters(filters: FilterMap, changed_paths: list[str]) -> dict[str, bool]:
    """A filter passes if ANY single changed path is included and not excluded."""
    normalized_paths = [normalize_path(path) for path in changed_paths]
    results: dict[str, bool] = {}

    for name, patterns in filters.items():
        includes = [pattern for pattern in patterns if not pattern.startswith("!")]
        excludes = [pattern[1:] for pattern in patterns if pattern.startswith("!")]
        results[name] = any(
            any(matches_glob(pattern, path) for pattern in includes)
            and not any(matches_glob(pattern, path) for pattern in excludes)
            for path in normalized_paths
        )

    return results
