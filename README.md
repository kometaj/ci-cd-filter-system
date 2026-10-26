# CI/CD Filter System

A small, installable Python command-line tool that evaluates changed repository file paths against named YAML glob filters and writes GitLab-compatible `KEY=true|false` dotenv output. The goal is to avoid running expensive application tasks when unrelated files change.

## Requirements

- Python 3.11+
- Pip 

## Project layout

```text
.
├── .github/workflows/ci.yml       # GitHub Actions lint, tests, smoke checks
├── examples/assignment-filters.yaml
├── src/ci_path_filter/
│   ├── __init__.py
│   ├── __main__.py               # python -m ci_path_filter
│   ├── cli.py                    # argparse + dotenv writing
│   └── filters.py                # YAML validation + glob engine + evaluation
├── tests/
│   ├── test_cli.py
│   └── test_filters.py
├── filters.yaml                  # Sample configuration
├── pyproject.toml                # Dependencies and CLI entrypoint
└── README.md
```

## Features

- YAML configuration with named filters.
- `*` matches characters within one path segment.
- `**` matches zero or more path segments.
- `!pattern` excludes a matching path from that filter.
- `.env` output uses lowercase `true` / `false`.
- Accepts changed paths as command-line arguments or from a newline-delimited file/stdin.
- Automated unit tests and GitHub Actions CI.

## Install / build

From the repository root:

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
python -m pip install -e .
```

This installs the `ci-path-filter` command. To build a distributable package instead, run `python -m pip install build` and `python -m build` (artifacts are placed in `dist/`).

## Configuration

Example `filters.yaml`:

```yaml
filters:
  backend:
    - "app/src/**/*.kt"
    - "!app/src/test/**"
  frontend:
    - "web/**/*.ts"
    - "web/**/*.tsx"
  docs:
    - "README.md"
    - "docs/**/*.md"
```

Each filter name becomes a dotenv variable. Names must match `[A-Za-z_][A-Za-z0-9_]*`. Each filter needs at least one inclusion pattern. Pattern order is irrelevant: exclusions always win **for the individual file** being checked.

## Run

```bash
ci-path-filter --config filters.yaml --output matched.env \
  app/src/main/App.kt web/src/App.tsx README.md
cat matched.env
```

Result:

```dotenv
backend=true
frontend=true
docs=true
```

Try the specific assignment example:

```bash
ci-path-filter --config examples/assignment-filters.yaml \
  --output matched.env App.kt src/test/FiltersTest.kt README.md
```

Result:

```dotenv
kotlin_sources=true
tests=true
documentation=true
```

To pass changed paths safely (including names with spaces), use a newline-separated file:

```bash
git diff --name-only BASE_COMMIT HEAD > changed-files.txt
ci-path-filter --config filters.yaml --files-from changed-files.txt --output matched.env
```

Replace `BASE_COMMIT` with the correct comparison commit for your CI event. The command also accepts a combination of positional paths and `--files-from`. An empty `--files-from` file is valid and emits `false` for all filters. The module can also be invoked as `python -m ci_path_filter`.

## Pattern semantics

| Pattern | Meaning |
| --- | --- |
| `*.kt` | A Kotlin file in the repository root only |
| `src/*.kt` | A Kotlin file directly inside `src` |
| `src/**/*.kt` | Kotlin files directly or recursively under `src` |
| `**/test/**` | Any file beneath a directory named `test` |
| `!**/test/**` | Exclude those files from that named filter |

- `*` matches zero or more characters **within one path segment**.
- `**` as a whole path segment matches **zero or more path segments**.
- Each path is included if **any inclusion pattern** matches and **no exclusion pattern** matches that **same path**. A filter is `true` if at least one included path survives.
- Matching is case-sensitive. Windows `\` file-path separators are normalized to `/`.
- Both the config patterns and changed paths must be repository-relative; absolute paths and parent (`..`) traversal are rejected.
- As a convenience, `?` and bracket character classes inside a single segment are supported via `fnmatchcase`.

## Test and CI

```bash
python -m pip install -e ".[dev]"
ruff check .
python -m pytest -q
```

The GitHub Actions workflow at `.github/workflows/ci.yml` runs linting, all automated tests, and a real installed-command smoke test on every push and pull request for Python 3.11, 3.12, and 3.13. See the **Actions** tab to confirm a green run before submission.

## GitLab integration

An upstream GitLab job can produce this tool's dotenv report:

```yaml
stages: [detect, build]

detect_changes:
  stage: detect
  image: python:3.12
  script:
    - pip install .
    # Supply an appropriate base SHA from your merge-request/branch workflow.
    - git diff --name-only "$CI_COMMIT_BEFORE_SHA" "$CI_COMMIT_SHA" > changed-files.txt
    - ci-path-filter --config filters.yaml --files-from changed-files.txt --output matched.env
  artifacts:
    reports:
      dotenv: matched.env

build_backend:
  stage: build
  needs:
    - job: detect_changes
      artifacts: true
  script:
    - |
      if [ "$backend" != "true" ]; then
        echo "No backend changes; skipping backend build"
        exit 0
      fi
      echo "Execute backend build here"
```

**Important GitLab limitation:** dotenv variables generated by a job **cannot control `rules:` evaluation** because `rules` are evaluated when the pipeline is created, before `detect_changes` runs. The example above skips the *build work*, not creation of `build_backend`. For true conditional **job creation**, generate a dynamic child-pipeline YAML configuration or use static GitLab `rules:changes`. A robust production GitLab example must also handle different merge-request and initial-commit diff bases; this snippet illustrates the output integration, not universal diff selection.

## Validation and errors

The CLI reports malformed YAML, unknown top-level fields, invalid environment variable names, empty/invalid pattern lists, invalid paths, and file I/O issues with a nonzero exit status. A failed evaluation does not write the output file.

## Intentional scope / trade-offs

- **YAML config is intentionally minimal**: no additional rule languages, combined boolean expression syntax, or precedence rules; exclusions always override inclusion on the same file.
- **Changed file discovery is delegated to Git** or the caller. CI providers disagree on how to compute merge-base and changed paths; this tool focuses on deterministic filtering from a supplied input list.
- **Pattern matching is segment-aware** using `fnmatchcase` and memoized recursion instead of a larger glob dependency. This gives the required `*` and `**` behavior but does not attempt full Git ignore syntax, brace expansion, or negation re-inclusion.
- **GitLab integration snippet is intentionally limited** to demonstrating dotenv output. Runtime dotenv data cannot influence earlier job scheduling; see the GitLab limitation above.
- **Input list format is newline-delimited**, making spaces safe, but file names containing literal newlines are not represented. A NUL-delimited input mode could be added for full Git filename generality.

## License

MIT (see `LICENSE`).
