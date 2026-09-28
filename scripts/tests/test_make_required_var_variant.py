"""`make_required_var_variant.py` against a copy of the smoke render.

template-ci's required-var variant step runs the script and then the copy's
whole gate; these tests pin the edit itself, so a reworded example or a
moved anchor fails here with the reason rather than as a gate failure.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import make_required_var_variant as v


@pytest.fixture
def project(
    smoke_render: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Path:
    """A private copy of the render: the script edits in place."""
    copy = tmp_path / "project"
    shutil.copytree(smoke_render, copy, symlinks=True)
    monkeypatch.chdir(copy)
    return copy


def test_uncomments_the_example_and_supplies_it_in_the_contract(project: Path) -> None:
    v.main()
    config = (project / "src/smoke_mcp/config.py").read_text()
    assert "    api_token: str = field(\n" in config
    assert (
        '            api_token=env(_ENV_PREFIX, "API_TOKEN", required=True),\n'
        in config
    )
    assert "# api_token" not in config
    conftest = (project / "tests/conftest.py").read_text()
    assert 'return {"SMOKE_MCP_API_TOKEN": "test-token"}' in conftest


@pytest.mark.usefixtures("project")
def test_a_second_run_fails_loudly() -> None:
    """The anchors are gone once edited, so re-running cannot test nothing."""
    v.main()
    with pytest.raises(SystemExit, match="expected exactly one occurrence"):
        v.main()


def test_refuses_a_project_without_an_env_prefix_answer(project: Path) -> None:
    answers = project / ".copier-answers.yml"
    answers.write_text(
        "".join(
            line
            for line in answers.read_text().splitlines(keepends=True)
            if not line.startswith("env_prefix:")
        )
    )
    with pytest.raises(SystemExit, match="no env_prefix answer"):
        v.main()


def test_refuses_anything_but_one_config(project: Path) -> None:
    shutil.copytree(project / "src/smoke_mcp", project / "src/second")
    with pytest.raises(SystemExit, match=r"expected exactly one src/\*/config\.py"):
        v.main()


@pytest.mark.usefixtures("project")
def test_refuses_a_path_outside_the_working_directory(tmp_path: Path) -> None:
    outside = tmp_path / "outside.py"
    outside.write_text("x\n")
    with pytest.raises(SystemExit, match="outside the working directory"):
        v._substitute_once(outside, "x", "y")
