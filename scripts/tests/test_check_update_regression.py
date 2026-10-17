"""Unit tests for check_update_regression.py's reference-page guard (#778).

The end-to-end run is template-ci's copier-update regression job; these pin
what the guard accepts and refuses on a project tree it is handed.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import check_update_regression as u


def _planted(tmp_path: Path) -> Path:
    u._plant_reference_page(tmp_path)
    return tmp_path


def test_a_planted_page_alone_passes(tmp_path: Path) -> None:
    u._assert_reference_pages_untouched(_planted(tmp_path))


@pytest.mark.parametrize(
    "scaffold_page",
    ["docs/reference/tools/tools.md", "docs/reference/cli.md"],
)
def test_a_scaffold_page_written_by_the_update_fails(
    tmp_path: Path, scaffold_page: str
) -> None:
    project = _planted(tmp_path)
    (project / scaffold_page).write_text("# scaffold\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="wrote scaffold reference pages"):
        u._assert_reference_pages_untouched(project)


def test_a_changed_project_page_fails(tmp_path: Path) -> None:
    project = _planted(tmp_path)
    (project / u._OWN_PAGE).write_text("# rewritten\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="changed the project's"):
        u._assert_reference_pages_untouched(project)


_RACE = (
    "OSError: [Errno 39] Directory not empty: "
    "'/tmp/copier._main.new_copy.l9g4aqw0/.git/objects'\n"
)


def _fake_updates(
    monkeypatch: pytest.MonkeyPatch, project: Path, outcomes: list[tuple[int, str]]
) -> list[str]:
    """Replace the copier run: each call records the project's state, dirties
    it the way a half-finished update would, and returns the next outcome."""
    seen: list[str] = []

    def run(*_a: object, **_k: object) -> subprocess.CompletedProcess[str]:
        marker = project / "state.txt"
        seen.append(marker.read_text(encoding="utf-8"))
        marker.write_text("touched by update\n", encoding="utf-8")
        code, stderr = outcomes[len(seen) - 1]
        return subprocess.CompletedProcess([], code, stdout="", stderr=stderr)

    monkeypatch.setattr(u.subprocess, "run", run)
    return seen


def _project(tmp_path: Path) -> Path:
    project = tmp_path / "project"
    project.mkdir()
    (project / "state.txt").write_text("committed\n", encoding="utf-8")
    return project


def test_update_retries_once_from_the_snapshot_on_the_cleanup_race(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = _project(tmp_path)
    seen = _fake_updates(monkeypatch, project, [(1, _RACE), (0, "")])
    u._update(project)
    assert seen == ["committed\n", "committed\n"]  # second run saw the snapshot


def test_update_does_not_retry_any_other_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = _project(tmp_path)
    seen = _fake_updates(monkeypatch, project, [(1, "Conflict in config.py\n")])
    with pytest.raises(SystemExit, match="exited 1"):
        u._update(project)
    assert len(seen) == 1


def test_update_fails_when_the_race_repeats(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = _project(tmp_path)
    seen = _fake_updates(monkeypatch, project, [(1, _RACE), (1, _RACE)])
    with pytest.raises(SystemExit, match="exited 1"):
        u._update(project)
    assert len(seen) == 2
