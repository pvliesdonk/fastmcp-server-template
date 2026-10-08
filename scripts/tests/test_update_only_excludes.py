"""Guard the files `copier.yml` excludes on update alone (#778).

A file rendered on `copier copy` but excluded on `copier update` belongs to
the project after the copy. `check_template_conformance.py` renders the
template as a copy and treats every file outside `_skip_if_exists` as
template-owned, so each such file must also be skip-listed, or every
project's own version of it would be reported as drift.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
_UPDATE_ONLY = re.compile(
    r"\{%\s*if\s+_copier_operation\s*==\s*'update'\s*%\}(?P<path>[^{]+)\{%\s*endif\s*%\}"
)


def _copier() -> dict:
    return yaml.safe_load((REPO / "copier.yml").read_text(encoding="utf-8"))


def _update_only_excludes() -> list[str]:
    found = [_UPDATE_ONLY.fullmatch(entry) for entry in _copier()["_exclude"]]
    return [m.group("path") for m in found if m]


def test_reference_pages_are_excluded_on_update() -> None:
    assert "docs/reference/tools/*.md" in _update_only_excludes()


def test_every_update_only_exclude_is_skip_listed() -> None:
    skip = set(_copier()["_skip_if_exists"])
    missing = [path for path in _update_only_excludes() if path not in skip]
    assert not missing, f"excluded on update but not in _skip_if_exists: {missing}"
