"""Move a downstream's nav onto the goal-shaped frame during `copier update`.

Runs from copier.yml `_migrations` (after-stage, every update).  Before the
frame, the whole `nav:` was one project-owned `PROJECT-NAV` block; now the
template owns the frame and gives each section its own `PROJECT-NAV-<SECTION>`
block.  Copier cannot map one onto the other, so it leaves diff3 conflict
markers in `nav:` (`<<<<<<< before updating`, `||||||| last update`,
`=======`, `>>>>>>> after updating`).  The project's real pre-update nav is
still at git HEAD, so recover from there, never from the conflict-marked file.

Steps (each printed when taken):
1. Resolve every conflict inside `nav:` to its "after updating" side, which
   together with the cleanly merged lines is the new frame.
2. Read HEAD:mkdocs.yml's old `PROJECT-NAV` block and keep each entry whose
   page the resolved nav does not already list, with its section titles.
3. Write those entries into the `PROJECT-NAV-UNSORTED` block at the end of
   `nav:` for the maintainer to sort into the section blocks.

Nothing outside `nav:` is changed.  Idempotent; a no-op on `copier copy` (no
HEAD:mkdocs.yml) and on a project whose HEAD already has the frame.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

OLD_START = "# PROJECT-NAV-START"
OLD_END = "# PROJECT-NAV-END"
NEW_MARKER = "PROJECT-NAV-USE-START"
UNSORTED_START = "PROJECT-NAV-UNSORTED-START"
UNSORTED_END = "PROJECT-NAV-UNSORTED-END"


def _nav_bounds(lines: list[str]) -> tuple[int, int]:
    """Return ``(first, stop)``: the ``nav:`` line and the line after its block."""
    first = lines.index("nav:")
    stop = first + 1
    while stop < len(lines):
        line = lines[stop]
        top_level = line and not line.startswith((" ", "#", "<", "|", "=", ">"))
        if top_level:
            break
        stop += 1
    return first, stop


def _resolve(region: list[str]) -> list[str]:
    """Keep clean lines and each conflict's "after updating" side."""
    out: list[str] = []
    side = None
    for line in region:
        if line.startswith("<<<<<<< "):
            side = "before"
        elif line.startswith("||||||| "):
            side = "base"
        elif line.startswith("=======") and side is not None:
            side = "after"
        elif line.startswith(">>>>>>> "):
            side = None
        elif side in (None, "after"):
            out.append(line)
    return out


def _leaves(node: Any) -> list[str]:
    if isinstance(node, str):
        return [node]
    if isinstance(node, list):
        return [leaf for item in node for leaf in _leaves(item)]
    if isinstance(node, dict):
        return [leaf for value in node.values() for leaf in _leaves(value)]
    return []


def _old_project_nav(head_text: str) -> list[Any] | None:
    if NEW_MARKER in head_text or OLD_START not in head_text:
        return None
    lines = head_text.splitlines()
    start = next(
        i for i, line in enumerate(lines) if line.strip().startswith(OLD_START)
    )
    end = next(i for i, line in enumerate(lines) if line.strip().startswith(OLD_END))
    body = [
        line for line in lines[start + 1 : end] if not line.lstrip().startswith("#")
    ]
    loaded = yaml.safe_load("nav:\n" + "\n".join(body))
    return loaded["nav"] if loaded else []


def _keep_missing(node: Any, present: set[str]) -> Any:
    """Drop leaves already present in the nav, and sections left empty."""
    if isinstance(node, str):
        return None if node in present else node
    if isinstance(node, list):
        items = [
            k for k in (_keep_missing(item, present) for item in node) if k is not None
        ]
        return items or None
    if isinstance(node, dict):
        mapping: dict[str, Any] = {}
        for key, value in node.items():
            sub = _keep_missing(value, present)
            if sub is not None:
                mapping[key] = sub
        return mapping or None
    return None


class _IndentedDumper(yaml.SafeDumper):
    """Indent lists under their key, matching the nav frame's style."""

    def increase_indent(self, flow: bool = False, indentless: bool = False) -> None:
        del indentless  # PyYAML passes it by keyword; always indent instead
        super().increase_indent(flow, False)


def park(updated_text: str, head_text: str) -> tuple[str, list[str]]:
    """Return the migrated ``mkdocs.yml`` text and the parked page paths."""
    lines = updated_text.split("\n")
    first, stop = _nav_bounds(lines)
    region = _resolve(lines[first + 1 : stop])
    old_nav = _old_project_nav(head_text)
    parked: list[str] = []
    if old_nav:
        present = set(_leaves(yaml.safe_load("nav:\n" + "\n".join(region))["nav"]))
        missing = _keep_missing(old_nav, present)
        if missing:
            parked = _leaves(missing)
            dumped = yaml.dump(
                missing,
                Dumper=_IndentedDumper,
                sort_keys=False,
                default_flow_style=False,
                allow_unicode=True,
            )
            block = ["  " + line for line in dumped.rstrip("\n").split("\n")]
            end = next(i for i, line in enumerate(region) if UNSORTED_END in line)
            region = region[:end] + block + region[end:]
    new_lines = lines[: first + 1] + region + lines[stop:]
    return "\n".join(new_lines), parked


def _head_mkdocs(root: Path) -> str | None:
    try:
        return subprocess.run(
            ["git", "show", "HEAD:mkdocs.yml"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def main() -> int:
    root = Path.cwd()
    path = root / "mkdocs.yml"
    head = _head_mkdocs(root)
    if head is None or not path.exists() or NEW_MARKER in head:
        return 0
    before = path.read_text(encoding="utf-8")
    after, parked = park(before, head)
    if after != before:
        path.write_text(after, encoding="utf-8")
        print("migrate_docs_nav: rebuilt nav: on the section frame")
    if parked:
        print(
            f"migrate_docs_nav: parked {len(parked)} of your nav entries under "
            "Unsorted at the end of nav: in mkdocs.yml; move each into the "
            "section it belongs to, then `git add mkdocs.yml`"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
