"""The template repository's locked tooling environment (#694).

`pyproject.toml` + `uv.lock` at the repository root pin the tools template-ci
runs, so a job never resolves whatever is newest.  It must track the
generated project's pvl-core pin, and it must never reach a render.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import tomllib
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
_CORE = re.compile(r'"(fastmcp-pvl-core[^"]*)"')


def test_tooling_pvl_core_pin_matches_the_generated_project() -> None:
    tooling = tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))
    (tooling_core,) = [
        d
        for d in tooling["project"]["dependencies"]
        if d.startswith("fastmcp-pvl-core")
    ]
    rendered = _CORE.search((REPO / "pyproject.toml.jinja").read_text(encoding="utf-8"))
    assert rendered is not None
    assert tooling_core == rendered[1], (
        "bump the fastmcp-pvl-core pin in pyproject.toml together with "
        "pyproject.toml.jinja, then run `uv lock`"
    )


def test_tooling_lock_is_current() -> None:
    if shutil.which("uv") is None:
        pytest.skip("uv is required to check the lock")
    result = subprocess.run(
        ["uv", "lock", "--check"], cwd=REPO, capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr


def test_tooling_project_never_reaches_a_render(smoke_render: Path) -> None:
    rendered = tomllib.loads((smoke_render / "pyproject.toml").read_text("utf-8"))
    assert rendered["project"]["name"] != "fastmcp-server-template-tooling"
