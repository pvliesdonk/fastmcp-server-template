"""Unit tests for the seeded-file change report (#519); the end-to-end run
happens in template-ci's copier-update regression job.  Importing the module
must be side-effect free: the `uv run` fallback lives in main() only."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import report_seeded_changes as r

SCRIPT = Path(__file__).resolve().parents[1] / "report_seeded_changes.py"


def _tree(root: Path, files: dict[str, str]) -> Path:
    for rel, text in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    return root


def test_importing_the_module_does_not_reexec() -> None:
    # A module-level exec would have replaced this pytest process already;
    # assert the contract explicitly for the no-answers path as well.
    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            f"import sys; sys.path.insert(0, {str(SCRIPT.parent)!r}); "
            "import report_seeded_changes; print('imported')",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.stdout.strip() == "imported", proc.stderr


def test_render_pattern_substitutes_answers() -> None:
    assert (
        r._render_pattern("src/{{python_module}}/tools.py", {"python_module": "x_mcp"})
        == "src/x_mcp/tools.py"
    )
    assert r._render_pattern("tests/conftest.py", {}) == "tests/conftest.py"


def test_matching_files_handles_trailing_doublestar(tmp_path: Path) -> None:
    root = _tree(
        tmp_path,
        {
            "docs/releases/index.md": "a",
            "docs/releases/5.6.md": "b",
            "docs/other.md": "c",
        },
    )
    assert r.matching_files(root, ["docs/releases/**"]) == {
        "docs/releases/index.md",
        "docs/releases/5.6.md",
    }


def test_diff_seeded_reports_changed_added_and_skips_generated(tmp_path: Path) -> None:
    old = _tree(
        tmp_path / "old",
        {"tests/test_smoke.py": "a\nb\n", ".env.example": "X=1\n", "same.txt": "s\n"},
    )
    new = _tree(
        tmp_path / "new",
        {
            "tests/test_smoke.py": "a\nc\n",
            ".env.example": "X=2\n",
            "same.txt": "s\n",
            "tests/test_cli.py": "new\n",
        },
    )
    patterns = ["tests/test_smoke.py", "tests/test_cli.py", ".env.example", "same.txt"]
    changes = dict(r.diff_seeded(old, new, patterns))
    assert set(changes) == {"tests/test_smoke.py", "tests/test_cli.py"}
    assert "-b\n+c" in changes["tests/test_smoke.py"]
    assert "+new" in changes["tests/test_cli.py"]


def test_report_is_hygiene_clean(tmp_path: Path) -> None:
    old = _tree(tmp_path / "old", {"f.py": "x\n\ny\n"})
    new = _tree(tmp_path / "new", {"f.py": "x\n\nz"})
    changes = r.diff_seeded(old, new, ["f.py"])
    text = r.render_report(
        src="gh:o/t", old="v1", new="v2", changes=changes, failure=None
    )
    assert all(line == line.rstrip() for line in text.splitlines()), (
        "trailing whitespace"
    )
    assert text.endswith("\n") and not text.endswith("\n\n")
    assert "````diff\n" in text and "\n````\n" in text


def test_report_states_no_changes_and_failure_explicitly() -> None:
    assert "No seeded file changed" in r.render_report(
        src="gh:o/t", old="v1.0.0", new="v1.1.0", changes=[], failure=None
    )
    text = r.render_report(
        src="gh:o/t", old="v1", new="v2", changes=[], failure="OSError: offline"
    )
    assert (
        "could not be computed" in text
        and "OSError: offline" in text
        and "template-updates.md" in text
    )


def test_skip_removes_a_stale_report(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".copier-seeded-changes.md").write_text("stale")
    assert r._skip("nothing to do") == 0
    assert not (tmp_path / ".copier-seeded-changes.md").exists()
