"""Tests for scripts/check_docs_structure.py (#715)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from check_docs_structure import collect, main

GOOD_FRONT = '---\ndescription: "A page."\nkind: how-to\n---\n\n'
SEC = "See the [security model](guides/security-model.md).\n"

MKDOCS = """site_name: t
exclude_docs: |
  design/**
  releases/next.md
  drafts

nav:
  - Overview: index.md
  - Security model: guides/security-model.md
  - Use:
      - Overview: use/index.md
      # PROJECT-NAV-USE-START — x
      # PROJECT-NAV-USE-END
  # PROJECT-NAV-UNSORTED-START — x
{unsorted}  # PROJECT-NAV-UNSORTED-END
"""


def _repo(tmp_path: Path, unsorted: str = "", strict: bool = False) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "mkdocs.yml").write_text(
        MKDOCS.format(unsorted=unsorted), encoding="utf-8"
    )
    (tmp_path / "pyproject.toml").write_text(
        f"[tool.docs-structure]\nstrict = {'true' if strict else 'false'}\n",
        encoding="utf-8",
    )
    _page(tmp_path, "index.md", GOOD_FRONT + "# Home\n" + SEC)
    _page(tmp_path, "guides/security-model.md", GOOD_FRONT + "# Security\n")
    _page(
        tmp_path,
        "use/index.md",
        GOOD_FRONT + "# Use\n" + SEC.replace("guides/", "../guides/"),
    )
    return tmp_path


def _page(root: Path, rel: str, text: str) -> None:
    path = root / "docs" / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _codes(root: Path) -> list[tuple[str, str]]:
    return sorted((f.code, f.path) for f in collect(root))


def test_clean_repo_has_no_findings(tmp_path: Path) -> None:
    assert _codes(_repo(tmp_path)) == []


def test_e1_links_that_leave_the_site(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    _page(root, "design/d.md", "# internal\n")
    (root / "docs" / "img.png").write_bytes(b"x")
    _page(root, "use/my page.md", GOOD_FRONT + "# Spaced\n")
    _page(
        root,
        "use/p.md",
        GOOD_FRONT
        + "# P\n[design](../design/d.md) [ex](../../examples/okf/) [gone](missing.md)"
        + " [abs](/index.md)\n"
        + "[ok](../index.md#home) [img](../img.png) [web](https://x.org) [top](#p)"
        + " [sp](my%20page.md)\n"
        + "```\n[in code](../design/d.md)\n```\n",
    )
    e1 = [f for f in collect(root) if f.code == "E1"]
    assert sorted(f.message.split(" ")[0] for f in e1) == [
        "../../examples/okf/",
        "../design/d.md",
        "/index.md",
        "missing.md",
    ]
    assert all(f.line == 7 for f in e1)
    assert any("root-relative" in f.message for f in e1)


def test_e2_page_unreachable_from_nav(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    _page(root, "use/extra.md", GOOD_FRONT + "# Near a nav page\n")
    _page(root, "stray/x.md", GOOD_FRONT + "# Nowhere\n")
    _page(root, "releases/next.md", "# excluded\n")
    assert ("E2", "docs/stray/x.md") in _codes(root)
    assert ("E2", "docs/use/extra.md") not in _codes(root)
    assert all(path != "docs/releases/next.md" for _, path in _codes(root))


def test_e3_template_entry_page_without_security_link(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    _page(root, "index.md", GOOD_FRONT + "# Home\nNo link here.\n")
    assert ("E3", "docs/index.md") in _codes(root)


def test_e3_counts_only_a_real_link(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    _page(root, "index.md", GOOD_FRONT + "# Home\n```\nsecurity-model.md\n```\n")
    _page(
        root,
        "deployment/docker.md",
        GOOD_FRONT + "# Docker\n" + SEC.replace("guides/", "../guides/"),
    )
    codes = _codes(root)
    assert ("E3", "docs/index.md") in codes
    assert ("E3", "docs/deployment/docker.md") not in codes


def test_exclude_docs_bare_name_matches_any_component(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    _page(root, "drafts/x.md", "# draft\n")
    _page(root, "use/drafts/y.md", "# draft\n")
    assert all("drafts" not in path for _, path in _codes(root))


def test_w1_page_outside_designated_places(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    _page(root, "guides/para.md", GOOD_FRONT + "# PARA\n")
    _page(root, "use/para.md", GOOD_FRONT + "# PARA\n")
    codes = _codes(root)
    assert ("W1", "docs/guides/para.md") in codes
    assert ("W1", "docs/use/para.md") not in codes


def test_w2_front_matter(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    _page(root, "use/a.md", "# No front matter\n")
    _page(root, "use/b.md", '---\ndescription: "x"\nkind: essay\n---\n# Bad kind\n')
    codes = _codes(root)
    assert ("W2", "docs/use/a.md") in codes
    assert ("W2", "docs/use/b.md") in codes


def test_front_matter_behind_a_bom_is_read(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    (root / "docs" / "use" / "bom.md").write_bytes(
        b"\xef\xbb\xbf" + (GOOD_FRONT + "# BOM\n").encode("utf-8")
    )
    assert ("W2", "docs/use/bom.md") not in _codes(root)


def test_w3_unsorted_entries(tmp_path: Path) -> None:
    root = _repo(tmp_path, unsorted="  - Guides:\n      - PARA: use/index.md\n")
    assert ("W3", "mkdocs.yml") in _codes(root)


def test_exit_codes_follow_level_and_strict(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    _page(root, "use/a.md", "# warning only\n")
    assert main(["--root", str(root)]) == 0
    assert main(["--root", str(root), "--strict"]) == 1
    strict_root = _repo(tmp_path / "s", strict=True)
    _page(strict_root, "use/a.md", "# warning only\n")
    assert main(["--root", str(strict_root)]) == 1
    _page(root, "stray/x.md", GOOD_FRONT + "# error\n")
    assert main(["--root", str(root)]) == 1


def test_w1_skips_pages_the_reference_generator_writes(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    _page(
        root,
        "reference/tools/reading.md",
        GOOD_FRONT
        + "<!-- generated by scripts/gen_reference.py; edit the docstrings, not this page -->\n# Reading\n",
    )
    assert ("W1", "docs/reference/tools/reading.md") not in _codes(root)


def test_w4_python_block_without_a_tag(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    _page(
        root,
        "use/x.md",
        GOOD_FRONT
        + "# X\n```python\nx = 1\n```\n```python { .run }\ny = 2\n```\n```python {.fragment}\nz\n```\n```bash\nls\n```\n",
    )
    _page(root, "use/y.md", GOOD_FRONT + "# Y\n```py\na\n```\n```pycon\n>>> 1\n```\n")
    (root / "README.md").write_text("# R\n```python\nr = 1\n```\n", encoding="utf-8")
    w4 = [f for f in collect(root) if f.code == "W4"]
    assert sorted((f.path, f.line) for f in w4) == [
        ("README.md", 2),
        ("docs/use/x.md", 7),
        ("docs/use/y.md", 7),
    ]
