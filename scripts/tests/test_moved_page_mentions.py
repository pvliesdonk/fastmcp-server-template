"""No template-owned file names a moved docs page at its old path (#758).

The page migration rewrites links on a project's own pages; text the
template ships is the template's to keep current.  A mention such as
``docs/deployment/integration-branches.md`` in a re-rendered page is stale,
and a project that corrects it is then reported as drifting from the
template.  History keeps its old paths: the upgrade notes, the changelog,
the migrations that map old to new, and comments in ``copier.yml``.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from migrate_docs_pages import REDIRECTS

ROOT = Path(__file__).resolve().parents[2]

HISTORY = (
    "CHANGELOG.md",
    "UPGRADING.md",
    "upgrading/",
    "docs/decisions/",
    "docs/superpowers/",
    "scripts/migrate_docs_pages.py",
    "scripts/migrate_docs_nav.py",
    "scripts/tests/",
)
_MENTION = re.compile(
    r"(?<![\w/.-])(" + "|".join(re.escape(old) for old, _ in REDIRECTS) + r")(?![\w/-])"
)


def _tracked() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files"], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout
    return [rel for rel in out.splitlines() if not rel.startswith(HISTORY)]


def stale_mentions(rel: str, text: str) -> list[str]:
    """Return ``path:line: old path`` for each mention of a moved page's old path."""
    found: list[str] = []
    for number, line in enumerate(text.splitlines(), 1):
        if rel == "copier.yml" and line.lstrip().startswith("#"):
            continue
        found.extend(f"{rel}:{number}: {m.group(1)}" for m in _MENTION.finditer(line))
    return found


def test_the_pattern_finds_an_old_path_and_not_a_new_one() -> None:
    assert stale_mentions("x.md", "supports `docs/deployment/oidc.md`, and") == [
        "x.md:1: docs/deployment/oidc.md"
    ]
    assert stale_mentions("x.md", "see docs/deploy/oidc.md") == []
    assert stale_mentions("x.md", "see docs/reference/tools/index.md") == []
    assert stale_mentions("copier.yml", "# docs/guides/authorization.md moved") == []


def test_no_template_file_names_a_moved_page_at_its_old_path() -> None:
    found: list[str] = []
    for rel in _tracked():
        path = ROOT / rel
        if path.is_symlink() or not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        found.extend(stale_mentions(rel, text))
    assert found == [], "\n".join(found)
