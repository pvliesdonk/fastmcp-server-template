"""The template repo's own `ruff.toml` mirrors the rendered project's
`[tool.ruff]` block, and never reaches a render (#568).

`ruff.toml` exists so the pre-commit hooks and template-ci's lint and format
steps read one rule set instead of ruff's shifting defaults.  It is meant to
apply to `scripts/` exactly what a downstream applies to its own code, so the
`select`, `ignore`, line length and target must equal what
`pyproject.toml.jinja` renders — and copier must keep the file out of a
render, where it would shadow that block.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]

# ruff renamed the flake8-type-checking prefix; both spellings select the
# same rules, and the rendered block still carries the older one.
_ALIASES = {"TCH": "TC"}


def _ruff_toml() -> dict:
    return tomllib.loads((REPO / "ruff.toml").read_text(encoding="utf-8"))


def _rendered_ruff_block() -> dict:
    """The `[tool.ruff]` and `[tool.ruff.lint]` tables of pyproject.toml.jinja.

    That region carries no Jinja, so the slice between the `[tool.ruff]`
    header and the per-file-ignores table parses as plain TOML.
    """
    text = (REPO / "pyproject.toml.jinja").read_text(encoding="utf-8")
    start = text.index("[tool.ruff]\n")
    end = text.index("[tool.ruff.lint.per-file-ignores]")
    return tomllib.loads(text[start:end])["tool"]["ruff"]


def _normalise(codes: list[str]) -> set[str]:
    return {_ALIASES.get(code, code) for code in codes}


def test_ruff_toml_mirrors_the_rendered_block():
    ours = _ruff_toml()
    theirs = _rendered_ruff_block()
    assert ours["target-version"] == theirs["target-version"]
    assert ours["line-length"] == theirs["line-length"]
    assert _normalise(ours["lint"]["select"]) == _normalise(theirs["lint"]["select"])
    assert ours["lint"]["ignore"] == theirs["lint"]["ignore"]


def test_ruff_toml_is_kept_out_of_renders():
    copier = yaml.safe_load((REPO / "copier.yml").read_text(encoding="utf-8"))
    assert "ruff.toml" in copier["_exclude"]
