"""Tests for scripts/migrate_docs_pages.py (#716, #717).

The reference-move fixtures are a real capture: a smoke render at the
integration head with a domain paragraph in docs/configuration.md and a tool
section in docs/tools/index.md, then `copier update` onto the #716 branch.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from migrate_docs_pages import (
    DOCS,
    README_BLOCKS,
    REDIRECTS,
    has_project_content,
    migrate,
    positional_blocks,
    rebase_links,
    resolve_nav_region,
    rewrite_links,
    rewrite_nav_paths,
    transplant,
    transplant_readme,
)

ROOT = Path(__file__).resolve().parents[2]
FIX = Path(__file__).parent / "fixtures" / "reference_migration"
DOMAIN_LINE = "SMOKE_MCP_VAULT and SMOKE_MCP_READ_ONLY interact"

OLD_README = (
    "<!-- DOMAIN-START -->\n<!-- Add an optional project logo. -->\n<!-- DOMAIN-END -->\n\n"
    "# Demo\n\n## Features\n\n"
    "<!-- DOMAIN-START -->\n- **Search:** finds notes.\n<!-- DOMAIN-END -->\n\n"
    "## What you can do with it\n\n"
    "<!-- DOMAIN-START -->\n- **[Task 1]:** placeholder text.\n<!-- DOMAIN-END -->\n\n"
    "### From PyPI\n\n"
    '<!-- DOMAIN-START -->\n- `pip install "demo[all]"` adds everything.\n<!-- DOMAIN-END -->\n\n'
    "## Key design decisions\n\n"
    "<!-- DOMAIN-START -->\n- Writes are append-only.\n<!-- DOMAIN-END -->\n"
)
NEW_README = "# Demo\n\n" + "".join(
    f"<!-- {name}-START -->\n<!-- hint -->\n<!-- {name}-END -->\n\n"
    for name in README_BLOCKS
)


def _git(root: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=root,
        check=True,
        capture_output=True,
    )


def _repo(tmp_path: Path, prompts: str | None = None, readme: str = OLD_README) -> Path:
    """A project as it stood before the update, committed, then as copier left it."""
    root = tmp_path / "proj"
    (root / "docs" / "tools").mkdir(parents=True)
    (root / "docs" / "deployment").mkdir(parents=True)
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
    (root / "docs" / "deployment" / "docker.md").write_text(
        "# Docker\n<!-- DOMAIN-DOCKER-EXTRA-START -->\nMount the vault at /data/vault.\n"
        "<!-- DOMAIN-DOCKER-EXTRA-END -->\n",
        encoding="utf-8",
    )
    (root / "README.md").write_text(readme, encoding="utf-8")
    _git(root, "init", "-q")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "before")
    for rel in (
        "docs/configuration.md",
        "docs/tools/index.md",
        "docs/prompts.md",
        "docs/deployment/docker.md",
    ):
        (root / rel).unlink()
    (root / "docs" / "reference").mkdir()
    (root / "docs" / "reference" / "configuration.md").write_text(
        (FIX / "updated_reference_configuration.md.txt").read_text(), encoding="utf-8"
    )
    (root / "docs" / "deploy").mkdir()
    # The new frame's pages the moves point at, as the update renders them.
    (root / "docs" / "security-model.md").write_text(
        "# Security model\n", encoding="utf-8"
    )
    (root / "docs" / "deploy" / "authentication.md").write_text(
        "# Authentication\n", encoding="utf-8"
    )
    (root / "docs" / "deploy" / "docker.md").write_text(
        "# Docker\n<!-- DOMAIN-DOCKER-EXTRA-START -->\n<!-- hint -->\n"
        "<!-- DOMAIN-DOCKER-EXTRA-END -->\n",
        encoding="utf-8",
    )
    (root / "README.md").write_text(NEW_README, encoding="utf-8")
    return root


def test_fixture_shape() -> None:
    assert DOMAIN_LINE in (FIX / "head_configuration.md.txt").read_text()
    assert (
        DOMAIN_LINE not in (FIX / "updated_reference_configuration.md.txt").read_text()
    )
    assert "search('x')" in (FIX / "head_tools_index.md.txt").read_text()


def test_blocks_are_carried_and_the_tools_page_parked(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    notes = migrate(root)
    new = (root / "docs" / "reference" / "configuration.md").read_text(encoding="utf-8")
    assert DOMAIN_LINE in new
    assert new.count("DOMAIN-CONFIG-VARS-START") == 1
    docker = (root / "docs" / "deploy" / "docker.md").read_text(encoding="utf-8")
    assert "Mount the vault at /data/vault." in docker
    assert (root / "docs" / "tools" / "index.md").exists()
    assert not (root / "docs" / "prompts.md").exists(), (
        "placeholder-only page is not parked"
    )
    assert not (root / "docs" / "configuration.md").exists()
    assert not (root / "docs" / "deployment" / "docker.md").exists()
    assert any(
        "docs/deployment/docker.md into docs/deploy/docker.md" in n for n in notes
    )
    assert any("parked docs/tools/index.md" in n for n in notes)
    assert migrate(root) == []


def test_readme_blocks_map_by_position_and_skip_placeholders(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    notes = migrate(root)
    readme = (root / "README.md").read_text(encoding="utf-8")
    assert (
        "- **Search:** finds notes."
        in readme.split("DOMAIN-README-PITCH-START")[1].split(
            "DOMAIN-README-PITCH-END"
        )[0]
    )
    assert "[Task 1]" not in readme, "the old placeholder is not carried"
    assert (
        "<!-- hint -->"
        in readme.split("DOMAIN-README-FIT-START")[1].split("DOMAIN-README-FIT-END")[0]
    )
    assert '`pip install "demo[all]"`' in readme.split("DOMAIN-README-EXTRAS-START")[1]
    assert "Writes are append-only." in readme.split("DOMAIN-README-DESIGN-START")[1]
    assert any("README.md's positional" in n for n in notes)
    assert any("still held the scaffold's placeholder" in n for n in notes)
    assert migrate(root) == []


def test_readme_with_fewer_blocks_keeps_positions(tmp_path: Path) -> None:
    short = "\n".join(OLD_README.split("\n")[0:3]) + (
        "\n\n# Demo\n\n## Features\n\n<!-- DOMAIN-START -->\n- **Search:** finds notes.\n"
        "<!-- DOMAIN-END -->\n"
    )
    root = _repo(tmp_path, readme=short)
    migrate(root)
    readme = (root / "README.md").read_text(encoding="utf-8")
    assert (
        "- **Search:** finds notes."
        in readme.split("DOMAIN-README-PITCH-START")[1].split(
            "DOMAIN-README-PITCH-END"
        )[0]
    )


def test_readme_block_without_a_home_is_reported() -> None:
    six = OLD_README + "\n<!-- DOMAIN-START -->\nsixth\n<!-- DOMAIN-END -->\n"
    _, missing, skipped = transplant_readme(six, NEW_README)
    assert missing == ["6"]
    assert skipped == ["3"], (
        "the [Task 1] placeholder block is reported, not silently dropped"
    )
    assert len(positional_blocks(six)) == 6


def test_readme_still_on_the_old_frame_is_left_alone(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    (root / "README.md").write_text(OLD_README, encoding="utf-8")
    migrate(root)
    assert (root / "README.md").read_text(encoding="utf-8") == OLD_README


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
    assert not has_project_content((FIX / "head_prompts.md.txt").read_text())
    assert has_project_content("<!-- DOMAIN-X-START -->\ntext\n<!-- DOMAIN-X-END -->\n")
    assert has_project_content("# rewritten\n")


def test_transplant_reports_blocks_without_a_home() -> None:
    old = (
        "<!-- DOMAIN-A-START -->\na\n<!-- DOMAIN-A-END -->\n"
        "<!-- DOMAIN-B-START -->\nb\n<!-- DOMAIN-B-END -->\n"
    )
    new = "x\n<!-- DOMAIN-A-START — with a comment -->\n<!-- hint -->\n<!-- DOMAIN-A-END -->\n"
    updated, missing = transplant(old, new)
    assert (
        updated
        == "x\n<!-- DOMAIN-A-START — with a comment -->\na\n<!-- DOMAIN-A-END -->\n"
    )
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


def test_readme_conflict_is_resolved_to_the_new_frame_then_mapped(
    tmp_path: Path,
) -> None:
    root = _repo(tmp_path)
    conflicted = (
        "# Demo\n\n"
        "<<<<<<< before updating\n"
        "## Configuration\n\n<!-- GENERATED-ENV-TABLE-CORE-START -->\n| a | b |\n"
        "<!-- GENERATED-ENV-TABLE-CORE-END -->\n"
        "||||||| last update\n"
        "## Configuration\n\n<!-- GENERATED-ENV-TABLE-CORE-START -->\n"
        "<!-- GENERATED-ENV-TABLE-CORE-END -->\n"
        "=======\n" + NEW_README.split("# Demo\n\n", 1)[1] + ">>>>>>> after updating\n"
    )
    (root / "README.md").write_text(conflicted, encoding="utf-8")
    notes = migrate(root)
    readme = (root / "README.md").read_text(encoding="utf-8")
    assert "<<<<<<<" not in readme
    assert "GENERATED-ENV-TABLE-CORE" not in readme
    assert "- **Search:** finds notes." in readme
    assert any("resolved README.md" in n for n in notes)
    assert migrate(root) == []


def test_links_at_moved_pages_are_rewritten_relative_to_the_page() -> None:
    text = (
        "See the [model](../guides/security-model.md#scope) and "
        "[docker](../deployment/docker.md), not [mine](../use/mine.md) "
        "or [web](https://x.org/guides/security-model.md)."
    )
    out = rewrite_links(text, "deployment/systemd.md")
    assert "[model](../security-model.md#scope)" in out
    assert "[docker](../deploy/docker.md)" in out
    assert "[mine](../use/mine.md)" in out
    assert "https://x.org/guides/security-model.md" in out
    assert (
        rewrite_links("[i](installation.md)", "index.md")
        == "[i](get-started/installation.md)"
    )


def test_migrate_rewrites_links_on_project_pages(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    page = root / "docs" / "deployment" / "systemd.md"
    page.write_text("# S\n\n[m](../guides/security-model.md)\n", encoding="utf-8")
    notes = migrate(root)
    assert "[m](../security-model.md)" in page.read_text(encoding="utf-8")
    assert any("docs/deployment/systemd.md" in n for n in notes)
    assert migrate(root) == []


def test_release_notes_are_rewritten_but_unpublished_history_and_fences_are_not(
    tmp_path: Path,
) -> None:
    # Release notes are published, so mkdocs build --strict checks their
    # links (#746); decision records are excluded from the build.
    root = _repo(tmp_path)
    (root / "docs" / "releases").mkdir()
    release = root / "docs" / "releases" / "1.0.md"
    release.write_text("# 1.0\n\n[m](../guides/security-model.md)\n", encoding="utf-8")
    (root / "docs" / "decisions").mkdir()
    decision = root / "docs" / "decisions" / "0001.md"
    decision.write_text("# 1\n\n[m](../guides/security-model.md)\n", encoding="utf-8")
    fenced = "# S\n\n```markdown\n[m](../guides/security-model.md)\n```\n\n[n](../guides/security-model.md)\n"
    page = root / "docs" / "deployment" / "systemd.md"
    page.write_text(fenced, encoding="utf-8")
    migrate(root)
    assert release.read_text(encoding="utf-8") == "# 1.0\n\n[m](../security-model.md)\n"
    assert (
        decision.read_text(encoding="utf-8")
        == "# 1\n\n[m](../guides/security-model.md)\n"
    )
    out = page.read_text(encoding="utf-8")
    assert "```markdown\n[m](../guides/security-model.md)\n```" in out
    assert "[n](../security-model.md)" in out


def test_links_at_every_redirected_page_are_rewritten(tmp_path: Path) -> None:
    # The seven links #746 found after a real v11.0.2 -> v11.1.0 update, plus
    # the pages that moved to contribute/ and the generated reference pages.
    root = _repo(tmp_path)
    for new in (
        "reference/configuration-generator.md",
        "reference/tools/index.md",
        "reference/prompts.md",
        "contribute/release-process.md",
    ):
        (root / "docs" / new).parent.mkdir(parents=True, exist_ok=True)
        (root / "docs" / new).write_text("# x\n", encoding="utf-8")
    index = root / "docs" / "index.md"
    index.write_text(
        "[gen](configuration-generator.md) [tools](tools/index.md)\n", encoding="utf-8"
    )
    (root / "docs" / "releases").mkdir()
    release = root / "docs" / "releases" / "5.0.md"
    release.write_text(
        "[c](../configuration.md#logging) [d](../deployment/docker.md) "
        "[p](../prompts.md) [r](../deployment/release-process.md)\n",
        encoding="utf-8",
    )
    migrate(root)
    assert index.read_text(encoding="utf-8") == (
        "[gen](reference/configuration-generator.md) [tools](reference/tools/index.md)\n"
    )
    assert release.read_text(encoding="utf-8") == (
        "[c](../reference/configuration.md#logging) [d](../deploy/docker.md) "
        "[p](../reference/prompts.md) [r](../contribute/release-process.md)\n"
    )


def _template_redirects() -> dict[str, str]:
    """The template's own entries in mkdocs.yml.jinja's redirect_maps."""
    text = (ROOT / "mkdocs.yml.jinja").read_text(encoding="utf-8")
    region = text.split("redirect_maps:\n", 1)[1].split("PROJECT-REDIRECTS-START", 1)[0]
    found = {}
    for line in region.splitlines():
        line = re.sub(r"\{%.*?%\}", "", line).strip()
        if line and not line.startswith("#"):
            old, new = (part.strip() for part in line.split(":", 1))
            found[old] = new
    return found


def test_every_template_redirect_is_followed() -> None:
    # A page the template moves and redirects, but the migration does not
    # follow, leaves links that fail mkdocs build --strict (#746).
    table = {old.removeprefix(DOCS): new.removeprefix(DOCS) for old, new in REDIRECTS}
    assert table == _template_redirects()


def test_carried_links_are_rebased_across_a_depth_change() -> None:
    body = (
        "See [auth](guides/authentication.md#modes), [docker](deployment/docker.md), "
        "[mine](use/mine.md) and [web](https://x.org/a.md).\n"
        "```\n[code](guides/authentication.md)\n```\n"
    )
    out = rebase_links(body, "docs/installation.md", "docs/get-started/installation.md")
    assert "[auth](../deploy/authentication.md#modes)" in out
    assert "[docker](../deploy/docker.md)" in out
    assert "[mine](../use/mine.md)" in out
    assert "https://x.org/a.md" in out
    assert "```\n[code](guides/authentication.md)\n```" in out
    up = rebase_links(
        "[d](../deployment/docker.md)",
        "docs/guides/security-model.md",
        "docs/security-model.md",
    )
    assert up == "[d](deploy/docker.md)"


def test_migrate_rebases_links_in_carried_blocks(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    old = root / "docs" / "installation.md"
    old.write_text(
        "# I\n<!-- DOMAIN-INSTALL-EXTRA-START -->\nSee [auth](guides/authentication.md).\n"
        "<!-- DOMAIN-INSTALL-EXTRA-END -->\n",
        encoding="utf-8",
    )
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "with installation page")
    old.unlink()
    (root / "docs" / "get-started").mkdir()
    new = root / "docs" / "get-started" / "installation.md"
    new.write_text(
        "# I\n<!-- DOMAIN-INSTALL-EXTRA-START -->\n<!-- hint -->\n<!-- DOMAIN-INSTALL-EXTRA-END -->\n",
        encoding="utf-8",
    )
    migrate(root)
    assert "[auth](../deploy/authentication.md)" in new.read_text(encoding="utf-8")


def test_fences_close_only_on_a_matching_marker() -> None:
    text = "~~~\n```\n[a](../guides/security-model.md)\n~~~\n[b](../guides/security-model.md)\n"
    out = rewrite_links(text, "deployment/x.md")
    assert "[a](../guides/security-model.md)" in out
    assert "[b](../security-model.md)" in out


def test_switched_off_page_is_reported_not_swallowed(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    (root / "docs" / "guides").mkdir()
    page = root / "docs" / "guides" / "authorization.md"
    page.write_text(
        "# A\n<!-- DOMAIN-AUTHZ-EXTRA-START -->\nours\n<!-- DOMAIN-AUTHZ-EXTRA-END -->\n",
        encoding="utf-8",
    )
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "authz")
    page.unlink()
    notes = migrate(root)
    assert any(
        "switched-off page" in n and "guides/authorization.md" in n for n in notes
    )


def test_blockless_old_page_is_noted_not_parked(tmp_path: Path) -> None:
    """A page without blocks may be a wholesale rewrite or an older template frame."""
    root = _repo(tmp_path)
    old = root / "docs" / "deployment" / "oidc.md"
    old.write_text(
        "# OIDC\n\nAn older template frame, or our own rewrite.\n", encoding="utf-8"
    )
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "blockless")
    old.unlink()
    (root / "docs" / "deploy" / "oidc.md").write_text(
        "# OIDC\n<!-- DOMAIN-OIDC-EXTRA-START -->\n<!-- hint -->\n<!-- DOMAIN-OIDC-EXTRA-END -->\n",
        encoding="utf-8",
    )
    notes = migrate(root)
    assert not old.exists(), "a pristine older frame must not be parked"
    assert any(
        "had no DOMAIN blocks" in n and "docs/deployment/oidc.md" in n for n in notes
    )
    new_page = root / "docs" / "deploy" / "oidc.md"
    new_text = new_page.read_text(encoding="utf-8")
    again = migrate(root)
    assert new_page.read_text(encoding="utf-8") == new_text
    assert again == [n for n in notes if "had no DOMAIN blocks" in n], (
        "a finding with no action to take recurs on every run; nothing else does"
    )


def test_links_to_a_switched_off_page_are_not_retargeted(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    page = root / "docs" / "deployment" / "systemd.md"
    page.write_text(
        "# S\n\n[authz](../guides/authorization.md) and [docker](../deployment/docker.md)\n",
        encoding="utf-8",
    )
    migrate(root)  # no docs/deploy/authorization.md exists under root
    out = page.read_text(encoding="utf-8")
    assert "[authz](../guides/authorization.md)" in out
    assert "[docker](../deploy/docker.md)" in out


def test_nav_entries_at_old_paths_are_retargeted() -> None:
    nav = (
        "site_name: x\n"
        "nav:\n"
        "  - Overview: index.md\n"
        "  - Deploy:\n"
        "      # PROJECT-NAV-DEPLOY-START\n"
        "      - Systemd: deployment/systemd.md\n"
        "      - Docker again: deployment/docker.md\n"
        "      - Model: guides/security-model.md\n"
        "      # PROJECT-NAV-DEPLOY-END\n"
        "plugins:\n"
        "  - search: deployment/docker.md\n"
    )
    out = rewrite_nav_paths(nav)
    assert "      - Docker again: deploy/docker.md\n" in out
    assert "      - Model: security-model.md\n" in out
    assert "      - Systemd: deployment/systemd.md\n" in out
    assert "  - search: deployment/docker.md\n" in out, "outside nav: untouched"
    assert rewrite_nav_paths(out) == out


def test_link_forms_with_title_angle_brackets_and_reference_definitions() -> None:
    text = (
        '[a](<../guides/security-model.md>) [b](../guides/security-model.md "The model")\n'
        "[c]: ../guides/security-model.md\n"
    )
    out = rewrite_links(text, "deployment/x.md")
    assert "[a](<../security-model.md>)" in out
    assert '[b](../security-model.md "The model")' in out
    assert "[c]: ../security-model.md" in out


def test_blocks_close_on_crlf_and_trailing_spaces() -> None:
    from migrate_docs_pages import blocks

    text = "<!-- DOMAIN-X-START -->\r\nbody\r\n<!-- DOMAIN-X-END -->  \r\n"
    assert blocks(text) == {"DOMAIN-X": "body\r\n"}
