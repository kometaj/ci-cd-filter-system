"""End-to-end tests for the CLI and generated dotenv format."""

import subprocess
import sys
from pathlib import Path

from ci_path_filter.cli import main


CONFIG = '''filters:
  kotlin_sources:
    - "**/*.kt"
    - "!**/test/**"
  tests:
    - "**/test/**/*.kt"
  documentation:
    - "README.md"
    - "docs/**"
'''


def test_cli_creates_expected_env_file(tmp_path: Path) -> None:
    config = tmp_path / "filters.yaml"
    output = tmp_path / "output" / "matched.env"
    config.write_text(CONFIG)

    assert main([
        "--config", str(config),
        "--output", str(output),
        "src/App.kt", "src/test/FiltersTest.kt", "README.md",
    ]) == 0
    assert output.read_text() == (
        "kotlin_sources=true\ntests=true\ndocumentation=true\n"
    )


def test_cli_files_from_and_no_changed_files(tmp_path: Path) -> None:
    config = tmp_path / "filters.yaml"
    file_list = tmp_path / "paths.txt"
    output = tmp_path / "matched.env"
    config.write_text(CONFIG)
    file_list.write_text("")
    assert main([
        "--config", str(config), "--files-from", str(file_list), "--output", str(output)
    ]) == 0
    assert output.read_text() == (
        "kotlin_sources=false\ntests=false\ndocumentation=false\n"
    )


def test_cli_supports_spaces_in_changed_file_names(tmp_path: Path) -> None:
    config = tmp_path / "filters.yaml"
    file_list = tmp_path / "paths.txt"
    output = tmp_path / "matched.env"
    config.write_text('filters:\n  docs:\n    - "docs/**"\n')
    file_list.write_text("docs/My Setup.md\n")
    assert main([
        "--config", str(config), "--files-from", str(file_list), "--output", str(output)
    ]) == 0
    assert output.read_text() == "docs=true\n"


def test_cli_invalid_config_is_nonzero_and_does_not_write_output(
    tmp_path: Path, capsys
) -> None:
    config = tmp_path / "filters.yaml"
    output = tmp_path / "matched.env"
    config.write_text("filters: [unclosed")
    assert main(["--config", str(config), "--output", str(output), "src/App.kt"]) == 1
    assert "error:" in capsys.readouterr().err
    assert not output.exists()


def test_cli_missing_config_is_nonzero(tmp_path: Path, capsys) -> None:
    assert main(["--config", str(tmp_path / "missing.yml"), "x.txt"]) == 1
    assert "error:" in capsys.readouterr().err


def test_cli_can_run_as_python_module(tmp_path: Path) -> None:
    config = tmp_path / "filters.yaml"
    output = tmp_path / "matched.env"
    config.write_text(CONFIG)
    completed = subprocess.run(
        [
            sys.executable, "-m", "ci_path_filter", "--config", str(config),
            "--output", str(output), "src/test/FiltersTest.kt",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert output.read_text() == (
        "kotlin_sources=false\ntests=true\ndocumentation=false\n"
    )
