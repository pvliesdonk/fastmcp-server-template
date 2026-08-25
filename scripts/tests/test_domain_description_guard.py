"""The `domain_description` answer is capped at the MCP registry's 100 chars.

`publish-registry` is the last job of a release and the only place the
registry's `description` length limit is enforced, so a long blurb passes
`copier copy`, every generated gate, and every other publish step before
failing (#481).  The copier validator moves that failure to the first
question; this renders with a blurb on each side of the cap to prove it.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]
ANSWERS = REPO / "tests" / "fixtures" / "smoke-answers.yml"


def _render(tmp_path: Path, blurb: str) -> subprocess.CompletedProcess[str]:
    answers = yaml.safe_load(ANSWERS.read_text(encoding="utf-8"))
    answers["domain_description"] = blurb
    answers_file = tmp_path / "answers.yml"
    answers_file.write_text(yaml.safe_dump(answers), encoding="utf-8")
    return subprocess.run(
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
            str(answers_file),
            str(REPO),
            str(tmp_path / "rendered"),
        ],
        check=False,
        capture_output=True,
        text=True,
    )


def test_blurb_at_the_cap_renders(tmp_path: Path) -> None:
    result = _render(tmp_path, "x" * 100)
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "rendered" / "server.json").is_file()


@pytest.mark.parametrize(
    ("blurb", "expected"),
    [
        ("x" * 101, "Too long (101 chars"),
        # Padding renders verbatim into server.json, so it counts (#499 review).
        (" " + "x" * 100 + " ", "Too long (102 chars"),
        ("   ", "Required"),
    ],
)
def test_rejected_blurb_fails_at_copy_time(
    tmp_path: Path, blurb: str, expected: str
) -> None:
    result = _render(tmp_path, blurb)
    assert result.returncode != 0
    assert expected in result.stderr, result.stderr
    assert not (tmp_path / "rendered" / "server.json").exists()
