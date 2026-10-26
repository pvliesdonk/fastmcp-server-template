"""The Docker image ships the interpreter CI's coverage lane tests (#828).

Renovate moved `FROM python:3.14-slim` to 3.15 while the matrix, the coverage
lane and the classifiers stayed at 3.14, and a downstream's native dependency
with no cp315 wheel broke its image.  The image now installs a uv-managed
CPython, which also brings a SQLite with the WAL-reset fix (#829), at a
version this test ties to the coverage lane, so the two move together.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import yaml

if TYPE_CHECKING:
    from pathlib import Path


def _instructions(render: Path) -> list[str]:
    return [
        line.strip()
        for line in (render / "Dockerfile").read_text().splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def _coverage_lane(render: Path) -> str:
    ci = yaml.safe_load((render / ".github/workflows/ci.yml").read_text())
    covered = next(
        step
        for step in ci["jobs"]["test"]["steps"]
        if step.get("name") == "Run tests with coverage"
    )
    m = re.fullmatch(r"matrix\.python-version == '(3\.\d+)'", covered["if"])
    assert m, f"unexpected coverage-lane condition: {covered['if']!r}"
    return m.group(1)


def test_image_installs_the_coverage_lane_python(smoke_render: Path) -> None:
    lines = _instructions(smoke_render)
    (base,) = [line for line in lines if line.startswith("FROM ")]
    assert not re.match(r"FROM\s+python:", base), base
    args = [line for line in lines if line.startswith("ARG PYTHON_VERSION=")]
    assert len(args) == 1, args
    assert args[0] == f"ARG PYTHON_VERSION={_coverage_lane(smoke_render)}"
    assert 'RUN uv python install "$PYTHON_VERSION"' in lines


def test_image_python_is_a_required_matrix_version(smoke_render: Path) -> None:
    ci = yaml.safe_load((smoke_render / ".github/workflows/ci.yml").read_text())
    entries = ci["jobs"]["test"]["strategy"]["matrix"]["include"]
    lane = _coverage_lane(smoke_render)
    (entry,) = [e for e in entries if e["python-version"] == lane]
    assert entry["experimental"] is False
