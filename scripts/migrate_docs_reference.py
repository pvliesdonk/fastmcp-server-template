"""Carry a project's reference prose across the move to docs/reference/ (#716).

Run by copier's ``_migrations`` after an update.  The template stopped
rendering ``docs/configuration.md``, ``docs/configuration-generator.md``,
``docs/tools/index.md`` and ``docs/prompts.md``; the update therefore
deletes them, and the reference now lives under ``docs/reference/``, where
``scripts/gen_reference.py`` writes the tool, resource, prompt and CLI pages
from the code.  Copier requires a clean tree, so ``HEAD`` still holds each
deleted page; this script reads them from there.

Template script parks, implementation agent sorts:

- ``docs/configuration.md``: the content of its ``DOMAIN-*`` blocks is
  transplanted into the same blocks of ``docs/reference/configuration.md``.
- ``docs/tools/index.md`` and ``docs/prompts.md``: when they carry project
  content (text in a ``DOMAIN-*`` block, or a page rewritten without the
  blocks), the page is restored where it was, as a parked page.  The agent
  applying the update moves each example into its tool's or prompt's
  ``DOMAIN-EXAMPLE-<name>`` slot and each piece of task guidance into a Use
  page, then deletes the parked page; ``scripts/check_docs_structure.py``
  reports E2 on it until then, and its old URL shows the parked page instead
  of the redirect.  The update is not finished while a parked page exists.

The ``GENERATED-NAV-TOOLS`` region of ``mkdocs.yml`` is template text that
every project's generator overwrites, so a template change to it conflicts
on update; a conflict inside that region is resolved to the template's side,
since ``gen_reference.py`` rewrites the region next.

Idempotent: a page already restored, or a block already carried, is left
alone; a project whose HEAD has no old page is a no-op.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

CONFIG_OLD = "docs/configuration.md"
CONFIG_NEW = "docs/reference/configuration.md"
PARKED = ("docs/tools/index.md", "docs/prompts.md")
NEXT_STEPS = (
    "run `uv run python scripts/gen_reference.py` to write docs/reference/ from the code",
    "run `uv run python scripts/check_docs_structure.py`; an E2 on a parked page means "
    "its content still has to move into DOMAIN-EXAMPLE slots or Use pages, after "
    "which the parked page is deleted",
)

NAV_START = "GENERATED-NAV-TOOLS-START"
NAV_END = "GENERATED-NAV-TOOLS-END"
_CONFLICT = re.compile(
    r"^<<<<<<< before updating\n(?P<before>.*?)"
    r"(?:^\|\|\|\|\|\|\| last update\n(?P<base>.*?))?"
    r"^=======\n(?P<after>.*?)^>>>>>>> after updating\n",
    re.DOTALL | re.MULTILINE,
)

_BLOCK = re.compile(
    r"<!-- (DOMAIN-[A-Za-z0-9_.-]+?)-START -->\n(.*?)<!-- \1-END -->", re.DOTALL
)
_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
# What the deleted pages' blocks held on a fresh render, comments stripped:
# a block still saying this carries nothing the project wrote.
_PLACEHOLDERS = frozenset(
    {
        "",
        '## ping\n\nHealth-check tool that returns `"pong"` if the service is alive.',
        "## Built-in prompts\n\n_None yet._",
    }
)


def _head(root: Path, rel: str) -> str | None:
    """Return *rel* as committed at HEAD, or None when HEAD has no such file."""
    try:
        return subprocess.run(
            ["git", "show", f"HEAD:{rel}"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def blocks(text: str) -> dict[str, str]:
    """Return ``DOMAIN-*`` block name -> body for *text*."""
    return dict(_BLOCK.findall(text))


def has_project_content(text: str) -> bool:
    """True when a page carries text the project wrote.

    Text inside a ``DOMAIN-*`` block other than comments counts; so does a
    page with no blocks at all, which the project rewrote wholesale.
    """
    found = blocks(text)
    if not found:
        return True
    return any(_written(body) for body in found.values())


def _written(body: str) -> bool:
    return _COMMENT.sub("", body).strip() not in _PLACEHOLDERS


def transplant(old: str, new: str) -> tuple[str, list[str]]:
    """Copy each ``DOMAIN-*`` block body of *old* into *new*.

    Returns the updated *new* and the names of blocks *old* has that *new*
    lacks, which cannot be carried automatically.
    """
    targets = blocks(new)
    missing = []
    for name, body in blocks(old).items():
        if not _written(body):
            continue
        if name not in targets:
            missing.append(name)
            continue
        start, end = f"<!-- {name}-START -->\n", f"<!-- {name}-END -->"
        i = new.index(start) + len(start)
        j = new.index(end, i)
        new = new[:i] + body + new[j:]
    return new, missing


def resolve_nav_region(text: str) -> str:
    """Take the template's side of any conflict inside the nav tools region.

    A conflict counts as inside the region when the text before it sits
    between the region's markers, or when the after side carries the
    markers itself (the template moved or reworded the region).
    """

    def choose(match: re.Match[str]) -> str:
        prefix = text[: match.start()]
        inside = prefix.rfind(NAV_START) > prefix.rfind(NAV_END)
        after = match.group("after")
        if inside or NAV_START in after:
            return after
        return match.group(0)

    return _CONFLICT.sub(choose, text)


def migrate(root: Path) -> list[str]:
    """Apply the migration under *root*; return the lines to print."""
    notes: list[str] = []
    old_config = _head(root, CONFIG_OLD)
    new_path = root / CONFIG_NEW
    if (
        old_config is not None
        and new_path.exists()
        and not (root / CONFIG_OLD).exists()
    ):
        updated, missing = transplant(old_config, new_path.read_text(encoding="utf-8"))
        if updated != new_path.read_text(encoding="utf-8"):
            new_path.write_text(updated, encoding="utf-8")
            notes.append(f"carried the DOMAIN blocks of {CONFIG_OLD} into {CONFIG_NEW}")
        if missing:
            (root / CONFIG_OLD).write_text(old_config, encoding="utf-8")
            notes.append(
                f"parked {CONFIG_OLD}: its block(s) {', '.join(missing)} have no home in "
                f"{CONFIG_NEW}; move the content, then delete the parked page"
            )
    mkdocs = root / "mkdocs.yml"
    if mkdocs.exists():
        before = mkdocs.read_text(encoding="utf-8")
        after = resolve_nav_region(before)
        if after != before:
            mkdocs.write_text(after, encoding="utf-8")
            notes.append(
                "resolved the conflict in mkdocs.yml's GENERATED-NAV-TOOLS region to "
                "the template's side; gen_reference.py rewrites it"
            )
    for rel in PARKED:
        old = _head(root, rel)
        if old is None or (root / rel).exists() or not has_project_content(old):
            continue
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(old, encoding="utf-8")
        notes.append(
            f"parked {rel}: move its examples into the DOMAIN-EXAMPLE slots under "
            "docs/reference/ and its task guidance into docs/use/, then delete it"
        )
    return notes


def main() -> int:
    root = Path.cwd()
    notes = migrate(root)
    for note in notes:
        print(f"migrate_docs_reference: {note}")
    if notes:
        for step in NEXT_STEPS:
            print(f"migrate_docs_reference: next, {step}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
