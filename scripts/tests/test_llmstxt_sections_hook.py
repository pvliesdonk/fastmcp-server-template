"""Tests for scripts/llmstxt_sections_hook.py (#714)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from llmstxt_sections_hook import sections_from_nav


def _page(docs: Path, rel: str, front: str | None = None) -> None:
    path = docs / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    head = f"---\n{front}\n---\n" if front is not None else ""
    path.write_text(f"{head}# {rel}\n", encoding="utf-8")


def _never(_rel: str) -> bool:
    return False


def test_sections_follow_the_nav_and_flatten_nesting(tmp_path: Path) -> None:
    for rel in ("index.md", "a/one.md", "a/two.md", "b/three.md"):
        _page(tmp_path, rel)
    nav = [
        {"Overview": "index.md"},
        {"Section A": [{"One": "a/one.md"}, {"Deeper": [{"Two": "a/two.md"}]}]},
        {"Section B": ["b/three.md"]},
    ]
    sections = sections_from_nav(nav, tmp_path, _never)
    assert list(sections) == ["Overview", "Section A", "Section B"]
    assert sections["Section A"] == [{"a/one.md": ""}, {"a/two.md": ""}]
    assert sections["Overview"] == [{"index.md": ""}]


def test_page_outside_nav_joins_the_section_of_its_directory(tmp_path: Path) -> None:
    for rel in (
        "releases/index.md",
        "releases/3.0.md",
        "releases/1.x.md",
        "stray/x.md",
    ):
        _page(tmp_path, rel)
    nav = [{"Upgrade": [{"Release notes": "releases/index.md"}]}]
    sections = sections_from_nav(nav, tmp_path, _never)
    assert sections["Upgrade"] == [
        {"releases/index.md": ""},
        {"releases/1.x.md": ""},
        {"releases/3.0.md": ""},
    ]
    assert "stray/x.md" not in str(sections)


def test_excluded_pages_never_appear(tmp_path: Path) -> None:
    for rel in ("releases/index.md", "releases/next.md", "design/d.md"):
        _page(tmp_path, rel)
    nav = [{"Upgrade": ["releases/index.md"]}]
    sections = sections_from_nav(
        nav,
        tmp_path,
        lambda rel: rel == "releases/next.md" or rel.startswith("design/"),
    )
    assert sections == {"Upgrade": [{"releases/index.md": ""}]}


def test_descriptions_come_from_front_matter(tmp_path: Path) -> None:
    _page(tmp_path, "a.md", "description: What a is for.\nkind: reference")
    _page(tmp_path, "b.md", "just a string")
    _page(tmp_path, "c.md", "description: [unclosed")
    nav = [{"S": ["a.md", "b.md", "c.md", "https://example.com/ext"]}]
    sections = sections_from_nav(nav, tmp_path, _never)
    assert sections["S"] == [{"a.md": "What a is for."}, {"b.md": ""}, {"c.md": ""}]


def test_first_section_in_nav_order_claims_a_directory(tmp_path: Path) -> None:
    for rel in (
        "deployment/a.md",
        "deployment/b.md",
        "deployment/c.md",
        "deployment/x.md",
    ):
        _page(tmp_path, rel)
    nav = [
        {"Get started": ["deployment/a.md"]},
        {"Deploy": ["deployment/b.md", "deployment/c.md"]},
    ]
    sections = sections_from_nav(nav, tmp_path, _never)
    assert {"deployment/x.md": ""} in sections["Get started"]


def test_crlf_and_eof_front_matter(tmp_path: Path) -> None:
    (tmp_path / "crlf.md").write_bytes(
        b"---\r\ndescription: CRLF page.\r\n---\r\n# Crlf\r\n"
    )
    (tmp_path / "eof.md").write_text(
        "---\ndescription: Only front matter.\n---", encoding="utf-8"
    )
    sections = sections_from_nav([{"S": ["crlf.md", "eof.md"]}], tmp_path, _never)
    assert sections["S"] == [
        {"crlf.md": "CRLF page."},
        {"eof.md": "Only front matter."},
    ]


def test_unparseable_front_matter_is_logged(tmp_path: Path, caplog: object) -> None:
    import logging

    _page(tmp_path, "bad.md", "description: [unclosed")
    with caplog.at_level(logging.WARNING):  # type: ignore[attr-defined]
        sections_from_nav([{"S": ["bad.md"]}], tmp_path, _never)
    assert "llmstxt_front_matter_unparseable" in caplog.text  # type: ignore[attr-defined]


def test_bare_page_entry_is_titled_from_its_heading(tmp_path: Path) -> None:
    (tmp_path / "extra.md").write_text("# Extra material\n\nBody.\n", encoding="utf-8")
    sections = sections_from_nav(["extra.md"], tmp_path, _never)
    assert list(sections) == ["Extra material"]
