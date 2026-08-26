"""Shared fixtures for the template's own tests.

`smoke_render` renders the template once per session from the committed
HEAD with `tests/fixtures/smoke-answers.yml`; tests that need a rendered
project share it instead of each running copier.  Copier's stderr is
surfaced on failure and the render has a timeout, so a Jinja error or a
stalled network fetch (the default answers vendor the MCP Apps SDK) shows
up as a readable failure rather than a hang.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SMOKE_ANSWERS = REPO / "tests" / "fixtures" / "smoke-answers.yml"


@pytest.fixture(scope="session")
def smoke_render(tmp_path_factory: pytest.TempPathFactory) -> Path:
    if shutil.which("uv") is None:
        pytest.skip("uv is required to render the template")
    out = tmp_path_factory.mktemp("smoke-render") / "rendered"
    cmd = [
        "uv",
        "run",
        "--no-project",
        "--with",
        "copier",
        "copier",
        "copy",
        "--trust",
        "--defaults",
        "--vcs-ref=HEAD",
        "--data-file",
        str(SMOKE_ANSWERS),
        str(REPO),
        str(out),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=600)
    if proc.returncode != 0:
        pytest.fail(f"copier copy failed ({proc.returncode}):\n{proc.stderr[-4000:]}")
    return out
