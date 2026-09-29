"""The nav migration also clears the removed llms.txt section list (#714).

Fixtures: a real ``copier update`` from v11.0.2 onto the branch that derives
llms.txt from the nav, taken with the migration unregistered, so the file
holds copier's raw conflicts (in ``plugins:`` and in ``nav:``).
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from migrate_docs_nav import migrate

FIX = Path(__file__).parent / "fixtures" / "llmstxt_migration"
HEAD = (FIX / "head_mkdocs.yml.txt").read_text(encoding="utf-8")
UPDATED = (FIX / "updated_mkdocs.yml.txt").read_text(encoding="utf-8")


def _llmstxt(text: str) -> dict:
    plugins = yaml.safe_load(text)["plugins"]
    return next(p["llmstxt"] for p in plugins if isinstance(p, dict) and "llmstxt" in p)


def test_no_conflict_markers_remain() -> None:
    text, _ = migrate(UPDATED, HEAD)
    for marker in ("<<<<<<<", "|||||||", ">>>>>>>"):
        assert marker not in text


def test_llmstxt_takes_the_template_side() -> None:
    text, _ = migrate(UPDATED, HEAD)
    assert _llmstxt(text) == {"full_output": "llms-full.txt", "sections": {}}
    assert "PROJECT-LLMSTXT-SECTIONS" not in text
    assert "PARA workflow, written by the project" not in text


def test_nav_is_still_migrated() -> None:
    _, parked = migrate(UPDATED, HEAD)
    assert sorted(parked) == ["api/vault.md", "guides/para.md"]


def test_second_run_changes_nothing() -> None:
    once, _ = migrate(UPDATED, HEAD)
    twice, parked = migrate(once, HEAD)
    assert twice == once
    assert parked == []
