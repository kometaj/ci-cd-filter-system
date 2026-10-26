"""Command-line interface for GitLab dotenv output."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .filters import evaluate_filters, load_filters


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Match changed files against named YAML globs and write a GitLab dotenv file."
    )
    parser.add_argument("paths", nargs="*", help="Changed repository-relative file paths")
    parser.add_argument("--config", default="filters.yaml", help="YAML filter configuration")
    parser.add_argument("--output", default="matched.env", help="Output GitLab dotenv file")
    parser.add_argument(
        "--files-from", metavar="FILE", help="Optional newline-separated list of changed files"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.paths and not args.files_from:
        parser.error("provide changed file paths or --files-from FILE")

    try:
        paths: list[str] = list(args.paths)
        if args.files_from:
            # An empty input file is valid: all filters should evaluate to false.
            paths.extend(
                line
                for line in Path(args.files_from).read_text(encoding="utf-8").splitlines()
                if line
            )
        filters = load_filters(args.config)
        results = evaluate_filters(filters, paths)
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            "".join(f"{name}={str(value).lower()}\n" for name, value in results.items()),
            encoding="utf-8",
        )
    except (OSError, ValueError) as exc:
        print(f"ci-path-filter: error: {exc}", file=sys.stderr)
        return 1

    print(f"Wrote {len(results)} filter result(s) to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
