"""Render the template with the MCP Apps toggle off and assert no SPA files leak."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
_ANSWERS = _REPO / "tests" / "fixtures" / "smoke-answers.yml"


def _render(tmp_path: Path, apps_on: bool) -> Path:
    answers = tmp_path / "answers.yml"
    text = _ANSWERS.read_text(encoding="utf-8")
    text = text.replace(
        "include_mcp_apps_scaffold: true",
        f"include_mcp_apps_scaffold: {'true' if apps_on else 'false'}",
    )
    answers.write_text(text, encoding="utf-8")
    out = tmp_path / "out"
    subprocess.run(
        [
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
            str(answers),
            str(_REPO),
            str(out),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return out


@pytest.mark.skipif(
    "CI" not in __import__("os").environ, reason="renders via network; CI only"
)
def test_apps_off_omits_spa_scaffold(tmp_path: Path):
    out = _render(tmp_path, apps_on=False)
    assert not (out / "scripts" / "vendor_spa.py").exists()
    assert not (out / ".gitattributes").exists()
    static = out / "src" / "smoke_mcp" / "static"
    assert not (static / "app.src.html").exists()
    assert not (static / "app.html").exists()
    assert not (out / "tests" / "test_apps_vendoring.py").exists()
