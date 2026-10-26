"""Allow `python -m ci_path_filter` as an alternative to the installed CLI."""

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
