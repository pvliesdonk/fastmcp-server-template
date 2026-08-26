"""`domain_description` is interpolated verbatim into JSON, TOML, Python and
YAML string literals.  The copier validator rejects the two characters that
break every one of them (`"` and `\\`, #501); this proves the characters it
deliberately allows — apostrophe, ampersand, angle brackets, non-ASCII —
still render every manifest as valid JSON and leave the bytes untouched
(`| tojson` would have rewritten them as `\\uXXXX` and diffed every
downstream blurb with an apostrophe).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import tomllib
import yaml

REPO = Path(__file__).resolve().parents[2]
ANSWERS = REPO / "tests" / "fixtures" / "smoke-answers.yml"
ALLOWED = "Peter's caf\u00e9 <index> & more \u2014 fast"
MANIFESTS = (
    "server.json",
    "packaging/mcpb/manifest.json.in",
    ".claude-plugin/plugin/.claude-plugin/plugin.json",
)


def _render(tmp_path: Path, blurb: str) -> Path:
    answers = yaml.safe_load(ANSWERS.read_text(encoding="utf-8"))
    answers["domain_description"] = blurb
    answers["include_claude_plugin"] = True
    answers_file = tmp_path / "answers.yml"
    answers_file.write_text(
        yaml.safe_dump(answers, allow_unicode=True), encoding="utf-8"
    )
    out = tmp_path / "rendered"
    result = subprocess.run(
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
            str(out),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    return out


def test_allowed_characters_render_valid_manifests_verbatim(tmp_path: Path) -> None:
    out = _render(tmp_path, ALLOWED)
    for rel in MANIFESTS:
        text = (out / rel).read_text(encoding="utf-8")
        assert json.loads(text)["description"] == ALLOWED, rel
        assert f'"description": "{ALLOWED}"' in text, f"{rel}: bytes were rewritten"
    manifest = json.loads((out / MANIFESTS[1]).read_text(encoding="utf-8"))
    assert manifest["long_description"] == ALLOWED
    pyproject = tomllib.loads((out / "pyproject.toml").read_text(encoding="utf-8"))
    assert pyproject["project"]["description"] == ALLOWED
