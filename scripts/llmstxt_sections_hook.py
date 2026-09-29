"""MkDocs hook: build the llms.txt sections from `nav:` (#714).

Registered under `hooks:` in mkdocs.yml.  The `llmstxt` plugin reads its
`sections` option when files are collected, after every `on_config` has run,
so filling that option here means `llms.txt` is derived from the navigation
and never kept as a second list.

- Each top-level nav entry is a section: a titled group lists its pages in
  nav order, nesting flattened; a titled single page is a one-page section.
- A published page that is not in the nav joins the section of a nav page
  in the same directory (per-minor release notes join the landing page's
  section), so every page a reader can reach from the site is indexed.
- Each page's description is its `description:` front matter, or empty.

External links and pages matched by `exclude_docs` never appear.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

if TYPE_CHECKING:
    from collections.abc import Callable

Sections = dict[str, list[dict[str, str]]]


def _pages(node: Any) -> list[str]:
    """Return the page paths under a nav node, in order."""
    if isinstance(node, str):
        return [] if "://" in node else [node]
    if isinstance(node, list):
        return [page for item in node for page in _pages(item)]
    if isinstance(node, dict):
        return [page for value in node.values() for page in _pages(value)]
    return []


def _description(docs_dir: Path, rel: str) -> str:
    """Return the page's `description:` front matter, or an empty string."""
    try:
        text = (docs_dir / rel).read_text(encoding="utf-8")
    except OSError:
        return ""
    if not text.startswith("---\n"):
        return ""
    try:
        front = yaml.safe_load(text.split("---\n", 2)[1])
    except yaml.YAMLError:
        return ""
    if not isinstance(front, dict):
        return ""
    value = front.get("description", "")
    return value if isinstance(value, str) else ""


def _nav_sections(nav: list[Any]) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    for entry in nav:
        if isinstance(entry, dict):
            title, value = next(iter(entry.items()))
        else:
            title, value = entry, entry
        pages = _pages(value)
        if pages:
            sections.setdefault(str(title), []).extend(pages)
    return sections


def sections_from_nav(
    nav: list[Any], docs_dir: Path, excluded: Callable[[str], bool]
) -> Sections:
    """Return llms.txt sections derived from *nav* and the files in *docs_dir*."""
    by_section = _nav_sections(nav)
    listed = {page for pages in by_section.values() for page in pages}
    home: dict[str, str] = {}
    for title, pages in by_section.items():
        for page in pages:
            home.setdefault(Path(page).parent.as_posix(), title)
    for path in sorted(docs_dir.rglob("*.md")):
        rel = path.relative_to(docs_dir).as_posix()
        if rel in listed or excluded(rel):
            continue
        section = home.get(Path(rel).parent.as_posix())
        if section is not None:
            by_section[section].append(rel)
    return {
        title: [{page: _description(docs_dir, page)} for page in pages]
        for title, pages in by_section.items()
    }


def on_config(config: Any) -> Any:
    """Fill the llmstxt plugin's `sections` from the nav."""
    plugin = config["plugins"].get("llmstxt")
    if plugin is None or not config["nav"]:
        return config
    spec = config["exclude_docs"]

    def excluded(rel: str) -> bool:
        return spec is not None and bool(spec.match_file(rel))

    plugin.config["sections"] = sections_from_nav(
        config["nav"], Path(config["docs_dir"]), excluded
    )
    return config
