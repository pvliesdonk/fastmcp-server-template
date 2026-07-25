"""Unit tests for the render-hygiene guard (issue #251).

The guard asserts a pristine copier render already satisfies the
``trailing-whitespace`` and ``end-of-file-fixer`` pre-commit hooks the
template ships, so a downstream's committed file stays byte-identical to
the render and ``copier update`` never conflicts on hook-rewritten
regions.

These tests exercise the checker itself against synthetic trees -- no
copier render, so they stay fast.  ``template-ci.yml`` runs the checker
against the real renders.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

# Make the script importable as a module (pytest runs from repo root).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from check_render_hygiene import (  # pyright: ignore[reportMissingImports]
    check_file,
    check_tree,
    main,
)

if TYPE_CHECKING:
    import pytest


def _write(tmp_path: Path, name: str, data: bytes) -> Path:
    path = tmp_path / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def test_clean_file_has_no_violations(tmp_path: Path) -> None:
    path = _write(tmp_path, "ci.yml", b"jobs:\n  lint:\n    runs-on: ubuntu-latest\n")
    assert check_file(path) == []


def test_blank_line_at_eof_is_flagged(tmp_path: Path) -> None:
    """The #251 shape: a terminal Jinja block tag leaves the render ending \\n\\n."""
    path = _write(tmp_path, "ci.yml", b"      --fail-under=100\n\n")
    (violation,) = check_file(path)
    assert violation.line is None
    assert "blank line(s) at EOF" in violation.message


def test_multiple_blank_lines_at_eof_are_flagged(tmp_path: Path) -> None:
    path = _write(tmp_path, "ci.yml", b"jobs:\n\n\n\n")
    (violation,) = check_file(path)
    assert "blank line(s) at EOF" in violation.message


def test_crlf_blank_line_at_eof_is_flagged(tmp_path: Path) -> None:
    """A CRLF file ends "\\r\\n\\r\\n", so a literal b"\\n\\n" test would miss it."""
    path = _write(tmp_path, "ci.yml", b"jobs:\r\n\r\n")
    (violation,) = check_file(path)
    assert "blank line(s) at EOF" in violation.message


def test_lone_cr_blank_line_at_eof_is_flagged(tmp_path: Path) -> None:
    path = _write(tmp_path, "ci.yml", b"jobs:\r\r")
    (violation,) = check_file(path)
    assert "blank line(s) at EOF" in violation.message


def test_mixed_terminators_at_eof_are_flagged(tmp_path: Path) -> None:
    path = _write(tmp_path, "ci.yml", b"jobs:\n\r\n")
    (violation,) = check_file(path)
    assert "blank line(s) at EOF" in violation.message


def test_file_of_only_terminators_is_flagged(tmp_path: Path) -> None:
    """end-of-file-fixer truncates an all-newline file to empty."""
    path = _write(tmp_path, "blank.txt", b"\n")
    (violation,) = check_file(path)
    assert "blank line(s) at EOF" in violation.message


def test_single_crlf_terminator_is_clean(tmp_path: Path) -> None:
    path = _write(tmp_path, "ci.yml", b"jobs:\r\n")
    assert check_file(path) == []


def test_missing_final_newline_is_flagged(tmp_path: Path) -> None:
    path = _write(tmp_path, "ci.yml", b"jobs:\n  lint: {}")
    (violation,) = check_file(path)
    assert "missing final newline" in violation.message


def test_trailing_whitespace_is_flagged_with_line_number(tmp_path: Path) -> None:
    path = _write(tmp_path, "ci.yml", b"jobs:\n  lint:   \n    x: 1\n")
    (violation,) = check_file(path)
    assert violation.line == 2
    assert "trailing whitespace" in violation.message


def test_trailing_tab_is_flagged(tmp_path: Path) -> None:
    path = _write(tmp_path, "a.md", b"text\t\n")
    (violation,) = check_file(path)
    assert violation.line == 1


def test_markdown_hard_break_is_not_exempt(tmp_path: Path) -> None:
    """No --markdown-linebreak-ext is configured, so .md gets no exemption."""
    path = _write(tmp_path, "README.md", b"line one  \nline two\n")
    (violation,) = check_file(path)
    assert violation.line == 1


def test_crlf_line_without_trailing_space_is_clean(tmp_path: Path) -> None:
    """The \\r belongs to the terminator, not the content."""
    path = _write(tmp_path, "a.txt", b"one\r\ntwo\r\n")
    assert check_file(path) == []


def test_crlf_line_with_trailing_space_is_flagged(tmp_path: Path) -> None:
    path = _write(tmp_path, "a.txt", b"one \r\ntwo\r\n")
    (violation,) = check_file(path)
    assert violation.line == 1


def test_empty_file_is_left_alone(tmp_path: Path) -> None:
    """end-of-file-fixer does not add a newline to an empty file."""
    path = _write(tmp_path, "py.typed", b"")
    assert check_file(path) == []


def test_binary_file_is_skipped(tmp_path: Path) -> None:
    """`types: [text]` means the hooks never see a NUL-bearing file."""
    path = _write(tmp_path, "logo.png", b"\x89PNG\r\n\x1a\n\x00\x00\x00 trailing  ")
    assert check_file(path) == []


def test_check_tree_reports_every_offender(tmp_path: Path) -> None:
    _write(tmp_path, "good.yml", b"ok\n")
    _write(tmp_path, ".github/workflows/ci.yml", b"jobs:\n\n")
    _write(tmp_path, "docs/index.md", b"title  \n")
    violations = check_tree(tmp_path)
    assert len(violations) == 2
    rendered = sorted(v.format(tmp_path) for v in violations)
    assert rendered[0].startswith(".github/workflows/ci.yml:")
    assert rendered[1].startswith("docs/index.md:1:")


def test_check_tree_skips_build_and_vcs_dirs(tmp_path: Path) -> None:
    _write(tmp_path, ".venv/lib/x.py", b"junk  \n\n")
    _write(tmp_path, ".git/COMMIT_EDITMSG", b"msg  \n\n")
    _write(tmp_path, "src/__pycache__/x.pyc", b"junk  \n\n")
    assert check_tree(tmp_path) == []


def test_main_passes_on_a_clean_tree(tmp_path: Path, capsys) -> None:
    _write(tmp_path, "ci.yml", b"jobs:\n")
    assert main([str(tmp_path)]) == 0
    assert "render hygiene OK" in capsys.readouterr().out


def test_main_fails_and_names_the_file(tmp_path: Path, capsys) -> None:
    _write(tmp_path, ".github/workflows/ci.yml", b"jobs:\n\n")
    assert main([str(tmp_path)]) == 1
    out = capsys.readouterr().out
    assert "render hygiene FAILED" in out
    assert ".github/workflows/ci.yml" in out


def test_main_emits_actions_annotations(
    tmp_path: Path, capsys, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    _write(tmp_path, "ci.yml", b"jobs:\n\n")
    assert main([str(tmp_path)]) == 1
    assert "::error::" in capsys.readouterr().out


def test_main_fails_on_a_missing_directory(tmp_path: Path) -> None:
    assert main([str(tmp_path / "nope")]) == 1


def test_main_checks_every_root(tmp_path: Path, capsys) -> None:
    clean = tmp_path / "clean"
    dirty = tmp_path / "dirty"
    _write(clean, "ci.yml", b"jobs:\n")
    _write(dirty, "ci.yml", b"jobs:\n\n")
    assert main([str(clean), str(dirty)]) == 1
    out = capsys.readouterr().out
    assert "render hygiene OK" in out
    assert "render hygiene FAILED" in out
