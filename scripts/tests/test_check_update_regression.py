"""Unit tests for check_update_regression.py's reference-page guard (#778).

The end-to-end run is template-ci's copier-update regression job; these pin
what the guard accepts and refuses on a project tree it is handed.
"""

from __future__ import annotations

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
