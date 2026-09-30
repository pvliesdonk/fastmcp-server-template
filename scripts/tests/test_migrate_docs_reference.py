"""Tests for scripts/migrate_docs_reference.py (#716).

Fixtures are a real capture: a smoke render at the integration head with a
domain paragraph in docs/configuration.md and a tool section in
docs/tools/index.md, then `copier update` onto the #716 branch (which
deletes the four old pages and renders docs/reference/).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from migrate_docs_reference import (
    has_project_content,
    migrate,
    resolve_nav_region,
    transplant,
)

FIX = Path(__file__).parent / "fixtures" / "reference_migration"
DOMAIN_LINE = "SMOKE_MCP_VAULT and SMOKE_MCP_READ_ONLY interact"


def _git(root: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=root,
        check=True,
        capture_output=True,
    )


def _repo(tmp_path: Path, prompts: str | None = None) -> Path:
    """A project as it stood before the update, committed, then as copier left it."""
    root = tmp_path / "proj"
    (root / "docs" / "tools").mkdir(parents=True)
    (root / "docs" / "configuration.md").write_text(
        (FIX / "head_configuration.md.txt").read_text(), encoding="utf-8"
    )
    (root / "docs" / "tools" / "index.md").write_text(
        (FIX / "head_tools_index.md.txt").read_text(), encoding="utf-8"
    )
    (root / "docs" / "prompts.md").write_text(
        prompts if prompts is not None else (FIX / "head_prompts.md.txt").read_text(),
        encoding="utf-8",
    )
    _git(root, "init", "-q")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "before")
    for rel in ("docs/configuration.md", "docs/tools/index.md", "docs/prompts.md"):
        (root / rel).unlink()
    (root / "docs" / "reference").mkdir()
    (root / "docs" / "reference" / "configuration.md").write_text(
        (FIX / "updated_reference_configuration.md.txt").read_text(), encoding="utf-8"
    )
    return root


def test_fixture_shape() -> None:
    assert DOMAIN_LINE in (FIX / "head_configuration.md.txt").read_text()
    assert (
        DOMAIN_LINE not in (FIX / "updated_reference_configuration.md.txt").read_text()
    )
    assert "search('x')" in (FIX / "head_tools_index.md.txt").read_text()


def test_domain_block_is_carried_and_tools_page_parked(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    notes = migrate(root)
    new = (root / "docs" / "reference" / "configuration.md").read_text(encoding="utf-8")
    assert DOMAIN_LINE in new
    assert new.count("DOMAIN-CONFIG-VARS-START") == 1
    assert (root / "docs" / "tools" / "index.md").exists()
    assert not (root / "docs" / "prompts.md").exists(), (
        "placeholder-only page is not parked"
    )
    assert not (root / "docs" / "configuration.md").exists()
    assert any("carried" in n for n in notes)
    assert any("parked docs/tools/index.md" in n for n in notes)
    assert migrate(root) == []


def test_rewritten_page_without_blocks_counts_as_project_content(
    tmp_path: Path,
) -> None:
    root = _repo(tmp_path, prompts="# Prompts\n\nOur own page, no markers.\n")
    migrate(root)
    assert (root / "docs" / "prompts.md").exists()


def test_has_project_content() -> None:
    assert not has_project_content(
        "<!-- DOMAIN-X-START -->\n<!-- hint -->\n<!-- DOMAIN-X-END -->\n"
    )
    assert has_project_content("<!-- DOMAIN-X-START -->\ntext\n<!-- DOMAIN-X-END -->\n")
    assert has_project_content("# rewritten\n")


def test_transplant_reports_blocks_without_a_home() -> None:
    old = "<!-- DOMAIN-A-START -->\na\n<!-- DOMAIN-A-END -->\n<!-- DOMAIN-B-START -->\nb\n<!-- DOMAIN-B-END -->\n"
    new = "x\n<!-- DOMAIN-A-START -->\n<!-- hint -->\n<!-- DOMAIN-A-END -->\n"
    updated, missing = transplant(old, new)
    assert updated == "x\n<!-- DOMAIN-A-START -->\na\n<!-- DOMAIN-A-END -->\n"
    assert missing == ["DOMAIN-B"]


def test_no_op_without_old_pages_in_head(tmp_path: Path) -> None:
    root = tmp_path / "fresh"
    root.mkdir()
    _git(root, "init", "-q")
    (root / "README.md").write_text("x\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "x")
    assert migrate(root) == []


NAV_CONFLICT = (
    "      - Tools:\n"
    "          - Overview: reference/tools/index.md\n"
    "          # GENERATED-NAV-TOOLS-START — one entry per tool group\n"
    "<<<<<<< before updating\n"
    "          - Reading: reference/tools/reading.md\n"
    "||||||| last update\n"
    "          - Tools: reference/tools/tools.md\n"
    "=======\n"
    "          - Tools: reference/tools/tools.md\n"
    "          - Server info: reference/tools/server_info.md\n"
    ">>>>>>> after updating\n"
    "          # GENERATED-NAV-TOOLS-END\n"
    "      - Resources: reference/resources.md\n"
    "<<<<<<< before updating\n"
    "      - Mine: use/mine.md\n"
    "=======\n"
    "      - Theirs: use/theirs.md\n"
    ">>>>>>> after updating\n"
)


def test_nav_region_conflict_takes_the_template_side_only_there() -> None:
    out = resolve_nav_region(NAV_CONFLICT)
    assert "<<<<<<< before updating\n          - Reading" not in out
    assert "          - Server info: reference/tools/server_info.md\n" in out
    assert "reading.md" not in out
    assert "<<<<<<< before updating\n      - Mine" in out, (
        "a conflict outside the region is left"
    )
    assert resolve_nav_region(out) == out


def test_nav_region_conflict_is_resolved_by_migrate(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    (root / "mkdocs.yml").write_text(
        NAV_CONFLICT.split("      - Resources")[0], encoding="utf-8"
    )
    notes = migrate(root)
    assert any("GENERATED-NAV-TOOLS" in n for n in notes)
    assert "<<<<<<<" not in (root / "mkdocs.yml").read_text(encoding="utf-8")
